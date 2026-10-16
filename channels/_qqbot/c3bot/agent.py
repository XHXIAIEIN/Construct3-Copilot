"""The model's tool loop: one answer from a question, a chat history and the tools of the knowledge plugin.

The configured Copilot provider supplies the tools, prompts and answer checks; reply.py handles
the reply's length and phrasing, usage.py counts tokens, config.py reads the settings. This module builds the
conversation, hands the model its tools, runs each call, checks and shortens the final text, and packs a
project that is to be sent."""
from __future__ import annotations

import html
import json
import logging
import re
import subprocess
import time
from pathlib import Path

from openai import BadRequestError, OpenAI

from . import copilot, gpu_yield, usage
from .config import BASE_URL, LOCAL, MAX_STEPS, MODEL, NO_THINK, PLUGIN, TIMEOUT, ZHIPU
from .reply import ASKED_EVENTS, BUILD_NOTE, PROMISE, drop_promise, is_build_ask, scrub, shorten

log = logging.getLogger("c3bot.agent")
from .knowledge import get_plugin

kb = get_plugin()

MAX_CHECKS = 2
NO_STEPS = "这次没有完成核实，暂时不能给你可直接照做的步骤。"
NOT_SURE = "这个我没把握写对，先不给步骤，免得你照着做却在编辑器里找不到对应的条件或动作。"
NOT_MADE = "这个游戏这次没生成出来。把玩法说得再简单具体一点，再让我做一次。"
NOT_FINISHED = "这次没改完，项目保持原样。分几步来：先说要先改哪一部分。"
NO_FILE = "这次没有生成可交付的工程文件，尚未完成你要的例子。"


def add_system(messages: list[dict], text: str) -> None:
    """Add text to the system message; the message exists only once something is added to it."""
    if messages and messages[0]["role"] == "system":
        messages[0]["content"] += "\n\n" + text.strip()
    else:
        messages.insert(0, {"role": "system", "content": text.strip()})


class Run:
    """The state of one answer: the conversation, the tools the model has, the project it works on and whether
    that project goes out as a file after the reply."""

    def __init__(self, question: str, history: list[dict] | None, project: Path | None, group: bool,
                 session: Path | None, notify) -> None:
        self.question = question
        self.project = project  # a new project replaces the one passed in
        self.session = session
        self.notify = notify
        self.trace: list[str] = []
        self.send = False  # set by a written edit, an undo that leaves edits, send_project or a new project
        self.told = False  # the busy note went out, at the first tool call that makes or changes a project
        self.asked = project is not None or bool(ASKED_EVENTS.search(question))  # events may make the reply longer
        self.edits_before = kb.edits.edit_count(project) if project else 0
        if session is not None and is_build_ask(question, project is not None):
            question += BUILD_NOTE
            self.trace.append("build ask")
        self.messages = [*(history or []), {"role": "user", "content": question}]
        self.tools = list(kb.TOOLS)
        self.handlers = dict(kb.HANDLERS)
        self.steps = MAX_STEPS
        if group:
            add_system(self.messages, kb.GROUP_PROMPT)

    def changed(self, result: tuple[bool, str]) -> str:
        self.send = self.send or result[0]
        return result[1]

    def send_project(self) -> str:
        # a model that cannot make the change sent the untouched project and said it had (script-only, 2026-10-04)
        project = self.project
        if project and kb.is_new(project):
            self.send = True
            return "the project as it is now is sent as a file after the reply"
        if not (project and kb.edits.edit_count(project)):
            return ("not sent: nothing in the project was changed, so the file would be the one the person sent. "
                    "Do not say a file was sent. If they asked for a change you did not make, tell them in words "
                    "what to change and where.")
        self.send = True
        return "the project as it is now is sent as a file after the reply"

    def use_project(self, project: Path) -> None:
        """The project's own tools, bound to this project."""
        if kb.PROJECT_TOOLS[0]["function"]["name"] not in self.handlers:
            add_system(self.messages, kb.PROJECT_PROMPT)
            self.tools.extend(kb.PROJECT_TOOLS)
        self.handlers.update(kb.project_handlers(project, self.changed, self.send_project))

    def made(self, result: tuple[Path | None, str]) -> str:
        # a new project is the person's from here on: its tools replace the old project's, and it is sent
        if result[0]:
            self.project = result[0]
            self.send = True
            self.use_project(result[0])
        return result[1]

    def add_project(self) -> None:
        self.steps += kb.PROJECT_STEPS
        self.use_project(self.project)

    def add_session(self) -> None:
        """The tools that make a new project in the session folder."""
        add_system(self.messages, kb.session_prompt())
        tools, handlers, steps = kb.session_tools(self)
        self.tools.extend(tools)
        self.handlers.update(handlers)
        self.steps += steps


