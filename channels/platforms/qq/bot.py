"""QQ transport for any application with handle(request); __main__.py passes it in. What is not QQ's own (the
daily limit, history, session folders, the answer log) is channels/core/chat.py."""
from __future__ import annotations

import json
import asyncio
import logging
import re
from pathlib import Path
from types import SimpleNamespace

import aiohttp

from ...core import answers as answer_log
from ...core.chat import Chats, serialized_sessions
from ...core.receipt import GatewayReceipt
from . import files as qqfile

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("channels.qq")


class _Quiet(logging.Filter):
    """bot.log keeps the conversation and every warning: botpy's INFO (heartbeats, sessions) is already in
    botpy.log, and the model request lines are counted in usage.log."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.WARNING or not record.name.startswith(("botpy", "httpx"))


for _handler in logging.getLogger().handlers:
    _handler.addFilter(_Quiet())

CHUNK = 1500
MAX_REPLIES = 4  # a C2C message takes at most 4 passive replies, a group message 5
URL = re.compile(r"https?://\S+")
QUESTION_MAX = 500  # characters of a quoted message passed to the model


def chunks(text: str) -> list[str]:
    text = URL.sub("", text).strip() or "（没有内容）"
    parts = [text[i : i + CHUNK] for i in range(0, len(text), CHUNK)]
    return parts[:MAX_REPLIES]


def chat_of(key: str) -> str:
    return "private" if key.startswith("c2c:") else "group"


def run_qq(application, *, settings: dict, data_dir: Path, usage=None) -> None:
    """usage: the model client's token counter, which the answer log reads; None leaves the counts at 0."""
    log_dir = data_dir / "logs" / "bot"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_dir / "bot.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    handler.addFilter(_Quiet())
    logging.getLogger().addHandler(handler)
    import botpy
    from botpy.message import C2CMessage, GroupMessage

    gateway = GatewayReceipt(data_dir)
    chats = Chats(application, data_dir=data_dir, channel="qq", usage=usage, receipt=gateway)

    @serialized_sessions
    async def handle(key: str, question: str, reply, attachments=(), send_file=None) -> None:
        """send_file(path, msg_seq) sends a file as a reply to the same message."""
        if chats.acknowledged(key, question, attachments=attachments):
            return
        refusal = chats.admit(key, question)
        if refusal:
            await reply(content=refusal, msg_seq=1)
            return
        notes: list[str] = []  # the busy note sent while the answer is being made, a passive reply of its own
        loop = asyncio.get_running_loop()

        def notify(note: str) -> None:
            notes.append(note)
            log.info("%s note: %s", key, note)
            asyncio.run_coroutine_threadsafe(reply(content=note, msg_seq=len(notes)), loop)
        turn = await chats.ask(key, question, group=key.startswith("group:"), notify=notify, attachments=[
            {"filename": a.filename or "", "url": a.url or "", "content_type": a.content_type or "", "size": a.size or 0}
            for a in attachments])
        files = turn.files[:1] if send_file else []
        parts = chunks(turn.text)[: MAX_REPLIES - len(files) - len(notes)]  # the file and the note are replies to the same message too
        sent = set()
        try:
            for seq, part in enumerate(parts, start=len(notes) + 1):
                await reply(content=part, msg_seq=seq)
            for seq, path in enumerate(files, start=len(notes) + len(parts) + 1):
                try:
                    await send_file(path, seq)
                    sent.add(path)
                    log.info("%s sent file %s bytes", key, path.stat().st_size)
                except (OSError, aiohttp.ClientError, asyncio.TimeoutError, qqfile.UploadError) as exc:
                    log.warning("%s file send failed: %s", key, exc)
                    if seq < MAX_REPLIES:
                        await reply(content="文件未发送成功，请稍后重试。", msg_seq=seq + 1)
        except Exception as exc:  # botpy raises when QQ refuses a message (botpy/http.py _handle_response)
            log.warning("%s reply send failed: %r", key, exc)
        finally:
            # the answer is made and in the history, so its line with the model usage and tools is written too
            chats.record(turn, chat=chat_of(key), session=key, sent=sent,
                         files_in=[answer_log.file_fact(a.filename, a.size) for a in attachments])

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
        async def on_ready(self) -> None:
            gateway.ready()
            log.info("QQ gateway ready event received")

        def file_sender(self, scope: str, target: str, msg_id: str, key: str):
            auth = qqfile.token_auth(self.http._token)  # botpy's token, renewed as botpy renews it
            return lambda path, seq: qqfile.send_file(auth, scope, target, path, msg_id=msg_id, msg_seq=seq, chat=key)

        async def on_c2c_message_create(self, message: C2CMessage) -> None:
            openid = message.author.user_openid
            attachments, quoted = all_attachments(message)
            key = f"c2c:{openid}"
            await handle(key, with_quote(message.content, quoted), message.reply,
                         attachments, self.file_sender("c2c", openid, message.id, key))

        async def deliver_pending(self, message: GroupMessage) -> bool:
            """A text and a file left for a group in sessions/_pending/<group_openid>.json, sent as the reply to
            the next @ there and then deleted: the open platform refuses this bot's active group messages."""
            path = chats.sessions / "_pending" / f"{message.group_openid}.json"
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
            key = f"group:{message.group_openid}:{message.author.member_openid}"
            await handle(key, with_quote(message.content, quoted), message.reply,
                         attachments, self.file_sender("group", message.group_openid, message.id, key))

    # botpy's own log (botpy.log, rotated daily) goes beside bot.log instead of the working folder
    file_log = dict(botpy.logging.DEFAULT_FILE_HANDLER, filename=str(log_dir / "%(name)s.log"))
    client = Client(intents=botpy.Intents(public_messages=True), ext_handlers=file_log)
    gateway.starting()
    log.info("QQ gateway connection starting")
    client.run(appid=settings["QQ_APPID"], secret=settings["QQ_SECRET"])

