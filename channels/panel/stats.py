"""Count the channels' answer logs (<data>/logs/<channel>/answers.jsonl) with a few atomic operations.

A metric is a declaration, not code: an op (count, sum, avg, rate) over the answers, after where (keep the ones
whose fields equal the given values, or one of a list), each (one item per element of a list field, whose own
fields the later paths then name), by (one result per value of a field) and split (one result for a true field,
one for a false one). The base metrics below are written that way over the fields every channel writes; the
application declares its own over the fields it adds under "app", in <data>/runtime/app.json. The panel knows
nothing of either application or channel beyond these declarations."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

OPS = ("count", "sum", "avg", "rate")
LOG_BYTES = 8 * 1024 * 1024  # per channel, about 20 000 answers
CHATS = ("private", "group")  # the chart stacks these and puts every other chat (the terminal) in a third part

BASE = [
    {"id": "answers", "label": "回答", "op": "count", "unit": "次",
     "note": {"label": "完成", "op": "rate", "field": "ok", "format": "percent"}},
    {"id": "people", "label": "人数", "op": "count", "distinct": "session", "unit": "人"},
    {"id": "tokens", "label": "词元", "op": "sum", "field": ["prompt", "completion"], "format": "number",
     "note": {"label": "输出", "op": "sum", "field": "completion", "format": "number"}},
    {"id": "seconds", "label": "用时（平均）", "op": "avg", "field": "seconds", "format": "duration"},
    {"id": "received", "label": "用户上传", "op": "count", "each": "files_in", "unit": "个",
     "note": {"label": "共", "op": "sum", "each": "files_in", "field": "bytes", "format": "bytes"}},
    {"id": "sent", "label": "发给用户", "op": "count", "each": "files_out", "where": {"sent": True}, "unit": "个",
     "note": {"label": "未发出", "op": "count", "each": "files_out", "where": {"sent": False}, "unit": "个"}},
]
NO_APP = "应用未提供统计"


def get(item, path):
    """The value at a dotted path, None when any step is missing."""
    for step in path.split("."):
        if not isinstance(item, dict):
            return None
        item = item.get(step)
    return item


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _value(item, field):
    """A field's number; a list of fields adds theirs up."""
    if isinstance(field, list):
        parts = [_number(get(item, f)) for f in field]
        return None if all(p is None for p in parts) else sum(p or 0 for p in parts)
    return _number(get(item, field))


def _matches(item, where):
    for path, want in (where or {}).items():
        value = get(item, path)
        if value not in want if isinstance(want, list) else value != want:
            return False
    return True


def _apply(metric, items):
    op = metric["op"]
    if op == "count":
        return len({json.dumps(get(i, metric["distinct"]), sort_keys=True) for i in items}) if metric.get("distinct") else len(items)
    if op == "rate":
        return sum(bool(get(i, metric["field"])) for i in items) / len(items) if items else None
    values = [v for v in (_value(i, metric["field"]) for i in items) if v is not None]
    if op == "sum":
        return sum(values)
    return sum(values) / len(values) if values else None  # avg


def _split(metric, items):
    if not metric.get("split"):
        return _apply(metric, items)
    return {str(flag).lower(): _apply(metric, [i for i in items if bool(get(i, metric["split"])) is flag])
            for flag in (True, False)}


def evaluate(metric, records):
    """The metric over records: a number (None when it has nothing to average), or with split
    {"true": ..., "false": ...}, or with by {value: number or split}."""
    if metric.get("op") not in OPS:
        raise ValueError(f"unknown op {metric.get('op')!r}")
    items = records
    if metric.get("each"):
        lists = (get(r, metric["each"]) for r in records)
        items = [element for found in lists if isinstance(found, list) for element in found]
    items = [i for i in items if _matches(i, metric.get("where"))]
    if not metric.get("by"):
        return _split(metric, items)
    groups = {}
    for item in items:
        key = get(item, metric["by"])
        if key is not None and not isinstance(key, (dict, list)):
            groups.setdefault(str(key).lower() if isinstance(key, bool) else str(key), []).append(item)
    return {key: _split(metric, group) for key, group in groups.items()}


def scalar(metric, result):
    """One number for a tile or a bar: a split or a by adds its parts up where the op adds up."""
    if isinstance(result, dict):
        parts = [scalar(metric, v) for v in result.values()]
        return sum(p or 0 for p in parts) if metric["op"] in ("count", "sum") else None
    return result


def additive(metric):
    """Whether a slice's results add up to the whole, so the chart can stack private and group chats."""
    return metric["op"] == "sum" or (metric["op"] == "count" and not metric.get("distinct"))


# ---- reading

def _tail(path, cap):
    with path.open("rb") as stream:
        size = stream.seek(0, 2)
        stream.seek(max(0, size - cap))
        data = stream.read()
    if size > cap:
        data = data[data.find(b"\n") + 1:]  # the first line began before the tail
    return data.decode("utf-8", errors="replace"), size > cap