def json_error(name: str, exc: json.JSONDecodeError) -> str:
    """The tool result for a call whose arguments are not JSON: a long call breaks its JSON somewhere in the
    middle, and the position alone does not show where."""
    log.warning("tool %s failed: %s", name, exc)
    text = exc.doc or ""
    before = text[max(0, exc.pos - 120):exc.pos]
    stray = re.search(r'\}\s*,\s*"([^"]+)"\s*$', before)
    hint = (f'the key "{stray.group(1)}" stands outside any object: the object before it closed too '
            f'early, or it needs an object of its own; a block is one object {{"eventType": "block", '
            f'"conditions": [...], "actions": [...]}} and its comment the object before it' if stray else
            'count the brackets before this spot; a quote inside a string is written \\"')
    return (f"tool error: the call's arguments are not valid JSON: {exc.msg} at character {exc.pos}, "
            f"here: {before}<<HERE>>{text[exc.pos:exc.pos + 60]}. {hint}. Send the whole call again "
            "with that spot fixed")


class Agent:
    def __init__(self, api_key: str) -> None:
        # the free glm-4.7-flash answers 429 "访问量过大" to about 5 calls in 8 (2026-10-09); the SDK backs off and retries
        self.client = OpenAI(api_key=api_key, base_url=BASE_URL, max_retries=10 if ZHIPU else 2)
        create = self.client.chat.completions.create

        def counted(*args, **kwargs):
            # every model call of an answer, the tool loop's and the checks', adds to the thread's tally
            if LOCAL:  # the TTS server on the same GPU goes first (2026-10-09)
                gpu_yield.wait_for_tts(BASE_URL, MODEL)
            resp = create(*args, **kwargs)
            usage.count(resp)
            return resp

        self.client.chat.completions.create = counted

    def answer(
        self, question: str, history: list[dict] | None = None, project: Path | None = None, group: bool = False,
        outbox: list[Path] | None = None, session: Path | None = None, notify=None,
    ) -> tuple[str, list[str]]:
        """Run an answer under the same-session lock and record prepared attachments."""
        with copilot.session(project, session, group) as task:
            text, trace = self._answer_in_session(question, history, project, group, outbox, session, notify)
            failed = text in (NO_FILE, NOT_MADE, NOT_FINISHED, NOT_SURE, NO_STEPS) or any(
                t.startswith("pack failed:") or t == "steps ran out" for t in trace)
            task.finish(status="failed" if failed else "completed", summary=text, artifacts=outbox or [])
            return text, trace

    def _answer_in_session(
        self, question: str, history: list[dict] | None, project: Path | None, group: bool,
        outbox: list[Path] | None, session: Path | None, notify,
    ) -> tuple[str, list[str]]:
        tally = usage.begin()
        started = time.monotonic()
        run = Run(question, history, project, group, session, notify)
        text = ""
        try:
            text = self._answer(run)
            tried = any(t.startswith(kb.BUILD_TOOLS) for t in run.trace)
            made = run.send and kb.is_new(run.project)
            # a reply that describes a game and promises its file, with no build tried (quick mode, 2026-10-06)
            if (tried and (not made or "steps ran out" in run.trace)) or (session and not project and not made and PROMISE.search(text)):
                # the model said the game was made when every build had been refused (2026-10-04)
                text = NOT_MADE
                # a build that failed its play test sits unmarked in the session folder; an edit_sheet on it then
                # packed and sent it as "-edited" beside this text (2026-10-06)
                run.send = False
        finally:
            text = self._finish(run, text, outbox)
            usage.write_usage(session, tally, time.monotonic() - started)
            usage.end()
        if session and is_build_ask(question, project is not None) and not outbox:
            text = NO_FILE
            run.trace.append("requested file unavailable")
        if not run.send:
            text, dropped = drop_promise(text)
            if dropped:
                run.trace.append("promise of a file dropped")
        if outbox and run.project and kb.is_new(run.project) and not kb.runtime_verified(run.project):
            text += "\n工程通过结构检查，尚未在编辑器中验证运行。"
        text, note = scrub(text)
        if note:
            run.trace.append(note)
        return text, run.trace

    def _finish(self, run: Run, text: str, outbox: list[Path] | None) -> str:
        """Take back the edits of an answer that is not sent, and pack the project of one that is."""
        project, trace = run.project, run.trace
        if project and kb.is_new(project) and "steps ran out" in trace:
            run.send = False  # a game the answer did not finish is not sent as if it were
        elif project and "steps ran out" in trace and kb.edits.edit_count(project) > run.edits_before:
            # a change left half done (a sheet with one variable, 2026-10-06) is taken back, not sent
            while kb.edits.edit_count(project) > run.edits_before:
                kb.edits.undo(project)
            run.send = False
            text = NOT_FINISHED
            trace.append("unfinished edits undone")
        elif project and not run.send and kb.edits.edit_count(project) > run.edits_before:
            while kb.edits.edit_count(project) > run.edits_before:  # edits of a build that is not sent
                kb.edits.undo(project)
            trace.append("edits of an unsent build undone")
        if project and run.send and outbox is not None:
            try:
                outbox.append(kb.pack(project))
                trace.append(f"packed {outbox[-1].name}")
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                log.warning("pack failed: %s", exc)
                trace.append(f"pack failed: {exc}")
                run.send = False
                text = NO_FILE
        elif run.send:
            run.send = False
            text = NO_FILE
        return text

    def _presearch(self, run: Run) -> None:
        """The plugin's search before the model answers, put in as the model's own first tool call: a tool
        result steers a small model where a prompt rule did not."""
        found = kb.presearch(run.question, self._json)
        if isinstance(found, str):
            if found:
                run.trace.append(found)
            return
        words, out = found
        call = {"id": "presearch", "type": "function",
                "function": {"name": kb.PRESEARCH_TOOL, "arguments": json.dumps({"words": words})}}
        run.messages.append({"role": "assistant", "content": "", "tool_calls": [call]})
        run.messages.append({"role": "tool", "tool_call_id": "presearch", "content": out})
        run.trace.append(f"presearch {words}")

    def _answer(self, run: Run) -> str:
        """The tool loop: the model answers or calls tools until it answers, the steps run out or the check
        fails twice."""
        self._presearch(run)
        if run.project:
            run.add_project()
        if run.session:
            run.add_session()
        checks = 0
        for _ in range(run.steps + MAX_CHECKS):
            resp = self.client.chat.completions.create(
                model=MODEL,
                messages=run.messages,
                tools=run.tools,
                extra_body=NO_THINK,
                timeout=TIMEOUT,
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                text = html.unescape((msg.content or "").strip())
                missing = kb.check(run.messages, text, run.project, self._json)
                if not missing:
                    return self._final(run, text)
                if checks >= MAX_CHECKS:
                    run.trace.append(f"check: still missing {missing}")
                    return NOT_SURE
                checks += 1
                run.trace.append(f"check: missing {missing}")
                run.messages.append({"role": "assistant", "content": text})
                run.messages.append({"role": "user", "content": kb.CHECK_FAILED.format(missing="; ".join(missing))})
                continue
            run.messages.append(msg.model_dump(exclude_none=True))
            for call in msg.tool_calls:
                result = self._call(run, call)
                run.trace.append(kb.tool_trace(call.function.name, call.function.arguments, result))
                run.messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
        run.trace.append("steps ran out")
        return NO_STEPS

    def _final(self, run: Run, text: str) -> str:
        """The checked answer, shortened. A rewrite for length renames things (2026-10-09: 设置对象速率 came back
        as 设定对象时间速率), so a short version that fails the check is dropped for the checked long one."""
        short = shorten(self._complete, run.messages, text, run.trace, run.asked, sent=run.send)
        if short == text or not kb.check(run.messages, short, run.project, self._json):
            return short
        run.trace.append("short version failed the check; long one sent")
        return text

    def _call(self, run: Run, call) -> str:
        """Run one tool call of the model and return its result, or the error the model should read."""
        name = call.function.name
        try:
            try:
                args = json.loads(call.function.arguments or "{}")
                mended = ""
            except json.JSONDecodeError:
                fixed = kb.mend_arguments(name, call.function.arguments)
                if fixed is None:
                    raise
                args, mended = fixed
            if run.notify and not run.told and name in kb.BUSY:
                run.told = True
                run.notify(kb.BUSY[name])
            return mended + run.handlers[name](**args)
        except json.JSONDecodeError as exc:
            return json_error(name, exc)
        except (KeyError, TypeError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            log.warning("tool %s failed: %s", name, exc)
            return f"tool error: {exc}"

    def _complete(self, messages: list[dict]) -> str:
        """One plain model call; the content it answers."""
        resp = self.client.chat.completions.create(model=MODEL, messages=messages, extra_body=NO_THINK, timeout=TIMEOUT)
        return resp.choices[0].message.content or ""

    def _json(self, messages: list[dict]) -> dict:
        """One call that answers a JSON object. JSON mode where the model has it; Step-3.5-Flash on SiliconFlow
        refuses it ("Json mode is not supported", 2026-10-09), so then the object is cut out of plain text."""
        ask = dict(model=MODEL, messages=messages, extra_body=NO_THINK, timeout=TIMEOUT)
        try:
            resp = self.client.chat.completions.create(response_format={"type": "json_object"}, **ask)
        except BadRequestError:
            resp = self.client.chat.completions.create(**ask)
        text = resp.choices[0].message.content or ""
        return json.loads(text[text.find("{"):text.rfind("}") + 1] or "{}")
