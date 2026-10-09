"""QQ bot front end for the Construct 3 answer agent.

    python bot.py                 connect to QQ over WebSocket (needs QQ_APPID, QQ_SECRET)
    python bot.py --cli "问题"     ask once in the terminal, print the reply and the tool calls
"""
from __future__ import annotations

import argparse
import hashlib
import json
import asyncio
import io
import logging
import os
import re
import shutil
import zipfile
from collections import defaultdict, deque
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import aiohttp
from dotenv import load_dotenv

import xml.etree.ElementTree as ET

import attachments as attachments_mod
import edits
import qqfile

# before agent.py, which reads C3BOT_BASE_URL and C3BOT_MODEL when it is imported (2026-10-06: the .env
# switch to a local model was read too late and the bot kept calling DeepSeek)
load_dotenv(Path(__file__).parent / ".env")
from agent import Agent  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("c3bot")


class _Quiet(logging.Filter):
    """bot.log keeps the conversation and every warning: botpy's INFO (heartbeats, sessions) is already in
    botpy.log, and the model request lines are counted in usage.log."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.WARNING or not record.name.startswith(("botpy", "httpx"))


for _handler in logging.getLogger().handlers:
    _handler.addFilter(_Quiet())

CHUNK = 1500
MAX_REPLIES = 4  # a C2C message takes at most 4 passive replies, a group message 5
HISTORY_TURNS = 3
URL = re.compile(r"https?://\S+")
QUESTION_MAX = 500  # characters passed to the model
DAILY_LIMIT = 30  # questions per user per day
SESSIONS = Path(__file__).parent / "sessions"
DOWNLOAD_MAX = 30 * 1024 * 1024  # bytes of one .c3p
UNPACK_MAX = 200 * 1024 * 1024  # bytes of its unpacked files


def safe_name(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", key)


def unpack_project(url: str, filename: str, key: str) -> tuple[Path | None, str]:
    """Download a .c3p, .zip or .capx. A Construct 3 project (a zip of the folder project) is unpacked and its
    folder returned; a Construct 2 project comes back as its printed events for the question instead."""
    data = attachments_mod.download(url, DOWNLOAD_MAX)
    log.info("project file md5 %s, %s bytes", hashlib.md5(data).hexdigest(), len(data))
    if Path(filename).suffix.lower() in attachments_mod.OTHER_ARCHIVES:
        data = attachments_mod.as_zip(data, filename, UNPACK_MAX)
    return load_archive(data, filename, key)


def load_archive(data: bytes, filename: str, key: str, depth: int = 0) -> tuple[Path | None, str]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = [i.filename.replace("\\", "/") for i in zf.infolist()]
        if any(n.rsplit("/", 1)[-1] == "project.c3proj" for n in names):
            if sum(i.file_size for i in zf.infolist()) > UNPACK_MAX:
                raise ValueError("项目解压后超过 200 MB")
            target = SESSIONS / safe_name(key)
            if target.exists():
                shutil.rmtree(target)
            target.mkdir(parents=True)
            for info in zf.infolist():
                dest = (target / info.filename).resolve()
                if not dest.is_relative_to(target.resolve()):
                    raise ValueError(f"压缩包里有不安全的路径：{info.filename}")
            zf.extractall(target)
            return next(target.rglob("project.c3proj")).parent, ""
        if any(n.lower().endswith(".caproj") for n in names):
            return None, attachments_mod.capx_block(filename, zf)
        inner = attachments_mod.nested_project(zf) if depth == 0 else None
        if inner:  # a zip of several projects: read the first
            count = sum(Path(n).suffix.lower() in (".c3p", ".capx") for n in names)
            project, extra = load_archive(zf.read(inner), Path(inner).name, key, depth + 1)
            note = (f"\n\n({filename} holds {count} projects; this is the first, {Path(inner).name}. "
                    "Ask for another one sent on its own.)") if count > 1 else ""
            return project, extra + note
    raise ValueError(f"{filename} 里没有 Construct 3 项目（project.c3proj）或 Construct 2 项目（.capx）")


def chunks(text: str) -> list[str]:
    text = URL.sub("", text).strip() or "（没有内容）"
    parts = [text[i : i + CHUNK] for i in range(0, len(text), CHUNK)]
    return parts[:MAX_REPLIES]


def run_qq(agent: Agent) -> None:
    import botpy
    from botpy.message import C2CMessage, GroupMessage

    history: dict[str, deque] = defaultdict(lambda: deque(maxlen=HISTORY_TURNS * 2))
    usage: dict[tuple[str, date], int] = defaultdict(int)
    projects: dict[str, Path] = {}

    async def handle(key: str, question: str, reply, attachments=(), send_file=None) -> None:
        """send_file(path, msg_seq) sends a file as a reply to the same message."""
        log.info("%s asks: %s", key, question)
        extra = ""  # file contents the model reads after the question
        sent = None  # what was attached, for the question asked when the message has no text
        unread = []  # suffixes of attachments the bot cannot read (images, video, PDF)
        for att in attachments:
            # the log keeps a digest of the name, not the name: users send receipts and other private files
            suffix = Path(att.filename or "").suffix.lower()
            log.info("attachment: name-md5 %s, %s, %s bytes, %s", hashlib.md5((att.filename or "").encode()).hexdigest(),
                     att.content_type, att.size, suffix)
            if not att.url:
                continue
            if suffix in attachments_mod.PROJECT_SUFFIXES:
                try:
                    project, more = await asyncio.to_thread(unpack_project, att.url, att.filename, key)
                except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError) as exc:
                    log.warning("project unpack failed: %s", exc)
                    await reply(content=f"项目文件打不开：{exc}", msg_seq=1)
                    return
                history[key].clear()
                if project:
                    projects[key] = project
                    edits.reset(project)  # the edits of an earlier upload do not apply to this one
                    log.info("project for %s: %s", key, project)
                else:  # a Construct 2 project replaces the session's project too
                    projects.pop(key, None)
                    if (SESSIONS / safe_name(key)).exists():
                        shutil.rmtree(SESSIONS / safe_name(key))
                    log.info("capx for %s: %d characters of events", key, len(more))
                extra += more
                sent = "项目"
            elif suffix in attachments_mod.TEXT_SUFFIXES:
                try:
                    data = await asyncio.to_thread(attachments_mod.download, att.url, attachments_mod.TEXT_MAX)
                except (OSError, ValueError) as exc:
                    log.warning("text file download failed: %s", exc)
                    await reply(content=f"文件打不开：{exc}", msg_seq=1)
                    return
                log.info("text file: %s bytes", len(data))
                extra += attachments_mod.text_block(att.filename, data)
                sent = sent or "文件"
            else:
                unread.append(suffix or "无扩展名")
        if unread and question:
            # without the note the model answered "没看懂" to a question about a file it never saw (2026-10-04)
            question += (f"\n(This message also came with a {', '.join(unread)} file that you cannot read: only "
                         "Construct 3 projects and text files reach you. Say so in one sentence if the question "
                         "is about that file.)")
        elif sent is None and question and (key in projects or (SESSIONS / safe_name(key)).is_dir()):
            # a project sent earlier pulled a general question into its scripts (2026-10-04)
            # the first wording ended the answer with an offer to apply it if the person sent the .c3p again
            question += ("\n(The project sent earlier is still open, so never ask for its file. If this message is "
                         "not about that project, answer it as a general question with search_guides, not from its "
                         "scripts, or make the example it asks for with the project tools; end with the answer: "
                         "no offer to apply it to the project, and "
                         "not a word about the project or this note.)")
        if sent and not question:
            # an open question about a sent project made the model invent problems to fix (2026-10-04)
            question = "我发来了项目，说说它做了什么。" if sent == "项目" else "我发来了文件，说说它是什么。"
        elif sent:
            question = f"{question}（随这条消息发来了{sent}）"
        if not question:
            await reply(content=("能看 Construct 3 项目（.c3p，或文件夹压成 .zip、.rar、.7z）、Construct 2 项目（.capx）和文本文件"
                                 "（.txt、.md、.js、.ts、.json 等）。" if attachments
                                 else "有 Construct 3 的问题直接问；要看项目，就发 .c3p 文件。"), msg_seq=1)
            return
        usage[(key, date.today())] += 1
        if usage[(key, date.today())] > DAILY_LIMIT:
            log.info("daily limit reached for %s", key)
            await reply(content=f"今天的 {DAILY_LIMIT} 个问题已经用完，明天再来。", msg_seq=1)
            return
        question = question[:QUESTION_MAX] + extra
        outbox: list[Path] = []  # files the answer sends after its text
        notes: list[str] = []  # the busy note sent while the answer is being made, a passive reply of its own
        loop = asyncio.get_running_loop()

        def notify(note: str) -> None:
            notes.append(note)
            log.info("note: %s", note)
            asyncio.run_coroutine_threadsafe(reply(content=note, msg_seq=len(notes)), loop)
        try:
            if key not in projects:  # a project sent before a restart is still on disk
                saved = next((SESSIONS / safe_name(key)).rglob("project.c3proj"), None) if (SESSIONS / safe_name(key)).is_dir() else None
                if saved:
                    projects[key] = saved.parent
            text, trace = await asyncio.to_thread(
                agent.answer, question, list(history[key]), projects.get(key), key.startswith("group:"), outbox,
                SESSIONS / safe_name(key), notify,
            )
            made = next((SESSIONS / safe_name(key)).rglob("project.c3proj"), None) if (SESSIONS / safe_name(key)).is_dir() else None
            if made:  # a project the answer made replaces the session's
                projects[key] = made.parent
        except Exception:  # the reply must still go out
            log.exception("agent failed")
            # a build finished before the failure is packed in outbox and still goes (2026-10-06: a 402 after a build)
            text, trace = ("后面出了错，做好的部分先发你。" if outbox else "出错了，稍后再试。"), []
        log.info("%s tools: %s", key, trace)
        log.info("%s reply: %s", key, text.replace("\n", " / "))
        history[key].extend([{"role": "user", "content": question}, {"role": "assistant", "content": text}])
        files = outbox[:1] if send_file else []
        parts = chunks(text)[: MAX_REPLIES - len(files) - len(notes)]  # the file and the note are replies to the same message too
        for seq, part in enumerate(parts, start=len(notes) + 1):
            await reply(content=part, msg_seq=seq)
        for seq, path in enumerate(files, start=len(notes) + len(parts) + 1):
            try:
                await send_file(path, seq)
                log.info("sent file %s bytes", path.stat().st_size)
            except (OSError, aiohttp.ClientError, asyncio.TimeoutError, qqfile.UploadError) as exc:
                log.warning("file send failed: %s", exc)
                if seq < MAX_REPLIES:
                    await reply(content="改好的项目文件没发出去，稍后说一声“发回来”再试。", msg_seq=seq + 1)

    # botpy 1.2 drops msg_elements, where a quoted message (message_type 103) carries its content and files,
    # so keep each event's raw payload by message id
    from botpy.connection import ConnectionState
    raw: dict[str, dict] = {}
    for name in ("parse_group_at_message_create", "parse_c2c_message_create"):
        original = getattr(ConnectionState, name)
        def keep(self, payload, original=original):
            d = payload.get("d", {})
            raw[d.get("id")] = d
            return original(self, payload)
        setattr(ConnectionState, name, keep)

    def all_attachments(message) -> tuple[list, str]:
        """The message's own attachments and those of a message it quotes, and the quoted message's text."""
        found = list(message.attachments)
        quoted: list[str] = []
        d = raw.pop(message.id, {})
        elements = d.get("msg_elements") or []
        if d.get("message_type") == 103 or elements:
            log.info("quoted message: type %s, %d elements, keys %s", d.get("message_type"), len(elements),
                     sorted({k for e in elements if isinstance(e, dict) for k in e}))
        stack = list(elements)  # MsgElement nests msg_elements of its own
        while stack:
            element = stack.pop()
            if not isinstance(element, dict):
                continue
            stack.extend(element.get("msg_elements") or [])
            if "content" in element:
                log.info("quoted content: %s %r", type(element["content"]).__name__, str(element["content"])[:80])
            if isinstance(element.get("content"), str) and element["content"].strip():
                quoted.append(element["content"].strip())
            for att in element.get("attachments") or []:
                found.append(SimpleNamespace(filename=att.get("filename"), url=att.get("url"),
                                             content_type=att.get("content_type"), size=att.get("size")))
        return found, "\n".join(quoted)[:QUESTION_MAX]

    def with_quote(content: str, quoted: str) -> str:
        """The question with the text of the message it replies to, which "做这个例子" points at (2026-10-06)."""
        content = (content or "").strip()
        return f"{content}\n（引用的消息：{quoted}）" if quoted else content

    class Client(botpy.Client):
        def file_sender(self, scope: str, target: str, msg_id: str):
            auth = qqfile.token_auth(self.http._token)  # botpy's token, renewed as botpy renews it
            return lambda path, seq: qqfile.send_file(auth, scope, target, path, msg_id=msg_id, msg_seq=seq)

        async def on_c2c_message_create(self, message: C2CMessage) -> None:
            openid = message.author.user_openid
            attachments, quoted = all_attachments(message)
            await handle(f"c2c:{openid}", with_quote(message.content, quoted), message.reply,
                         attachments, self.file_sender("c2c", openid, message.id))

        async def deliver_pending(self, message: GroupMessage) -> bool:
            """A text and a file left for a group in sessions/_pending/<group_openid>.json, sent as the reply to
            the next @ there and then deleted: the open platform refuses this bot's active group messages."""
            path = SESSIONS / "_pending" / f"{message.group_openid}.json"
            if not path.is_file():
                return False
            pending = json.loads(path.read_text(encoding="utf-8"))
            path.unlink()
            log.info("group:%s pending delivery of %s", message.group_openid, pending.get("name"))
            await message.reply(content=pending["text"], msg_seq=1)
            auth = qqfile.token_auth(self.http._token)
            await qqfile.send_file(auth, "group", message.group_openid, Path(pending["file"]), pending.get("name"),
                                   msg_id=message.id, msg_seq=2)
            return True

        async def on_group_at_message_create(self, message: GroupMessage) -> None:
            if await self.deliver_pending(message):
                return
            attachments, quoted = all_attachments(message)
            await handle(
                f"group:{message.group_openid}:{message.author.member_openid}",
                with_quote(message.content, quoted),
                message.reply,
                attachments,
                self.file_sender("group", message.group_openid, message.id),
            )

    # botpy's own log (botpy.log, rotated daily) goes beside bot.log instead of the working folder
    file_log = dict(botpy.logging.DEFAULT_FILE_HANDLER, filename=str(Path(__file__).parent / "logs" / "bot" / "%(name)s.log"))
    client = Client(intents=botpy.Intents(public_messages=True), ext_handlers=file_log)
    client.run(appid=os.environ["QQ_APPID"], secret=os.environ["QQ_SECRET"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", metavar="QUESTION", help="ask once in the terminal instead of connecting to QQ")
    parser.add_argument("--project", type=Path, help="with --cli: the folder that holds project.c3proj")
    parser.add_argument("--session", type=Path, help="with --cli: the folder a new project is made in (default sessions/cli)")
    args = parser.parse_args()
    key = (os.environ.get("SILICONFLOW_API_KEY") or os.environ.get("SILICONFLOW_KEY")) if "siliconflow" in os.environ.get("C3BOT_BASE_URL", "") else None
    if "bigmodel.cn" in os.environ.get("C3BOT_BASE_URL", ""):
        key = os.environ.get("ZHIPU_API_KEY")
    agent = Agent(os.environ.get("C3BOT_API_KEY") or key or os.environ["DEEPSEEK_API_KEY"])
    if args.cli:
        outbox: list[Path] = []
        text, trace = agent.answer(args.cli, project=args.project, outbox=outbox,
                                   session=args.session or SESSIONS / "cli", notify=lambda n: print(f"[note] {n}"))
        print("\n".join(f"[tool] {t}" for t in trace))
        print("---")
        print("\n=====\n".join(chunks(text)))
        for path in outbox:
            print(f"[file] {path}")
    else:
        run_qq(agent)


if __name__ == "__main__":
    main()
