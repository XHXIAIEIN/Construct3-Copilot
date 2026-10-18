"""Review Construct replies against the installed skills and project snapshot."""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path

from .services import DATA, RAG, get_runtime
# The channel's answer log and, under each line's turn id, the question, reply and trace. copilot/ does not import
# channels/, so the two JSON files are read here; channels/core/answers.py writes them.
ANSWERS = DATA / "logs" / "qq" / "answers.jsonl"
TURNS = ANSWERS.with_name("turns.jsonl")
SESSIONS = DATA / "sessions"
REVIEWS = DATA / "reviews"
OFFSET = REVIEWS / ".answers-offset"  # .offset counted bytes of bot.log
GRADER = os.environ.get("GRADER", "codex")  # the claude CLI's login expired on 2026-10-09; GRADER=claude after a /login
CODEX_MODEL = os.environ.get("CODEX_MODEL", "gpt-5.6-sol")  # config.toml's default is refused on a ChatGPT account
TIMEOUT = 20 * 60  # seconds for one grade; a project question runs scripts in the editor's data
POLL = 5


log = logging.getLogger("grader")

PROMPT = """You grade one answer of a QQ bot that answers Construct 3 questions in Chinese. The bot runs a small
configured model with tools from this installation. Nobody sees your grade but the repository's owner: do not
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

Check every factual claim of the reply against the installed skill and data: lookup_ace.py for each
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
    prompt = (PROMPT.format(**item) + "\nRead skills/construct3-agent-plugin/SKILL.md. "
              "Run scripts from skills/construct3-agent-plugin/scripts/ with --rag "
              + json.dumps(RAG.as_posix()) + ".")
    repo = get_runtime().skills_root
    if GRADER == "codex":
        cmd = ["codex", "exec", "-m", CODEX_MODEL, "--sandbox", "read-only", "-C", str(repo), "-"]
    else:
        cmd = ["claude", "-p", "--output-format", "text",
               "--allowedTools", "Read", "Grep", "Glob", "Bash(python:*)", "Bash(python3:*)",
               "--disallowedTools", "Edit", "Write", "NotebookEdit"]
        if item["snap"] != "none":
            cmd += ["--add-dir", item["snap"]]
    try:
        done = subprocess.run(cmd, input=prompt, cwd=repo, capture_output=True, text=True, encoding="utf-8",
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
                f"工具：`{item['tools'][:600].replace(chr(10), ' | ')}`\n\n{verdict}\n\n---\n\n")
    first = verdict.splitlines()[0] if verdict else "?"
    with (REVIEWS / "summary.tsv").open("a", encoding="utf-8") as f:
        f.write(f"{item['when']}\t{item['key']}\t{first}\t{item['question'][:60]}\n")
    log.info("%s %s -> %s", item["when"], item["key"], first)


def turn_of(turn: str) -> dict | None:
    """The question, reply and trace written under turn; the channel appends it just after the answer's line, so a
    miss is looked for again for a few polls."""
    for attempt in range(3):
        try:
            with TURNS.open(encoding="utf-8", errors="replace") as f:
                for raw in f:
                    if f'"{turn}"' in raw[:60]:  # "turn" is the first key; a whole line can be a long trace
                        try:
                            return json.loads(raw)
                        except ValueError:
                            break
        except OSError:
            pass
        if attempt < 2:
            time.sleep(POLL)
    return None


def item_of(line: dict, earlier: deque) -> dict | None:
    """What one answer's grade needs, None for a line not to grade: no turn (written before turn ids), a failed
    answer, a terminal question or a turn that cannot be found."""
    if not line.get("turn") or not line.get("ok") or line.get("chat") == "cli":
        return None
    turn = turn_of(line["turn"])
    if turn is None:
        log.warning("turn %s is not in %s; not graded", line["turn"], TURNS)
        return None
    key = str(line.get("session", "")).replace(":", "_")  # the session folder's spelling
    when = datetime.fromisoformat(str(line["at"]).replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    snap = snapshot(key, datetime.now().strftime("%Y%m%d-%H%M%S"))
    return {"key": key, "when": when, "question": turn.get("question", ""),
            "earlier": "\n".join(f"Q: {q}\nA: {a}" for q, a in earlier) or "(none)",
            "tools": "\n".join(turn.get("trace", [])) or "(none)", "reply": turn.get("reply", "").replace("\n", " / "),
            "snap": str(snap) if snap else "none"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-start", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    REVIEWS.mkdir(parents=True, exist_ok=True)
    if args.from_start:
        offset = 0
    elif OFFSET.exists():
        offset = int(OFFSET.read_text())
    else:
        offset = ANSWERS.stat().st_size if ANSWERS.exists() else 0
    turns: dict[str, deque] = defaultdict(lambda: deque(maxlen=2))
    log.info("grader %s from byte %d of %s", GRADER, offset, ANSWERS)
    while True:
        size = ANSWERS.stat().st_size if ANSWERS.exists() else 0
        if size < offset:  # the log was rotated or truncated
            offset = 0
        if size == offset:
            time.sleep(POLL)
            continue
        with ANSWERS.open("rb") as f:
            f.seek(offset)
            chunk = f.read()
        end = chunk.rfind(b"\n") + 1  # a line still being written waits for the next read
        lines = chunk[:end].decode("utf-8", errors="replace").splitlines()
        offset += end
        for raw in lines:
            try:
                line = json.loads(raw)
            except ValueError:
                continue
            key = str(line.get("session", "")).replace(":", "_")
            item = item_of(line, turns[key]) if isinstance(line, dict) else None
            if item is not None:
                turns[key].append((item["question"], item["reply"]))
                write(item, grade(item))
            OFFSET.write_text(str(offset))
        OFFSET.write_text(str(offset))


if __name__ == "__main__":
    main()
