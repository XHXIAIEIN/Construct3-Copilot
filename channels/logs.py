"""Read the channel's answers one turn at a time, instead of grepping bot.log, whose tool lines held whole traces.

    python -m channels.logs                         the last 10 turns: time, question, files, cost, tools, reply
    python -m channels.logs --since 23:00           turns from 23:00 today (or "2026-10-18", "2026-10-18 23:00")
    python -m channels.logs --session E5DB --failed  turns of a chat whose key contains E5DB and that failed
    python -m channels.logs --skipped               only the messages given no answer, each with the bot message
                                                    it was judged against
    python -m channels.logs --turn 20261018-231714-a1b2              one turn in full, its trace one step a line
    python -m channels.logs --turn 20261018-231714-a1b2 --grep new_project --width 0   only those steps, uncut

The list also shows the messages given no answer (skipped.jsonl, such as a "哦哦" after a reply), in time order
among the turns. A turn or message that waited WAIT_SHOWN seconds or more for its chat's running answer shows the
wait and when it came. A turn written before turn ids existed shows its counts only; its question, reply and trace
are in bot.log.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime

from .core.answers import read_answers, read_skipped, read_turns, trace_summary

OLD = "（旧记录：问题、回复和工具轨迹只在 bot.log）"
# skipped.jsonl's "skipped", as channels/core/chat.py writes it
REASONS = {"ack": "只表示收到，没回复也没调模型"}
# seconds; a message that comes while its chat has no answer running waits well under one
WAIT_SHOWN = 3


def local_time(line: dict, name: str = "at") -> datetime | None:
    try:
        return datetime.fromisoformat(str(line[name]).replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
    except (KeyError, ValueError):
        return None


def wait(line: dict) -> str:
    """How long the message waited for its chat's running answer, when it is long enough to be such a wait."""
    waited = line.get("waited")
    if not isinstance(waited, (int, float)) or waited < WAIT_SHOWN:
        return ""
    came = local_time(line, "arrived")
    return f"  排队 {waited:.0f}s" + (f"（{came:%H:%M:%S} 到）" if came else "")


def parse_since(text: str) -> datetime:
    for form in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, form)
        except ValueError:
            pass
    try:
        return datetime.combine(date.today(), datetime.strptime(text, "%H:%M").time())
    except ValueError:
        raise argparse.ArgumentTypeError(f"not HH:MM, YYYY-MM-DD or YYYY-MM-DD HH:MM: {text}") from None


def cut(text: str, width: int) -> str:
    text = str(text).replace("\n", " / ")
    return text if not width or len(text) <= width else f"{text[:width]}…（共 {len(text)} 字）"


def cut_step(step: str, width: int) -> str:
    """A trace step cut to width keeps what the tool answered after " -> " and cuts the arguments before it."""
    call, arrow, result = str(step).partition(" -> ")
    if not width or len(step) <= width or not arrow:
        return cut(step, width)
    return f"{cut(call, max(width - len(result) - 4, 40))}{arrow}{cut(result, width)}"


def files(items: list) -> str:
    return ", ".join(f"{f.get('type') or '?'} {f.get('bytes')}B" + ("" if f.get("sent", True) else " 未发出")
                     for f in items if isinstance(f, dict)) or "-"


def app_fields(app) -> str:
    """The application's record without knowing it: a scalar as is, a list as its length, with how many of its
    items say ok false, an object as its own fields in brackets."""
    if not isinstance(app, dict):
        return ""
    parts = []
    for key, value in app.items():
        if isinstance(value, list):
            bad = sum(1 for v in value if isinstance(v, dict) and v.get("ok") is False)
            parts.append(f"{key} {len(value)}" + (f"（{bad} 个失败）" if bad else ""))
        elif isinstance(value, dict):
            parts.append(f"{key}（{app_fields(value)}）")
        else:
            parts.append(f"{key}={value}")
    return ", ".join(parts)


def unsent(line: dict) -> str:
    """How much of the reply did not go out, empty when all of it did or the line does not say."""
    if line.get("reply_sent") is not False:
        return ""
    went, total = (line.get("reply_parts") or ["?", "?"])[:2]
    return f"回复只发出 {went}/{total} 段，“答”是发出的部分"


def head(line: dict) -> str:
    when = local_time(line)
    return (f"[{when:%Y-%m-%d %H:%M:%S}] " if when else "") + (
        f"turn {line.get('turn', '-')}  {line.get('chat')} {line.get('session')}{wait(line)}  "
        f"{line.get('seconds')}s calls {line.get('calls')} prompt {line.get('prompt')} "
        f"completion {line.get('completion')}" + (f" model {line['model']}" if line.get("model") else "")
        + f"  {'ok' if line.get('ok') else '失败'}")


