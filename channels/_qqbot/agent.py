"""Construct 3 answer agent: DeepSeek with two lookup tools over a Construct3-RAG clone."""
from __future__ import annotations

import html
import json
import logging
import re
import subprocess
import threading
import time
from pathlib import Path

from openai import BadRequestError, OpenAI

import edits
import gpu_yield
import newproject
from config import BASE_URL, LOCAL, LOCALE, MAX_STEPS, MODEL, NO_THINK, RAG, TIMEOUT, ZHIPU
from acecheck import LIST_ACES, missing_aces, project_text
from reply import ASKED_EVENTS, BUILD_NOTE, PROMISE, drop_promise, is_build_ask, scrub, shorten
from tools import GROUP_PROMPT, HANDLERS, PROJECT_PROMPT, PROJECT_TOOLS, TOOLS, project_handlers, run_script

log = logging.getLogger("c3bot.agent")

def add_system(messages: list[dict], text: str) -> None:
    """Add text to the system message; the message exists only once something is added to it."""
    if messages and messages[0]["role"] == "system":
        messages[0]["content"] += "\n\n" + text.strip()
    else:
        messages.insert(0, {"role": "system", "content": text.strip()})


MAX_CHECKS = 2
# the note sent before the reply when a tool starts to make or change a project, so the person knows the bot is
# busy and not stuck (2026-10-06); a making run takes two to four minutes, an edit about one
BUSY = {"design_guide": "在做了，要两三分钟，做好发你。", "check_design": "在做了，要两三分钟，做好发你。",
        "new_project_from_spec": "在做了，要两三分钟，做好发你。", "new_project_from_template": "在做了，做好发你。",
        "edit_sheet": "在改了，改好发你。"}
PRESEARCH_MIN = 8  # characters; "在吗" or "做好了吗" asks nothing to search for
PRESEARCH = (
    "A Construct 3 user asks:\n{question}\n\nGive 2 to 5 short English search words for the Construct 3 features "
    "and the problem in this question (e.g. time scale, pause, animation, touch, layer). "
    'Reply with JSON only: {{"words": ["...", "..."]}}'
)


USAGE_LOG = Path(__file__).parent / "logs" / "bot" / "usage.log"  # one line an answer, QQ and --cli alike
_tally = threading.local()  # the token count of the answer this thread is giving