def answers(data_dir):
    """Every channel's answers, oldest first, each with its local time under "_when"; and whether a log was cut."""
    records, clipped = [], False
    for path in sorted((data_dir / "logs").glob("*/answers.jsonl")):
        try:
            text, cut = _tail(path, LOG_BYTES)
        except OSError:
            continue
        clipped = clipped or cut
        for line in text.splitlines():
            try:
                record = json.loads(line)
                record["_when"] = datetime.fromisoformat(record["at"].replace("Z", "+00:00")).astimezone()
            except (ValueError, TypeError, KeyError, AttributeError):
                continue  # a torn or foreign line
            records.append(record)
    records.sort(key=lambda r: r["_when"])
    return records, clipped


def description(data_dir):
    """The application's declaration, or None when there is none or it cannot be read."""
    try:
        value = json.loads((data_dir / "runtime" / "app.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(value, dict) or not isinstance(value.get("metrics"), list):
        return None
    return value


def buckets(range_, now):
    """The chart's columns: the last 14 days or the last 12 months, oldest first."""
    if range_ == "day":
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        days = [today - timedelta(days=i) for i in range(13, -1, -1)]
        return [{"key": d.strftime("%Y-%m-%d"), "start": d, "tick": "今天" if i == 13 else "" if (13 - i) % 2 else f"{d.month}/{d.day}",
                 "name": "今天" if i == 13 else f"{d.month}月{d.day}日"} for i, d in enumerate(days)]
    months, year, month = [], now.year, now.month
    for _ in range(12):
        months.append(now.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0))
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    return [{"key": d.strftime("%Y-%m"), "start": d, "tick": f"{d.month}月", "name": f"{d.year}年{d.month}月"}
            for d in reversed(months)]


def _series(metric, slices, root):
    """One bar per slice: [private, group, other] when the metric adds up, else [value]."""
    bars = []
    for records in slices:
        rows = [root(r) for r in records]
        if additive(metric):
            chats = [[root(r) for r in records if r.get("chat") == c] for c in CHATS]
            other = [root(r) for r in records if r.get("chat") not in CHATS]
            bars.append([scalar(metric, evaluate(metric, part)) if part else 0 for part in (*chats, other)])
        else:
            bars.append([scalar(metric, evaluate(metric, rows)) if rows else None])
    return bars


def _metric(metric, records, columns, root, fields):
    rows = [root(r) for r in records]
    result = evaluate(metric, rows)
    shown = {k: metric[k] for k in ("id", "label", "unit", "format", "names") if k in metric}
    shown["view"] = metric.get("view", "tile")
    if metric.get("by") and fields.get(metric["by"]):
        shown["values"] = fields[metric["by"]]
    if shown["view"] == "table":
        return {**shown, "rows": result}
    note = metric.get("note")
    out = {**shown, "value": scalar(metric, result), "parts": result if isinstance(result, dict) else None,
           "stacked": additive(metric),
           "trend": _series(metric, [[r for r in records if r["_key"] == c["key"]] for c in columns], root),
           "hours": _series(metric, [[r for r in records if r["_when"].hour == h] for h in range(24)], root)}
    if isinstance(note, dict) and note.get("op") in OPS:
        out["note"] = {k: note[k] for k in ("label", "unit", "format") if k in note}
        out["note"]["value"] = scalar(note, evaluate(note, rows)) if rows else None
    return out


def _checked(metrics):
    return [m for m in metrics if isinstance(m, dict) and m.get("op") in OPS and m.get("id")]


def report(data_dir, range_="day", now=None):
    """The stats page: the base metrics and the application's, over the chosen range."""
    now = now or datetime.now().astimezone()
    columns = buckets(range_, now)
    records, clipped = answers(data_dir)
    shown = []
    for record in records:
        when = record["_when"]
        if when >= columns[0]["start"]:
            record["_key"] = when.strftime("%Y-%m-%d" if range_ == "day" else "%Y-%m")
            shown.append(record)
    app = description(data_dir)
    out = {"range": range_, "clipped": clipped, "total": len(records), "count": len(shown),
           "since": records[0]["_when"].strftime("%Y-%m-%d") if records else None,
           "buckets": [{k: c[k] for k in ("key", "tick", "name")} for c in columns],
           "base": [_metric(m, shown, columns, lambda r: r, {}) for m in BASE]}
    if app is None:
        out["app"] = None
        out["app_note"] = NO_APP
    else:
        fields = {f["id"]: f.get("values") for f in app.get("fields", []) if isinstance(f, dict) and f.get("id")}
        out["app"] = {"id": app.get("id"), "label": app.get("label") or app.get("id") or "应用",
                      "metrics": [_metric(m, shown, columns, lambda r: r.get("app") or {}, fields)
                                  for m in _checked(app["metrics"])]}
    return out