def summary(line: dict, turn: dict | None, width: int) -> str:
    rows = [head(line), f"  文件：收 {files(line.get('files_in', []))}；发 {files(line.get('files_out', []))}"]
    if line.get("app"):
        rows.append(f"  应用：{app_fields(line['app'])}")
    if unsent(line):
        rows.append(f"  {unsent(line)}")
    if turn is None:
        rows.append(f"  {OLD}")
    else:
        rows += [f"  问：{cut(turn.get('question', ''), width)}",
                 f"  工具（{len(turn.get('trace', []))} 步）：{trace_summary(turn.get('trace', []))}",
                 f"  答：{cut(turn.get('reply', ''), width)}"]
    return "\n".join(rows)


def skipped(line: dict, width: int) -> str:
    when = local_time(line)
    reason = line.get("skipped")
    after = cut(line.get("after", ""), width) or "（无：会话还没有回复，或消息来时上一问正在回答、还没发提示）"
    return "\n".join([(f"[{when:%Y-%m-%d %H:%M:%S}] " if when else "")
                      + f"未回答  {line.get('chat')} {line.get('session')}{wait(line)}  {REASONS.get(reason, reason)}",
                      f"  消息：{cut(line.get('message', ''), width)}", f"  对照的 bot 消息的最后一句：{after}"])


def detail(line: dict, turn: dict | None, width: int, grep: str | None) -> str:
    rows = [head(line), f"文件：收 {files(line.get('files_in', []))}；发 {files(line.get('files_out', []))}"]
    if line.get("app"):
        rows.append(f"应用：{app_fields(line['app'])}")
    if unsent(line):
        rows.append(unsent(line))
    if turn is None:
        return "\n".join(rows + [OLD])
    trace = turn.get("trace", [])
    pattern = re.compile(grep) if grep else None
    history = turn.get("history")
    if isinstance(history, list):  # turns written before it was kept have none
        rows.append(f"带着的历史（{len(history)} 条）：" + ("" if history else "无"))
        rows += [f"  {'问' if m.get('role') == 'user' else '答'}：{cut(m.get('content', ''), width)}"
                 for m in history if isinstance(m, dict)]
    rows += [f"问：{turn.get('question', '')}", f"答：{turn.get('reply', '')}"]
    if "written" in turn:
        rows.append(f"应用写的全文：{turn['written']}")
    rows.append(f"工具轨迹（{len(trace)} 步" + (f"，只列含 {grep} 的" if grep else "") + "）：")
    rows += [f"  {n:>3}. {cut_step(step, width)}" for n, step in enumerate(trace, 1)
             if pattern is None or pattern.search(step)]
    return "\n".join(rows)


def main(argv=None) -> None:
    from . import settings as channel_settings
    from .platforms import PANEL
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--channel", default=PANEL, help=f"the channel's log folder under logs/ (default {PANEL})")
    parser.add_argument("--last", type=int, default=10, help="how many turns, newest last (default 10, 0 for all)")
    parser.add_argument("--since", type=parse_since, help="turns from this local time")
    parser.add_argument("--session", help="turns of chats whose key contains this")
    only = parser.add_mutually_exclusive_group()
    only.add_argument("--failed", action="store_true", help="only answers whose handle raised")
    only.add_argument("--skipped", action="store_true", help="only messages given no answer")
    parser.add_argument("--turn", help="one turn in full")
    parser.add_argument("--grep", help="with --turn: only trace steps matching this regular expression")
    parser.add_argument("--width", type=int, help="characters per question, reply or step (default 200 in the list, "
                                                  "400 per step with --turn; 0 for no cut)")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    data_dir = channel_settings.data_dir(channel_settings.load())
    lines = read_answers(data_dir, args.channel)

    if args.turn:
        line = next((l for l in reversed(lines) if l.get("turn") == args.turn), None)
        if line is None:
            parser.exit(1, f"no turn {args.turn} in logs/{args.channel}/answers.jsonl\n")
        print(detail(line, read_turns(data_dir, args.channel, [args.turn]).get(args.turn),
                     400 if args.width is None else args.width, args.grep))
        return

    if args.failed:
        lines = [l for l in lines if not l.get("ok")]
    elif args.skipped:
        lines = read_skipped(data_dir, args.channel)
    else:  # an answer's line is written once it is sent, so a skip sorts after the reply it followed
        lines = sorted(lines + read_skipped(data_dir, args.channel), key=lambda l: local_time(l) or datetime.min)
    if args.since:
        lines = [l for l in lines if (local_time(l) or datetime.min) >= args.since]
    if args.session:
        lines = [l for l in lines if args.session in str(l.get("session", ""))]
    if args.last:
        lines = lines[-args.last:]
    if not lines:
        print(f"nothing in logs/{args.channel}/answers.jsonl or skipped.jsonl for this filter")
        return
    turns = read_turns(data_dir, args.channel, [l["turn"] for l in lines if l.get("turn")])
    width = 200 if args.width is None else args.width
    print("\n\n".join(skipped(l, width) if "skipped" in l else summary(l, turns.get(l.get("turn")), width)
                      for l in lines))


if __name__ == "__main__":
    main()
