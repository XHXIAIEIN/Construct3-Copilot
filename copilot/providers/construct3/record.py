"""The record of one answer that the host keeps beside its own fields, and the declaration of how to count it.

The host writes the record under "app" in its answer log without reading it; the panel counts it by DESCRIPTION
with its atomic operations. Both come from Copilot's own execution: the run's tool calls as the agent made them,
and the task store's rows for the scripts those calls ran and for the ACE check's own lookups. The application
adds "failed" when the answer broke off, which the host cannot tell, since the reply still goes out."""
from __future__ import annotations

from .acecheck import CHECK_REQUEST
from .services import TOOL_REQUEST

ACE_CHECK = "ace-check"  # the tool name of the check's lookups, beside the model's own lookup_ace

DESCRIPTION = {
    "id": "construct3",
    "label": "Construct 3",
    "fields": [
        {"id": "build", "label": "生成结果", "values": {"ok": "成功", "failed": "失败"}},
        {"id": "fixes", "label": "自动修正"},
        {"id": "tools", "label": "工具"},  # a list of {"name", "ok"}
        {"id": "failed", "label": "出错"},  # true when the answer broke off and the reply said so
    ],
    "metrics": [
        {"id": "failed", "label": "出错", "op": "count", "where": {"failed": True}, "unit": "次",
         "note": {"label": "占", "op": "rate", "field": "failed", "format": "percent"}},
        {"id": "builds", "label": "生成项目", "op": "count", "by": "build", "unit": "次"},
        {"id": "fixes", "label": "自动修正", "op": "sum", "field": "fixes", "unit": "处",
         "note": {"label": "来自", "op": "count", "where": {"build": ["ok", "failed"]}, "unit": "次生成"}},
        {"id": "tools", "label": "工具", "op": "count", "each": "tools", "by": "name", "split": "ok", "view": "table",
         "names": {ACE_CHECK: "ACE 校验"}},
    ],
}


def fixed_lines(result: str) -> int:
    """The spec errors a build corrected by itself: its "fixed: " lines, counted whatever the build's outcome."""
    return sum(line.startswith("fixed: ") for line in result.splitlines())


def settle(calls: list[dict], children: list[dict]) -> dict:
    """The record from the run's calls ({"id", "name", "ok"}, a build also "built" and "fixes") and the task
    store's rows under the answer. A call fails when the agent saw an error, when it was a build that built
    nothing, or when a script it ran did not complete; the ACE check's lookups are tools of their own."""
    status: dict[str, bool] = {}
    checks = []
    for row in children:
        request_id = str(row.get("request_id") or "")
        completed = row.get("status") == "completed"
        if request_id.startswith(CHECK_REQUEST):
            checks.append({"name": ACE_CHECK, "ok": completed})
        elif request_id.startswith(TOOL_REQUEST):
            call = request_id.removeprefix(TOOL_REQUEST).rsplit(":", 1)[0]
            status[call] = status.get(call, True) and completed
    tools = [{"name": c["name"], "ok": c["ok"] and c.get("built", True) and status.get(c["id"], True)} for c in calls]
    record: dict = {"tools": tools + checks}
    builds = [c for c in calls if "built" in c]
    if builds:
        record["build"] = "ok" if any(c["built"] for c in builds) else "failed"
        record["fixes"] = sum(c["fixes"] for c in builds)
    return record
