"""Handle Construct requests independently of their message transport."""
from pathlib import Path
from types import SimpleNamespace
import base64
import copy
import hashlib
import io
import json
import logging
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET

from . import attachments as attachments_mod, plugin as kb
from .agent import Agent
from .record import DESCRIPTION

log = logging.getLogger("copilot.construct3")
DOWNLOAD_MAX = 30 * 1024 * 1024
UNPACK_MAX = 200 * 1024 * 1024
QUESTION_MAX = 500
EARLIER_IMAGE_TURNS = 3  # the questions after an image it still goes with, as many turns as the chat history keeps

def unpack_project(url: str, filename: str, target: Path) -> tuple[Path | None, str]:
    """Download a .c3p, .zip or .capx. A Construct 3 project (a zip of the folder project) is unpacked and its
    folder returned; a Construct 2 project comes back as its printed events for the question instead."""
    data = attachments_mod.download(url, DOWNLOAD_MAX)
    log.info("project file md5 %s, %s bytes", hashlib.md5(data).hexdigest(), len(data))
    if Path(filename).suffix.lower() in attachments_mod.OTHER_ARCHIVES:
        data = attachments_mod.as_zip(data, filename, UNPACK_MAX)
    return load_archive(data, filename, target)


def load_archive(data: bytes, filename: str, target: Path, depth: int = 0) -> tuple[Path | None, str]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = [i.filename.replace("\\", "/") for i in zf.infolist()]
        if any(n.rsplit("/", 1)[-1] == "project.c3proj" for n in names):
            if sum(i.file_size for i in zf.infolist()) > UNPACK_MAX:
                raise attachments_mod.Unreadable("项目解压后超过 200 MB")
            for info in zf.infolist():
                dest = (target / info.filename).resolve()
                if not dest.is_relative_to(target.resolve()):
                    raise attachments_mod.Unreadable(f"压缩包里有不安全的路径：{info.filename}")
            if target.exists():
                shutil.rmtree(target)
            target.mkdir(parents=True)
            zf.extractall(target)
            return next(target.rglob("project.c3proj")).parent, ""
        if any(n.lower().endswith(".caproj") for n in names):
            return None, attachments_mod.capx_block(filename, zf)
        inner = attachments_mod.nested_project(zf) if depth == 0 else None
        if inner:  # a zip of several projects: read the first
            count = sum(Path(n).suffix.lower() in (".c3p", ".capx") for n in names)
            project, extra = load_archive(zf.read(inner), Path(inner).name, target, depth + 1)
            note = (f"\n\n({filename} holds {count} projects; this is the first, {Path(inner).name}. "
                    "Ask for another one sent on its own.)") if count > 1 else ""
            return project, extra + note
    raise attachments_mod.Unreadable(f"{filename} 里没有 Construct 3 项目（project.c3proj）或 Construct 2 项目（.capx）")