def write_usage(session: Path | None, tally: dict, seconds: float) -> None:
    """Terminal runs (--cli, specs/e2e.py) do not write bot.log, so every answer also goes to usage.log."""
    line = (f"{session.name if session else '-'} calls {tally['calls']} prompt {tally['prompt']} "
            f"(cache hit {tally['cache_hit']}) completion {tally['completion']} in {seconds:.0f} s")
    log.info("usage: %s", line)
    try:
        with USAGE_LOG.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}\n")
    except OSError as exc:
        log.warning("usage.log not written: %s", exc)


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
            tally, usage = getattr(_tally, "now", None), getattr(resp, "usage", None)
            if tally is not None and usage is not None:
                tally["calls"] += 1
                tally["prompt"] += usage.prompt_tokens or 0
                tally["completion"] += usage.completion_tokens or 0
                tally["cache_hit"] += getattr(usage, "prompt_cache_hit_tokens", 0) or 0
            return resp

        self.client.chat.completions.create = counted

    def answer(
        self, question: str, history: list[dict] | None = None, project: Path | None = None, group: bool = False,
        outbox: list[Path] | None = None, session: Path | None = None, notify=None,
    ) -> tuple[str, list[str]]:
        """Return the reply and a trace of tool calls. With a project, its sheets and checker are tools too,
        and a project the answer changed, or was asked to send, is packed into outbox to go after the reply.
        With a session folder, a new project can be made there; it replaces the project and is sent."""
        trace: list[str] = []
        _tally.now = {"calls": 0, "prompt": 0, "completion": 0, "cache_hit": 0}
        started = time.monotonic()
        send = {"project": False}  # set by a written edit, an undo that leaves edits, send_project or a new project
        current = {"project": project}  # a new project replaces the one passed in
        edits_before = edits.edit_count(project) if project else 0

        def changed(result: tuple[bool, str]) -> str:
            send["project"] = send["project"] or result[0]
            return result[1]

        def send_project() -> str:
            # a model that cannot make the change sent the untouched project and said it had (script-only, 2026-10-04)
            project = current["project"]
            if project and newproject.is_new(project):
                send["project"] = True
                return "the project as it is now is sent as a file after the reply"
            if not (project and edits.edit_count(project)):
                return ("not sent: nothing in the project was changed, so the file would be the one the person sent. "
                        "Do not say a file was sent. If they asked for a change you did not make, tell them in words "
                        "what to change and where.")
            send["project"] = True
            return "the project as it is now is sent as a file after the reply"

        try:
            text = self._answer(question, history, project, group, trace, changed, send_project, session, current, send,
                                notify)
            tried = any(t.startswith(("new_project_from_", "check_design", "patch_spec")) for t in trace)
            made = send["project"] and newproject.is_new(current["project"])
            # a reply that describes a game and promises its file, with no build tried (quick mode, 2026-10-06)
            if (tried and (not made or "steps ran out" in trace)) or (session and not project and not made and PROMISE.search(text)):
                # the model said the game was made when every build had been refused (2026-10-04)
                text = "这个游戏这次没生成出来。把玩法说得再简单具体一点，再让我做一次。"
                # a build that failed its play test sits unmarked in the session folder; an edit_sheet on it then
                # packed and sent it as "-edited" beside this text (2026-10-06)
                send["project"] = False
        finally:
            project = current["project"]
            if project and newproject.is_new(project) and "steps ran out" in trace:
                send["project"] = False  # a game the answer did not finish is not sent as if it were
            elif project and "steps ran out" in trace and edits.edit_count(project) > edits_before:
                # a change left half done (a sheet with one variable, 2026-10-06) is taken back, not sent
                while edits.edit_count(project) > edits_before:
                    edits.undo(project)
                send["project"] = False
                text = "这次没改完，项目保持原样。分几步来：先说要先改哪一部分。"
                trace.append("unfinished edits undone")
            elif project and not send["project"] and edits.edit_count(project) > edits_before:
                while edits.edit_count(project) > edits_before:  # edits of a build that is not sent
                    edits.undo(project)
                trace.append("edits of an unsent build undone")
            if project and send["project"] and outbox is not None:
                try:
                    outbox.append(newproject.pack(project, RAG) if newproject.is_new(project) else edits.pack(project, RAG))
                    trace.append(f"packed {outbox[-1].name}")
                except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                    log.warning("pack failed: %s", exc)
                    trace.append(f"pack failed: {exc}")
            write_usage(session, _tally.now, time.monotonic() - started)
            _tally.now = None
        if session and is_build_ask(question, project is not None) and not outbox:
            text = "这次没有生成可交付的工程文件，尚未完成你要的例子。"
            trace.append("requested file unavailable")
        if not send["project"]:
            text, dropped = drop_promise(text)
            if dropped:
                trace.append("promise of a file dropped")
        text, note = scrub(text)
        if note:
            trace.append(note)
        return text, trace

    def _presearch(self, messages: list[dict], question: str, trace: list[str]) -> None:
        """Search the pitfalls before the model answers and put the result in as its own search_guides call.

        2026-10-09: asked how to pause a battle while an ultimate animation plays, the model guessed ACE names three
        times and gave up without one search, though wait-and-time-scale.md holds the answer; a tool result steers
        a small model where the prompt's "call it for every how-to question" did not."""
        if len(question) < PRESEARCH_MIN:
            return
        try:
            found = self._json([{"role": "user", "content": PRESEARCH.format(question=question[:1000])}])
            words = [str(w) for w in found.get("words", [])][:6]
        except (json.JSONDecodeError, AttributeError, TypeError) as e:
            trace.append(f"presearch: no words ({type(e).__name__})")
            return
        if not words:
            trace.append("presearch: no words")
            return
        try:
            out = run_script("search_guides", [*words, "--examples", "0", "--pitfalls", "3"], limit=5000)
        except subprocess.TimeoutExpired:
            trace.append("presearch: search timed out")
            return
        call = {"id": "presearch", "type": "function",
                "function": {"name": "search_guides", "arguments": json.dumps({"words": words})}}
        messages.append({"role": "assistant", "content": "", "tool_calls": [call]})
        messages.append({"role": "tool", "tool_call_id": "presearch", "content": out})
        trace.append(f"presearch {words}")

    def _answer(self, question, history, project, group, trace, changed, send_project, session=None, current=None,
                send=None, notify=None) -> str:
        told = []  # the note sent once, at the first tool call that makes or changes a project
        asked = project is not None or bool(ASKED_EVENTS.search(question))  # events may make the reply longer
        if session is not None and is_build_ask(question, project is not None):
            question += BUILD_NOTE
            trace.append("build ask")
        tools = list(TOOLS)
        handlers = dict(HANDLERS)
        steps = MAX_STEPS
        messages = [*(history or []), {"role": "user", "content": question}]
        if group:
            add_system(messages, GROUP_PROMPT)
        self._presearch(messages, question, trace)

        def use_project(project: Path) -> None:
            if "print_sheet" not in handlers:
                add_system(messages, PROJECT_PROMPT)
                tools.extend(PROJECT_TOOLS)
            handlers.update(project_handlers(project, changed, send_project))

        def made(result: tuple[Path | None, str]) -> str:
            # a new project is the person's from here on: its tools replace the old project's, and it is sent
            if result[0]:
                current["project"] = result[0]
                send["project"] = True
                use_project(result[0])
            return result[1]

        if project:
            steps += 6  # a change reads the sheet, looks its ACEs up and may send a plan twice
            use_project(project)
        if session:
            add_system(messages, newproject.prompt())
            tools.extend(newproject.QUICK_TOOLS if newproject.QUICK else newproject.TOOLS)
            # a new game reads an example, sends its design two or three times, looks up a dozen ACEs and may send
            # its spec three times
            steps += 20 if newproject.QUICK else 48
            handlers["spec_guide"] = lambda: newproject.QUICK_GUIDE if newproject.QUICK else newproject.SPEC_GUIDE
            handlers["read_example"] = lambda id: newproject.read_example(
                id, RAG, LOCALE, sum(t.startswith("read_example") for t in trace))
            handlers["design_guide"] = lambda: newproject.design_guide(RAG)
            handlers["check_design"] = lambda design=None, arguments=None: newproject.check_design(
                design if design is not None else newproject.unwrap(arguments, "design"), session, RAG,
                any(t.startswith("read_example") for t in trace))
            # after a JSON error the model sometimes wraps the whole call in {"arguments": "<the call as a string>"}
            # keys of the spec sent beside it ("viewport", 2026-10-04) go into it
            handlers["new_project_from_spec"] = lambda spec=None, arguments=None, **rest: made(newproject.from_spec(
                newproject.gather(spec if spec is not None or rest else newproject.unwrap(arguments), rest),
                session, RAG, LOCALE))
            handlers["patch_spec"] = lambda changes=None, arguments=None: made(newproject.patch_spec(
                changes if changes is not None else newproject.unwrap(arguments, "changes"), session, RAG, LOCALE))
            handlers["new_project_from_template"] = lambda template_id, name: made(
                newproject.from_template(template_id, name, session, RAG, LOCALE))
        checks = 0
        draft = ''  # the last answer written, sent when the steps run out
        for _ in range(steps + MAX_CHECKS):
            resp = self.client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools,
                extra_body=NO_THINK,
                timeout=TIMEOUT,
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                # check the model's own answer, then shorten it: a rewrite for length renames ACEs
                # (2026-10-09: 设置对象速率 came back as 设定对象时间速率), so a short version that fails the
                # check is dropped for the checked long one
                text = html.unescape((msg.content or "").strip())
                draft = text
                missing = self._check(messages, text, project)
                if not missing:
                    short = shorten(self._complete, messages, text, trace, asked, sent=bool(send and send["project"]))
                    if short == text or not self._check(messages, short, project):
                        return short
                    trace.append("short version failed the check; long one sent")
                    return text
                if checks >= MAX_CHECKS:
                    trace.append(f"check: still missing {missing}")
                    return "这个我没把握写对，先不给步骤，免得你照着做却在编辑器里找不到对应的条件或动作。"
                checks += 1
                trace.append(f"check: missing {missing}")
                messages.append({"role": "assistant", "content": text})
                messages.append({
                    "role": "user",
                    "content": (
                        "Check failed: "
                        + "; ".join(missing)
                        + ". A name the schema lacks may not exist, or may belong to another plugin or behavior. "
                        "Look each one up "
                        "with lookup_ace, then rewrite the whole answer for the user using only ACEs the lookups "
                        "printed. Do not mention this check."
                    ),
                })
                continue
            messages.append(msg.model_dump(exclude_none=True))
            for call in msg.tool_calls:
                try:
                    try:
                        args = json.loads(call.function.arguments or "{}")
                        mended = ""
                    except json.JSONDecodeError:
                        if not call.function.name.startswith(("new_project", "check_design", "patch_spec")):
                            raise
                        # a spec breaks its brackets far from where the parser notices; put them in order and let
                        # the build check what the spec now says
                        args = json.loads(newproject.mend(newproject.balance(call.function.arguments)))
                        mended = ("-- the call's JSON had brackets out of order; they were closed where the next "
                                  "closer showed a list or object had ended. Check the build below as usual\n")
                    if notify and not told and call.function.name in BUSY:
                        told.append(call.function.name)
                        notify(BUSY[call.function.name])
                    result = handlers[call.function.name](**args)
                    result = mended + result if mended else result
                except json.JSONDecodeError as exc:
                    # a long call breaks its JSON somewhere in the middle; the position alone does not show where
                    log.warning("tool %s failed: %s", call.function.name, exc)
                    text = exc.doc or ""
                    before = text[max(0, exc.pos - 120):exc.pos]
                    stray = re.search(r'\}\s*,\s*"([^"]+)"\s*$', before)
                    hint = (f'the key "{stray.group(1)}" stands outside any object: the object before it closed too '
                            f'early, or it needs an object of its own; a block is one object {{"eventType": "block", '
                            f'"conditions": [...], "actions": [...]}} and its comment the object before it' if stray else
                            'count the brackets before this spot; a quote inside a string is written \\"')
                    result = (f"tool error: the call's arguments are not valid JSON: {exc.msg} at character {exc.pos}, "
                              f"here: {before}<<HERE>>{text[exc.pos:exc.pos + 60]}. {hint}. Send the whole call again "
                              "with that spot fixed")
                except (KeyError, TypeError, OSError, subprocess.TimeoutExpired) as exc:
                    log.warning("tool %s failed: %s", call.function.name, exc)
                    result = f"tool error: {exc}"
                trace.append(f"{call.function.name}({call.function.arguments})"
                             # the log keeps what an edit did, to find refusals that do not steer the model
                             + (f" -> {result.splitlines()[0][:200]}" if call.function.name in ("edit_sheet", "undo_edit") else "")
                             + (f" -> {' / '.join(result.splitlines()[:4])[:600]}" if call.function.name.startswith(("new_project", "patch_spec")) else "")
                             + (f" -> {' / '.join(l for l in result.splitlines() if l.startswith(('tests[', 'rules', 'state', 'inputs', 'design', 'ok:', 'refused', 'win', 'lose', 'reference', 'screen')))[:900]}"
                                if call.function.name == "check_design" else ""))
                messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
        trace.append("steps ran out")
        return "这次没有完成核实，暂时不能给你可直接照做的步骤。"

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

    def _check(self, messages: list[dict], text: str, project: Path | None = None) -> list[str]:
        try:
            aces = self._json([*messages, {"role": "assistant", "content": text},
                               {"role": "user", "content": LIST_ACES}]).get("aces", [])
        except (json.JSONDecodeError, AttributeError) as exc:
            log.warning("ACE list unreadable: %s", exc)
            return ["ACE validation result unreadable"]
        if not isinstance(aces, list):
            return ["ACE validation result must be a list"]
        return missing_aces(aces, project, project_text(messages))
