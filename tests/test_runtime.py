"""Exercise execution boundaries with child processes and persistent task records."""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from copilot import Runtime, BusyError, DuplicateRequestError
from copilot.locks import ResourceLock


@pytest.fixture
def runtime(tmp_path):
    scripts = tmp_path / "provider/skills/construct3-agent-plugin/scripts"
    scripts.mkdir(parents=True)
    code = '''import pathlib, sys, time
args = sys.argv[1:]
if "--sleep" in args:
    time.sleep(30)
if "--counter" in args:
    p = pathlib.Path(args[args.index("--counter") + 1])
    p.write_text(str(int(p.read_text()) + 1) if p.exists() else "1")
if "--out" in args:
    pathlib.Path(args[args.index("--out") + 1]).write_bytes(b"artifact bytes")
print("result \\u4e2d\\u6587", flush=True)
print("diagnostic", file=sys.stderr, flush=True)
if "--fail" in args:
    sys.exit(7)
if "--busy" in args:
    sys.exit(5)
'''
    for name in ("lookup_ace", "print_sheet", "pack_project", "preview_project", "new_project"):
        (scripts / f"{name}.py").write_text(code, encoding="utf-8")
    return Runtime(tmp_path / "provider", tmp_path / "state")


@pytest.fixture
def project(tmp_path):
    folder = tmp_path / "project"
    folder.mkdir()
    (folder / "project.c3proj").write_text('{"uniqueId":"example-project"}')
    return folder


def test_result_retains_failure_and_provider(runtime):
    result = runtime.run_script("lookup_ace", ["--fail"])
    assert result["status"] == "failed" and result["exit_code"] == 7
    assert "中文" in result["stdout"] and "diagnostic" in result["stderr"]
    script = Path(result["provider"]["script"]["path"])
    assert result["provider"]["script"]["sha256"] == hashlib.sha256(script.read_bytes()).hexdigest()
    record = runtime.get_task(result["task_id"])
    assert record["status"] == "failed" and record["result"] == result
    assert (runtime.data_dir / "runs" / result["task_id"] / "stderr.txt").read_bytes().decode() == result["stderr"]


def test_idempotent_request_does_not_repeat_side_effect(runtime, tmp_path):
    counter = tmp_path / "count"
    args = ["--counter", str(counter)]
    first = runtime.run_script("lookup_ace", args, request_id="message-1")
    second = runtime.run_script("lookup_ace", args, request_id="message-1")
    assert first == second and counter.read_text() == "1"
    with pytest.raises(ValueError, match="different inputs"):
        runtime.run_script("lookup_ace", [], request_id="message-1")


def test_running_duplicate_is_not_reexecuted(runtime):
    request = {"capability": "lookup_ace", "args": [], "project": None,
               "locale": None, "limit": None, "timeout": 90}
    task_id = runtime.store.create("lookup_ace", request, "cli", "local", "pending")
    result = runtime.run_script("lookup_ace", [], request_id="pending")
    assert result["task_id"] == task_id and result["status"] == "running"


@pytest.mark.parametrize("name,args", [("../lookup_ace", []), ("unknown", []),
                                      ("lookup_ace", ["--project=other"])])
def test_rejects_unsupported_capability_or_project_override(runtime, name, args):
    result = runtime.run_script(name, args)
    assert result["status"] == "failed" and result["exit_code"] is None


def test_explicit_project_required_and_identity_retained(runtime, project):
    assert runtime.run_script("print_sheet", [])["status"] == "failed"
    result = runtime.run_script("print_sheet", [], project=project)
    assert result["status"] == "completed"
    assert result["project"]["unique_id"] == "example-project"
    assert result["project"]["path"] == str(project.resolve())


def test_project_lock_prevents_execution_and_is_released(runtime, project):
    with ResourceLock(runtime.data_dir / "locks", "project:" + os.path.normcase(str(project.resolve()))):
        result = runtime.run_script("print_sheet", [], project=project)
        assert result["status"] == "busy" and result["exit_code"] is None
    assert runtime.run_script("print_sheet", [], project=project)["status"] == "completed"


def test_timeout_is_not_success_and_result_is_persisted(runtime):
    result = runtime.run_script("lookup_ace", ["--sleep"], timeout=0.2)
    assert result["status"] == "timed_out" and result["exit_code"] != 0
    assert runtime.get_task(result["task_id"])["status"] == "timed_out"


def test_browser_busy_is_distinct_from_script_failure(runtime, project):
    result = runtime.run_script("preview_project", ["--busy"], project=project)
    assert result["status"] == "busy" and result["exit_code"] == 5
    assert runtime.run_script("lookup_ace", ["--busy"])["status"] == "failed"


