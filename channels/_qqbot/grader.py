"""Silent grader: reads bot.log, has Codex (or Claude Code) check each reply, writes the verdict to reviews/.

Nothing is sent to QQ. The bot uses the Construct3-Agent-Skills tools and data. A grade names the root of each
wrong claim so a later session can fix it there.

    python -u grader.py              # follow bot.log from its end
    python -u grader.py --from-start # grade the whole log first
    GRADER=claude python -u grader.py # Claude Code instead of Codex

State (the byte offset read so far) lives in reviews/.offset, so a restart neither skips nor repeats a reply.
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import subprocess
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv  # noqa: E402

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")  # the paths and keys the bot itself reads
DATA = Path(os.environ.get("C3BOT_DATA") or HERE / "var")  # as c3bot/config.py reads it
LOG = DATA / "logs" / "bot" / "bot.log"
SESSIONS = DATA / "sessions"
REVIEWS = DATA / "reviews"
OFFSET = REVIEWS / ".offset"
from c3bot.construct3 import PLUGIN_ROOT, RAG  # noqa: E402
REPO = PLUGIN_ROOT
GRADER = os.environ.get("GRADER", "codex")  # the claude CLI's login expired on 2026-10-09; GRADER=claude after a /login
CODEX_MODEL = os.environ.get("CODEX_MODEL", "gpt-5.6-sol")  # config.toml's default is refused on a ChatGPT account
TIMEOUT = 20 * 60  # seconds for one grade; a project question runs scripts in the editor's data
POLL = 5

LINE = re.compile(r"^(\S+ \S+) c3bot INFO (\S+) (asks|tools|reply): (.*)$")
SKIP_REPLIES = ("出错了，稍后再试。",)

log = logging.getLogger("grader")

PROMPT = """You grade one answer of a QQ bot that answers Construct 3 questions in Chinese. The bot runs a small
local model (qwen 27B) with tools from this repository. Nobody sees your grade but the repository's owner: do not
contact anyone, do not edit any file, do not run the bot.

Question ({key}, {when}):
{question}

Earlier turns of the same chat, oldest first (may be empty):
{earlier}

Tool calls the bot made:
{tools}

Reply it sent (" / " marks a line break):
{reply}

Snapshot of the chat's session folder (a project the user sent or the bot made, may be absent): {snap}

Check every factual claim of the reply against the plugin skill at skills/construct3-agent-plugin/SKILL.md.
Run scripts from skills/construct3-agent-plugin/scripts/ with --rag "{data_root}". Use lookup_ace.py for each
condition, action, expression and addon it names (both zh-CN names and en-US), search_guides.py and
prompts/pitfalls/ for the approach, data/c3-examples for examples it names, print_sheet.py / print_layout.py /
check_project.py on the snapshot when the reply describes or changes a project. If the reply describes an approach,
judge whether it works in Construct 3 and whether it matches what the pitfalls say. Do not grade style beyond:
a reply that dodges the question or asks for information it already has counts as wrong.

Write the grade in Chinese for the owner, in this exact shape and nothing else:

评分：对 | 部分对 | 错 | 没答
问题：<one line>
错处：
- <each wrong or missing claim, with the evidence: script output, file and line>
根因：<where the repo or the bot falls short so the model said this: a missing pitfall (name the file it belongs
in), a lookup miss (the query that failed), a misleading script message, a bot prompt or tool limit, or "模型自己的错"
when the tools returned the right thing and the model ignored it. Quote the tool output that shows it>
建议：<one concrete fix, or "无">
"""


def snapshot(key: str, stamp: str) -> Path | None:
    """Copies the session folder now, because the next upload replaces it."""
    src = SESSIONS / re.sub(r"[^A-Za-z0-9_-]", "_", key)
    if not src.is_dir():
        return None
    dst = REVIEWS / "snap" / f"{stamp}_{src.name}"
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.c3p", "*.zip"))
    return dst


def grade(item: dict) -> str:
    prompt = PROMPT.format(**item, data_root=RAG.as_posix())
    if GRADER == "codex":
        cmd = ["codex", "exec", "-m", CODEX_MODEL, "--sandbox", "read-only", "-C", str(REPO), "-"]
    else:
        cmd = ["claude", "-p", "--output-format", "text",
               "--allowedTools", "Read", "Grep", "Glob", "Bash(python:*)", "Bash(python3:*)",
               "--disallowedTools", "Edit", "Write", "NotebookEdit"]
        if item["snap"] != "none":
            cmd += ["--add-dir", item["snap"]]
    try:
        done = subprocess.run(cmd, input=prompt, cwd=REPO, capture_output=True, text=True, encoding="utf-8",
                              timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return f"评分：没评完\n问题：{item['question'][:80]}\n错处：\n- 批改超过 {TIMEOUT // 60} 分钟\n根因：无\n建议：无"
    if done.returncode != 0:
        return f"评分：没评完\n问题：{item['question'][:80]}\n错处：\n- {GRADER} 退出码 {done.returncode}：{done.stderr.strip()[-400:]}\n根因：无\n建议：无"
    return done.stdout.strip()


def write(item: dict, verdict: str) -> None:
    day = REVIEWS / f"{item['when'][:10]}.md"
    with day.open("a", encoding="utf-8") as f:
        f.write(f"## {item['when']} {item['key']}\n\n**问：** {item['question']}\n\n**答：** {item['reply']}\n\n"
                f"工具：`{item['tools'][:600]}`\n\n{verdict}\n\n---\n\n")
    first = verdict.splitlines()[0] if verdict else "?"
    with (REVIEWS / "summary.tsv").open("a", encoding="utf-8") as f:
        f.write(f"{item['when']}\t{item['key']}\t{first}\t{item['question'][:60]}\n")
    log.info("%s %s -> %s", item["when"], item["key"], first)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-start", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    REVIEWS.mkdir(exist_ok=True)
    if args.from_start:
        offset = 0
    elif OFFSET.exists():
        offset = int(OFFSET.read_text())
    else:
        offset = LOG.stat().st_size
    pending: dict[str, deque] = defaultdict(deque)  # key -> asks waiting for their reply
    tools: dict[str, str] = {}
    turns: dict[str, deque] = defaultdict(lambda: deque(maxlen=2))
    log.info("grader %s from byte %d of %s", GRADER, offset, LOG)
    while True:
        size = LOG.stat().st_size
        if size < offset:  # the log was rotated or truncated
            offset = 0
        if size == offset:
            time.sleep(POLL)
            continue
        with LOG.open("rb") as f:
            f.seek(offset)
            chunk = f.read()
        end = chunk.rfind(b"\n") + 1  # a line still being written waits for the next read
        lines = chunk[:end].decode("utf-8", errors="replace").splitlines()
        offset += end
        for line in lines:
            m = LINE.match(line)
            if not m:
                continue
            when, key, kind, text = m.groups()
            key = key.replace(":", "_")  # the session folder's spelling
            if kind == "asks":
                pending[key].append((when, text))
            elif kind == "tools":
                tools[key] = text
            elif pending[key]:
                asked_at, question = pending[key].popleft()
                if text in SKIP_REPLIES:
                    continue
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                snap = snapshot(key, stamp)
                earlier = "\n".join(f"Q: {q}\nA: {a}" for q, a in turns[key]) or "(none)"
                item = {"key": key, "when": asked_at, "question": question, "earlier": earlier,
                        "tools": tools.pop(key, "[]"), "reply": text, "snap": str(snap) if snap else "none"}
                turns[key].append((question, text))
                write(item, grade(item))
            OFFSET.write_text(str(offset))
        OFFSET.write_text(str(offset))


if __name__ == "__main__":
    main()
