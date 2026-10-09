"""Files a user sends besides a Construct 3 project: text files read into the question, and a
Construct 2 project (.capx) printed as events, since the repository's tools read only Construct 3 folders."""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

TEXT_SUFFIXES = {".md", ".txt", ".js", ".ts", ".mjs", ".json", ".csv", ".xml", ".html", ".htm", ".css", ".log", ".ini",
                 ".yaml", ".yml"}
OTHER_ARCHIVES = {".rar", ".7z", ".tar", ".tgz", ".gz"}  # read with bsdtar and turned into a zip
PROJECT_SUFFIXES = {".c3p", ".zip", ".capx"} | OTHER_ARCHIVES
TEXT_MAX = 512 * 1024  # bytes downloaded of a text file
TEXT_CHARS = 8000  # characters of one file passed to the model
SHEET_CHARS = 12000  # characters of a .capx's printed events passed to the model


def download(url: str, limit: int) -> bytes:
    if url.startswith("//"):
        url = "https:" + url
    with urllib.request.urlopen(url, timeout=60) as resp:
        data = resp.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"file larger than {limit // (1024 * 1024)} MB")
    return data


def decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def text_block(name: str, data: bytes) -> str:
    """The file as the model reads it after the question."""
    text = decode(data)
    cut = f"\n(the file has {len(text)} characters; only the first {TEXT_CHARS} are shown)" if len(text) > TEXT_CHARS else ""
    return f"\n\n--- attached file {name} ---\n{text[:TEXT_CHARS]}{cut}\n--- end of {name} ---"


def bsdtar() -> str | None:
    """libarchive's tar, which reads rar (RAR5 too) and 7z: tar.exe on Windows 10 and later, bsdtar on Linux
    (package libarchive-tools); GNU tar reads neither."""
    windows = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "tar.exe"
    return shutil.which("bsdtar") or (str(windows) if windows.exists() else None)


def as_zip(data: bytes, filename: str, limit: int) -> bytes:
    """A .rar, .7z or tar archive unpacked and packed again as a zip, so the rest reads one format."""
    tool = bsdtar()
    if not tool:
        raise ValueError("这里读不了这种压缩包，改发 .zip 或 .c3p")
    try:
        return _as_zip(tool, data, filename, limit)
    except subprocess.TimeoutExpired:
        raise ValueError("压缩包太大，解压超时；改发 .zip 或 .c3p") from None


def _as_zip(tool: str, data: bytes, filename: str, limit: int) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / ("archive" + "".join(Path(filename).suffixes[-2:]).lower())
        src.write_bytes(data)
        listing = subprocess.run([tool, "-tvf", str(src)], capture_output=True, text=True, encoding="utf-8",
                                 errors="replace", timeout=60)
        if listing.returncode:
            raise ValueError("压缩包打不开，可能损坏或设了密码；改发 .zip 或 .c3p")
        # bsdtar -tv lists like ls -l: the fifth field is the size
        sizes = [line.split()[4] for line in listing.stdout.splitlines() if len(line.split()) > 4]
        if sum(int(s) for s in sizes if s.isdigit()) > limit:
            raise ValueError(f"解压后超过 {limit // (1024 * 1024)} MB")
        out = Path(tmp) / "x"
        out.mkdir()
        # bsdtar refuses absolute paths and ".." on extraction unless -P is given
        done = subprocess.run([tool, "-xf", str(src), "-C", str(out)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=120)
        if done.returncode:
            raise ValueError("压缩包解不开，可能设了密码；改发 .zip 或 .c3p")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
            for f in sorted(out.rglob("*")):
                if f.is_file():
                    zf.write(f, f.relative_to(out).as_posix())
        return buf.getvalue()


def nested_project(zf: zipfile.ZipFile) -> str | None:
    """The first .c3p or .capx inside a zip that holds no project of its own (a bundle of projects)."""
    names = [i.filename for i in zf.infolist() if Path(i.filename).suffix.lower() in (".c3p", ".capx")]
    return names[0] if names else None


# --- Construct 2 projects -------------------------------------------------------------------------

def _params(node: ET.Element) -> str:
    values = [(p.text or "").strip() for p in node.findall("param")]
    return f" ({', '.join(values)})" if values else ""


def _ace(node: ET.Element) -> str:
    owner = node.get("type") or ""
    behavior = node.get("behavior")
    who = f"{owner}.{behavior}" if behavior else owner
    neg = "NOT " if node.get("inverted") == "true" else ""
    return f"{neg}{who}: {node.get('name', node.get('id', '?'))}{_params(node)}"


def _events(parent: ET.Element, depth: int, out: list[str]) -> None:
    pad = "  " * depth
    for node in parent:
        tag = node.tag
        if tag == "event-block":
            conditions = node.find("conditions")
            conds = [_ace(c) for c in (conditions if conditions is not None else [])]
            head = " ; ".join(conds) or "(every tick)"
            if node.get("any") == "true":
                head = "[OR] " + head
            out.append(f"{pad}{head}")
            actions = node.find("actions")
            for a in actions if actions is not None else []:
                out.append(f"{pad}    -> {_ace(a)}")
            sub = node.find("sub-events")
            if sub is not None:
                _events(sub, depth + 1, out)
        elif tag == "event-group":
            out.append(f"{pad}group {node.get('title', '')}" + ("" if node.get("active", "true") == "true" else " (inactive)"))
            sub = node.find("sub-events")
            if sub is not None:
                _events(sub, depth + 1, out)
        elif tag == "comment":
            out.append(f"{pad}// {(node.text or '').strip()}")
        elif tag == "variable":
            const = "constant " if node.get("constant") == "1" else ""
            out.append(f"{pad}{const}{node.get('type', '').lower()} {node.get('name')} = {(node.text or '').strip()}")
        elif tag == "include":
            out.append(f"{pad}include {(node.text or '').strip()}")


def capx_events(zf: zipfile.ZipFile) -> str:
    """Every event sheet of a .capx as indented events, the way Construct 2 names its ACEs."""
    out: list[str] = []
    for info in sorted(zf.infolist(), key=lambda i: i.filename):
        path = info.filename.replace("\\", "/")
        if not (path.lower().startswith("event sheets/") and path.lower().endswith(".xml")):
            continue
        root = ET.fromstring(zf.read(info))
        out.append(f"== {root.findtext('name') or Path(path).stem}")
        events = root.find("events")
        if events is not None:
            _events(events, 1, out)
    return "\n".join(out)


def capx_block(name: str, zf: zipfile.ZipFile) -> str:
    sheets = capx_events(zf)
    cut = f"\n(events are {len(sheets)} characters; only the first {SHEET_CHARS} are shown)" if len(sheets) > SHEET_CHARS else ""
    return (f"\n\n--- {name} is a Construct 2 project (.capx); its event sheets follow ---\n"
            "print_sheet, check_project and edit_sheet do not read it. Construct 3 opens a .capx dragged into its "
            "window, unless it uses third-party addons the Construct 3 runtime lacks (manual: importing Construct 2 "
            "projects); to have it changed here, the person opens it in Construct 3, saves it as a .c3p and sends "
            "that. The names below are Construct 2's English ACE names.\n"
            f"{sheets[:SHEET_CHARS] or '(no event sheets)'}{cut}\n--- end of event sheets ---")