def test_cleanup_timeout_keeps_timeout_outcome(runtime):
    process = Mock(returncode=0)
    process.communicate.side_effect = [subprocess.TimeoutExpired("script", 0.2),
                                       subprocess.TimeoutExpired("script", 5, output=b"partial")]
    with patch("copilot.runtime.subprocess.Popen", return_value=process), patch("copilot.runtime.terminate"):
        result = runtime.run_script("lookup_ace", [], timeout=0.2)
    assert result["status"] == "timed_out" and result["stdout"] == "partial"
    assert "handles remained open" in result["reason"]


@pytest.mark.parametrize("name,expected", [("screenshot_sheet", (False, False)),
                                          ("export_project", (False, False)),
                                          ("review_look", (False, True)),
                                          ("advanced_random", (False, True))])
def test_only_supported_shared_options_are_forwarded(runtime, project, name, expected):
    (runtime.script_root / f"{name}.py").write_text("import sys; print(repr(sys.argv[1:]))")
    result = runtime.run_script(name, [], project=project, locale="zh-CN", limit=123)
    assert result["status"] == "completed"
    assert ("--locale" in result["stdout"], "--limit" in result["stdout"]) == expected


def test_delivery_hash_uses_actual_file_bytes(runtime, project):
    result = runtime.run_script("pack_project", ["--out", "demo.c3p"], project=project)
    assert result["status"] == "completed"
    artifact, = result["artifacts"]
    assert artifact["path"] == str(project / "demo.c3p")
    assert artifact["sha256"] == hashlib.sha256(b"artifact bytes").hexdigest()


def test_pack_cannot_bypass_project_identity(runtime, project):
    result = runtime.run_script("pack_project", [str(project)])
    assert result["status"] == "failed" and result["exit_code"] is None
    result = runtime.run_script("pack_project", ["different-project", "--out", "demo.c3p"], project=project)
    assert result["status"] == "failed" and "positional SOURCE" in result["reason"]


def test_new_project_requires_target_before_options(runtime):
    result = runtime.run_script("new_project", ["--rag", "provider", "target"])
    assert result["status"] == "failed" and result["exit_code"] is None
    assert "target folder before" in result["reason"]


def test_parent_session_and_duplicate_message(runtime, project):
    with runtime.session("qqbot", "opaque", project=project, request_id="message") as task:
        with pytest.raises(BusyError):
            with runtime.session("qqbot", "opaque"):
                pass
        child = runtime.run_script("lookup_ace", [])
        assert child["parent_id"] == task.task_id
        task.finish(summary="Done")
    record = runtime.get_task(task.task_id)
    assert record["status"] == "completed" and len(record["children"]) == 1
    with pytest.raises(DuplicateRequestError):
        with runtime.session("qqbot", "opaque", project=project, request_id="message"):
            pass


def test_unfinished_session_fails_and_unlocks(runtime):
    with runtime.session("qqbot", "opaque") as task:
        pass
    assert runtime.get_task(task.task_id)["status"] == "failed"
    with runtime.session("qqbot", "opaque") as next_task:
        next_task.finish()


def test_parent_must_still_be_running(runtime):
    with runtime.session("qqbot", "opaque") as task:
        task.finish()
    with pytest.raises(ValueError, match="Parent task"):
        runtime.run_script("lookup_ace", [], parent_id=task.task_id)


def test_process_lock_survives_contention_and_releases_after_exit(runtime, tmp_path):
    ready = tmp_path / "ready"
    code = ("from copilot.locks import ResourceLock; from pathlib import Path; import time; "
            f"lock=ResourceLock(Path({str(runtime.data_dir / 'locks')!r}), 'cross-process'); "
            f"lock.__enter__(); Path({str(ready)!r}).write_text('ready'); time.sleep(30)")
    process = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 8
        while not ready.exists() and time.monotonic() < deadline and process.poll() is None:
            time.sleep(0.02)
        assert ready.exists()
        with pytest.raises(BusyError):
            with ResourceLock(runtime.data_dir / "locks", "cross-process"):
                pass
    finally:
        process.kill()
        process.communicate(timeout=5)
    with ResourceLock(runtime.data_dir / "locks", "cross-process"):
        pass


def test_cli_json_and_failure_exit(runtime):
    result = subprocess.run([sys.executable, "-m", "copilot", "--skills-root", str(runtime.skills_root),
                             "--data", str(runtime.data_dir), "run", "lookup_ace", "--", "--fail"],
                            stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
    assert result.returncode == 1
    assert json.loads(result.stdout)["exit_code"] == 7
