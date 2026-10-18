"""Serve the model panel on loopback and run one background operation at a time."""
from __future__ import annotations

import argparse
import json
import logging
import secrets
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .control import ModelControl, ControlError
from .api_profiles import ApiProfiles
from . import logs as panel_logs
from . import stats as panel_stats

log = logging.getLogger(__name__)


class Jobs:
    def __init__(self, control):
        self.control = control
        self.lock = threading.Lock()
        self.job = None

    def snapshot(self):
        with self.lock:
            return dict(self.job) if self.job else None

    def submit(self, action, model):
        if action not in {"start", "restart", "warm", "switch", "api_save", "api_delete", "api_balance", "api_switch"}:
            raise ValueError("请选择启动、重启、加载或切换操作")
        if action == "api_save" and not isinstance(model, dict):
            raise ValueError("接口配置无效")
        if action not in {"start", "restart", "api_save"} and (not isinstance(model, str) or not model.strip()):
            raise ValueError("请先选择一个模型")
        with self.lock:
            if self.job and self.job["state"] == "running":
                raise RuntimeError("正在处理上一项操作，请等待结果")
            self.job = {"action": action, "model": model.get("name", "接口") if isinstance(model, dict) else model, "state": "running", "message": "正在处理…"}
        threading.Thread(target=self._run, args=(action, model), daemon=True).start()
        return self.snapshot()

    def _run(self, action, model):
        try:
            if action.startswith("api_"):
                registry = ApiProfiles(self.control)
                if action == "api_switch":
                    with self.control.lock:
                        profile = registry.selection(model)
                        result = self.control.switch(profile["model"], api=profile)
                else:
                    fn = getattr(registry, action.removeprefix("api_"))
                    result = fn(model)
            else:
                fn = getattr(self.control, action)
                result = fn() if action in {"start", "restart"} else fn(model)
            state = "completed" if result.get("ok") else "failed"
            message = result.get("message", "操作完成" if state == "completed" else "操作失败")
        except Exception as exc:
            state = "failed"
            message = str(exc) if isinstance(exc, (ControlError, ValueError)) else "操作失败，请检查配置和本地日志。"
            log.warning("Model operation %s failed: %s", action, type(exc).__name__)
        with self.lock:
            self.job.update(state=state, message=message)


def create_server(control, port=8767):
    token = secrets.token_urlsafe(32)
    jobs = Jobs(control)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            log.debug(fmt, *args)

        def send(self, code, value, content_type="application/json; charset=utf-8"):
            data = value.encode("utf-8") if isinstance(value, str) else json.dumps(value, ensure_ascii=False).encode("utf-8")
            try:
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.end_headers()
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                self.close_connection = True
                log.debug("Browser closed a panel request before its response completed")

        def valid_host(self):
            port = self.server.server_address[1]
            return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

        def do_GET(self):
            if not self.valid_host():
                self.send(403, {"error": "请从本机地址打开页面"})
                return
            if self.path == "/":
                page = (Path(__file__).parent / "static/index.html").read_text(encoding="utf-8")
                self.send(200, page.replace("__PANEL_TOKEN__", token), "text/html; charset=utf-8")
            elif self.path == "/api/health":
                self.send(200, {"app": "channels-panel", "home": str(control.home)})
            elif self.path == "/api/stats" or self.path.startswith("/api/stats?"):
                # the counts never name a chat, but they come from the conversations, so they need the token too
                range_ = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("range", ["day"])[0]
                if self.headers.get("X-Panel-Token") != token:
                    self.send(403, {"error": "页面已失效，请刷新后重试"})
                elif range_ not in ("day", "month"):
                    self.send(400, {"error": "时间范围只能按天或按月"})
                else:
                    self.send(200, panel_stats.report(control.data_dir(), range_))
            elif self.path == "/api/logs" or self.path.startswith("/api/logs/"):
                self.send_log()
            elif self.path == "/api/status":
                try:
                    self.send(200, {"status": control.status(), "job": jobs.snapshot()})
                except Exception as exc:
                    self.send(500, {"error": str(exc), "job": jobs.snapshot()})
            else:
                self.send(404, {"error": "页面不存在"})

        def send_log(self):
            # Logs hold conversations, so reading them needs the page token as well as the loopback Host.
            if self.headers.get("X-Panel-Token") != token:
                self.send(403, {"error": "页面已失效，请刷新后重试"})
                return
            url = urllib.parse.urlsplit(self.path)
            ident = url.path.removeprefix("/api/logs").removeprefix("/")
            if not ident:
                self.send(200, {"logs": panel_logs.catalog(control)})
                return
            after = urllib.parse.parse_qs(url.query).get("after", [None])[-1]
            try:
                after = int(after) if after is not None else None
            except ValueError:
                self.send(400, {"error": "日志位置无效"})
                return
            try:
                self.send(200, panel_logs.read(control, ident, after))
            except KeyError:
                self.send(404, {"error": "没有这个日志"})

        def do_POST(self):
            if not self.valid_host() or self.headers.get("X-Panel-Token") != token:
                self.send(403, {"error": "页面已失效，请刷新后重试"})
                return
            if self.path != "/api/action":
                self.send(404, {"error": "操作不存在"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size <= 0 or size > 16384:
                    raise ValueError("操作参数无效")
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError("操作参数必须是对象")
                job = jobs.submit(body.get("action"), body.get("model"))
                self.send(202, {"job": job})
            except (ValueError, TypeError) as exc:
                self.send(400, {"error": str(exc)})
            except RuntimeError as exc:
                self.send(409, {"error": str(exc)})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path(__file__).resolve().parents[1], help="the channels folder")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--open", action="store_true", help="open the panel in the default browser")
    parser.add_argument("--start-ollama", action="store_true", help="start the configured service and exit")
    args = parser.parse_args()
    home = args.home.resolve()
    logs = home / "var/logs/models"
    logs.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=logs / "panel.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    control = ModelControl(home)
    if args.start_ollama:
        result = control.start()
        if sys.stdout:
            print(result.get("message", ""))
        return 0 if result.get("ok") else 1
    url = f"http://127.0.0.1:{args.port}"
    try:
        server = create_server(control, args.port)
    except OSError:
        with urllib.request.urlopen(url + "/api/health", timeout=3) as response:
            existing = json.load(response)
        if existing.get("app") != "channels-panel" or Path(existing.get("home", "")).resolve() != home:
            raise RuntimeError("端口被其他程序占用，请使用 --port 指定其他端口")
        if args.open:
            webbrowser.open(url)
        return 0
    if args.open:
        webbrowser.open(url)
    log.info("Model panel listening at %s", url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