class Application:
    def __init__(self, client, *, model, request_options=None, timeout=120, project_options=None,
                 project_timeout=None, usage=None, bad_request_error=(), vision=False):
        """vision: the model reads images, which then reach it with the question instead of a note."""
        self.agent = Agent(client, model=model, request_options=request_options, timeout=timeout,
                           project_options=project_options, project_timeout=project_timeout, usage=usage,
                           bad_request_error=bad_request_error)
        self.vision = vision
        self.projects = {}

    def describe(self):
        """The fields this application adds to an answer's record (handle's "record") and how to count them."""
        return copy.deepcopy(DESCRIPTION)

    def handle(self, request):
        """The reply text, the files to send and the tool trace; "record" is the answer's record when the agent
        ran, absent for a message answered before it (an unreadable file, nothing to ask)."""
        key = request["session_id"]
        session = Path(request["session_dir"])
        question = request.get("text", "")
        history = list(request.get("history") or [])
        attachments = [SimpleNamespace(**a) for a in request.get("attachments", [])]
        notify = request.get("notify")
        if request.get("project"):
            self.projects[key] = Path(request["project"])
        extra = ""  # file contents the model reads after the question
        sent = None  # what was attached, for the question asked when the message has no text
        unread = []  # suffixes of attachments the bot cannot read (video, PDF, and images when the model reads none)
        images = []  # {"media_type", "data"}: images the model reads with the question
        for att in attachments:
            # the log keeps a digest of the name, not the name: users send receipts and other private files
            suffix = Path(att.filename or "").suffix.lower()
            # the session key leads the line as in qqbot's own lines, so its panel can split private and group chats
            log.info("%s attachment: name-md5 %s, %s, %s bytes, %s", key,
                     hashlib.md5((att.filename or "").encode()).hexdigest(), att.content_type, att.size, suffix)
            if not att.url:
                continue
            if suffix in attachments_mod.PROJECT_SUFFIXES:
                try:
                    project, more = unpack_project(att.url, att.filename, session)
                except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError) as exc:
                    log.warning("project unpack failed: %s", exc)
                    text = f"项目文件打不开：{exc}" if isinstance(exc, attachments_mod.Unreadable) else \
                        "项目文件打不开，请重新发送；还打不开就在 Construct 3 里另存为 .c3p 再发。"
                    return {"text": text, "files": [], "trace": []}
                history.clear()
                if project:
                    self.projects[key] = project
                    kb.edits.reset(project)  # the edits of an earlier upload do not apply to this one
                    log.info("project for %s: %s", key, project)
                else:  # a Construct 2 project replaces the session's project too
                    self.projects.pop(key, None)
                    if session.exists():
                        shutil.rmtree(session)
                    log.info("capx for %s: %d characters of events", key, len(more))
                extra += more
                sent = "项目"
            elif suffix in attachments_mod.TEXT_SUFFIXES:
                try:
                    data = attachments_mod.download(att.url, attachments_mod.TEXT_MAX)
                except (OSError, ValueError) as exc:
                    log.warning("text file download failed: %s", exc)
                    text = f"文件打不开：{exc}" if isinstance(exc, attachments_mod.Unreadable) else "文件没有下载成功，请重新发送。"
                    return {"text": text, "files": [], "trace": []}
                log.info("text file: %s bytes", len(data))
                extra += attachments_mod.text_block(att.filename, data)
                sent = sent or "文件"
            elif self.vision and (media := attachments_mod.image_type(att.filename or "", att.content_type or "")):
                # 2026-10-18: a screenshot of a skew effect reached Claude only as "a .png you cannot read"
                try:
                    data = attachments_mod.download(att.url, attachments_mod.IMAGE_MAX)
                except (OSError, ValueError) as exc:
                    log.warning("image download failed: %s", exc)
                    unread.append(suffix or media)
                    continue
                images.append({"media_type": media, "data": base64.b64encode(data).decode("ascii")})
                sent = sent or "图片"
            else:
                unread.append(suffix or "无扩展名")
        # kept on disk: "给我做一个示例" after three restarts was built from the old project, without the image (2026-10-19)
        kept = session.parent / "_images" / f"{re.sub(r'[^A-Za-z0-9_-]', '_', key)}.json"
        if images:
            kept.parent.mkdir(parents=True, exist_ok=True)
            kept.write_text(json.dumps({"images": images, "left": EARLIER_IMAGE_TURNS}), encoding="utf-8")
        elif self.vision and question and kept.is_file():
            # history keeps only text, so "还原一模一样的效果图" after a screenshot was built without it (2026-10-18)
            try:
                earlier = json.loads(kept.read_text(encoding="utf-8"))
                images, left = earlier["images"], earlier["left"]
            except (OSError, ValueError, KeyError, TypeError) as exc:
                log.warning("earlier image unreadable: %s", exc)
                images, left = [], 0
            if left > 1:
                kept.write_text(json.dumps({"images": images, "left": left - 1}), encoding="utf-8")
            else:
                kept.unlink(missing_ok=True)
            if images:
                extra += "\n(The image sent earlier in this chat comes with this message again.)"
        if unread and question:
            # without the note the model answered "没看懂" to a question about a file it never saw (2026-10-04)
            readable = "Construct 3 projects, text files and images under 5 MB" if self.vision else \
                "Construct 3 projects and text files"
            question += (f"\n(This message also came with a {', '.join(unread)} file that you cannot read: only "
                         f"{readable} reach you. Say so in one sentence if the question is about that file.)")
        elif sent is None and question and (key in self.projects or (session.is_dir() and any(session.rglob("project.c3proj")))):
            # a project sent earlier pulled a general question into its scripts (2026-10-04)
            # the first wording ended the answer with an offer to apply it if the person sent the .c3p again
            question += ("\n(The project sent earlier is still open, so never ask for its file. If this message is "
                         "not about that project, answer it as a general question with search_guides, not from its "
                         "scripts, or make the example it asks for with the project tools; end with the answer: "
                         "no offer to apply it to the project, and "
                         "not a word about the project or this note.)")
        if sent and not question:
            # an open question about a sent project made the model invent problems to fix (2026-10-04)
            question = {"项目": "我发来了项目，说说它做了什么。", "图片": "我发来了图片，说说它是什么。"}.get(
                sent, "我发来了文件，说说它是什么。")
        elif sent:
            question = f"{question}（随这条消息发来了{sent}）"
        if not question:
            return {"text": "请发送 Construct 问题、项目或文本文件。", "files": [], "trace": []}
        question = question[:QUESTION_MAX] + extra
        outbox = []
        record = {}  # filled by the agent, also when it fails part way
        try:
            if key not in self.projects:  # a project sent before a restart is still on disk
                saved = next(session.rglob("project.c3proj"), None) if session.is_dir() else None
                if saved:
                    self.projects[key] = saved.parent
            text, trace = self.agent.answer(question, history, self.projects.get(key), request.get("group", False), outbox,
                                            session, notify, record=record, images=images)
            made = next(session.rglob("project.c3proj"), None) if session.is_dir() else None
            if made:  # a project the answer made replaces the session's
                self.projects[key] = made.parent
        except Exception:  # the reply must still go out
            log.exception("agent failed")
            # a build finished before the failure is packed in outbox and still goes (2026-10-06: a 402 after a build)
            text, trace = ("后面出了错，做好的部分先发你。" if outbox else "出错了，稍后再试。"), []
            # the host only sees handle return, so without this a 529 on the last call counted as answered (2026-10-18)
            record["failed"] = True
        return {"text": text, "trace": trace, "files": outbox, "record": record}

    def review(self):
        from .review import main
        main()
