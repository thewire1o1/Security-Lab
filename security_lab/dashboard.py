from __future__ import annotations

import json
import os
import re
import shutil
import subprocess  # nosec B404 - required for fixed argv execution; shell invocation is not used.
import sys
import threading
import time
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from security_lab.common import ROOT, newest_directories, read_json
from security_lab.platform import api as platform_api

WEB = ROOT / "dashboard" / "web"
ACTIVITY = ROOT / "reports" / "dashboard-activity.log"
MAX_ACTION_BODY = 4096
COMPOSE = ("docker", "compose", "-f", str(ROOT / "lab" / "docker-compose.yml"))
PROJECT_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{1,62}$")
DPSR = str(ROOT / "bin" / "dpsr")
PLATFORM_CACHE_SECONDS = 4.0


@dataclass(frozen=True)
class Service:
    container: str
    port: int | None
    label: str


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


SERVICES = {
    "juice-shop": Service("dpsr-juice-shop", 3000, "Juice Shop"),
    "dvwa": Service("dpsr-dvwa", 8080, "DVWA"),
    "webgoat": Service("dpsr-webgoat", 8081, "WebGoat"),
    "kali": Service("dpsr-kali", None, "Kali Operator"),
}


class CommandRunner:
    @staticmethod
    def run(argv: list[str], timeout: float = 8) -> CommandResult:
        try:
            result = subprocess.run(  # nosec B603 - argv is preconstructed and never evaluated by a shell.
                argv,
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
            return CommandResult(result.returncode, result.stdout.strip(), result.stderr.strip())
        except subprocess.TimeoutExpired:
            return CommandResult(124, stderr=f"command timed out after {timeout} seconds")
        except OSError as exc:
            return CommandResult(126, stderr=str(exc))


class ActivityLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def write(self, message: str) -> None:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{stamp}] {message}\n")

    def tail(self, limit: int = 80) -> list[str]:
        try:
            return self.path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
        except OSError:
            return []


class ActionManager:
    def __init__(self, log: ActivityLog) -> None:
        self.log = log
        self._lock = threading.Lock()
        self._active: str | None = None

    @property
    def active(self) -> str | None:
        with self._lock:
            return self._active

    def submit(self, name: str, argv: tuple[str, ...]) -> bool:
        with self._lock:
            if self._active is not None:
                return False
            self._active = name
        threading.Thread(target=self._worker, args=(name, argv), daemon=True).start()
        return True

    def _worker(self, name: str, argv: tuple[str, ...]) -> None:
        self.log.write(f"ACTION {name}: started")
        try:
            process = subprocess.Popen(  # nosec B603 - argv is server-constructed and never evaluated by a shell.
                list(argv),
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            if process.stdout is not None:
                for raw_line in process.stdout:
                    line = raw_line.rstrip()
                    if line:
                        self.log.write(f"{name}: {line}")
            returncode = process.wait()
            self.log.write(f"ACTION {name}: finished rc={returncode}")
        except OSError as exc:
            self.log.write(f"ACTION {name}: failed: {exc}")
        finally:
            with self._lock:
                self._active = None


class DashboardState:
    def __init__(self, log: ActivityLog, actions: ActionManager) -> None:
        self.log = log
        self.actions = actions
        self._platform_lock = threading.Lock()
        self._platform_cached_at = 0.0
        self._platform_cache: dict[str, Any] = {}

    def payload(self) -> dict[str, Any]:
        stats = self._docker_stats()
        services: dict[str, dict[str, Any]] = {}
        for key, service in SERVICES.items():
            state = self._container_state(service.container)
            state.update(
                {
                    "label": service.label,
                    "port": service.port,
                    "stats": stats.get(service.container, {}),
                }
            )
            services[key] = state

        target_keys = ("juice-shop", "dvwa", "webgoat")
        online_targets = sum(bool(services[key]["running"]) for key in target_keys)
        pipeline = self._latest_json("defense-*", "pipeline.json")
        validation = self._latest_json("defense-*", "validation.json")
        return {
            "timestamp": int(time.time()),
            "lab": "online" if online_targets == 3 else ("partial" if online_targets else "offline"),
            "services": services,
            "engagements": self._count_dirs("engagements"),
            "cases": self._count_dirs("cases"),
            "history": self._scan_history(),
            "findings": self._finding_counts(),
            "tools": self._tool_presence(),
            "activity": self.log.tail(),
            "pipeline": pipeline,
            "validation": validation,
            "active_action": self.actions.active,
            "platform": self._platform_snapshot(),
            "control_plane": self._control_plane(),
        }

    def _platform_snapshot(self) -> dict[str, Any]:
        now = time.monotonic()
        with self._platform_lock:
            if self._platform_cache and now - self._platform_cached_at < PLATFORM_CACHE_SECONDS:
                return self._platform_cache
            try:
                snapshot = platform_api.snapshot(30)
                snapshot["error"] = None
            except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
                snapshot = {
                    "platform": "APOTHEON ONE",
                    "profiles": [],
                    "projects": [],
                    "jobs": [],
                    "counts": {"profiles": 0, "projects": 0, "jobs": 0},
                    "runners": {},
                    "error": str(exc),
                }
            self._platform_cache = snapshot
            self._platform_cached_at = now
            return snapshot

    @staticmethod
    def _control_plane() -> dict[str, dict[str, Any]]:
        commands = {
            "bridge": ["bash", str(ROOT / "bin" / "remote-agent"), "status"],
            "mcp": ["bash", str(ROOT / "bin" / "mcp-control"), "status"],
            "dashboard": ["bash", str(ROOT / "bin" / "dashboard-control"), "status"],
        }
        output: dict[str, dict[str, Any]] = {}
        for name, argv in commands.items():
            result = CommandRunner.run(argv, timeout=4)
            output[name] = {
                "running": result.returncode == 0,
                "status": result.stdout or result.stderr or "unknown",
            }
        return output

    @staticmethod
    def _container_state(name: str) -> dict[str, Any]:
        result = CommandRunner.run(["docker", "inspect", "-f", "{{json .State}}", name], timeout=3)
        if result.returncode or not result.stdout:
            return {"running": False, "status": "offline", "health": "unknown"}
        try:
            state = json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"running": False, "status": "unknown", "health": "unknown"}
        return {
            "running": bool(state.get("Running")),
            "status": state.get("Status", "unknown"),
            "health": (state.get("Health") or {}).get("Status", "n/a"),
            "started": state.get("StartedAt"),
        }

    @staticmethod
    def _docker_stats() -> dict[str, dict[str, str]]:
        result = CommandRunner.run(
            [
                "docker",
                "stats",
                "--no-stream",
                "--format",
                "{{json .}}",
                *(service.container for service in SERVICES.values()),
            ],
            timeout=5,
        )
        if result.returncode:
            return {}
        stats: dict[str, dict[str, str]] = {}
        for line in result.stdout.splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            name = str(row.get("Name") or "")
            if not name:
                continue
            stats[name] = {
                "cpu": str(row.get("CPUPerc") or "0%"),
                "memory": str(row.get("MemUsage") or "0B / 0B"),
                "memory_percent": str(row.get("MemPerc") or "0%"),
                "net": str(row.get("NetIO") or "0B / 0B"),
            }
        return stats

    @staticmethod
    def _count_dirs(name: str) -> int:
        base = ROOT / name
        if not base.exists():
            return 0
        return sum(path.is_dir() and not path.name.startswith(".") for path in base.iterdir())

    @staticmethod
    def _latest_json(pattern: str, filename: str) -> dict[str, Any]:
        for run_dir in newest_directories(ROOT / "reports", pattern):
            data = read_json(run_dir / filename, None)
            if isinstance(data, dict):
                return {**data, "_run": run_dir.name}
        return {}

    def _finding_counts(self) -> dict[str, int]:
        summary = self._latest_json("defense-*", "summary.json")
        severity = summary.get("severity")
        levels = ("critical", "high", "medium", "low", "info")
        if isinstance(severity, dict):
            return {level: int(severity.get(level, 0)) for level in levels}
        counts = {level: 0 for level in levels}
        scans = newest_directories(ROOT / "reports", "lab-*")
        if not scans:
            return counts
        path = scans[0] / "nuclei.txt"
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return counts
        for level in levels:
            counts[level] = len(re.findall(rf"\[{level}\]", text, flags=re.IGNORECASE))
        return counts

    @staticmethod
    def _scan_history(limit: int = 10) -> list[dict[str, Any]]:
        base = ROOT / "reports"
        if not base.exists():
            return []
        prefixes = ("lab-", "defense-", "fuzz-", "triage-")
        candidates = [path for path in base.iterdir() if path.is_dir() and path.name.startswith(prefixes)]
        candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return [
            {
                "name": path.name,
                "modified": int(path.stat().st_mtime),
                "files": sum(item.is_file() for item in path.rglob("*")),
            }
            for path in candidates[:limit]
        ]

    @staticmethod
    def _tool_presence() -> dict[str, bool]:
        tools = (
            "nmap",
            "nuclei",
            "httpx",
            "subfinder",
            "naabu",
            "semgrep",
            "bandit",
            "pip-audit",
            "trivy",
            "gitleaks",
            "ffuf",
            "yara",
            "radare2",
            "shellcheck",
        )
        return {tool: shutil.which(tool) is not None for tool in tools}


# Security boundary: browser input selects a key only; argv remains static and server-controlled.
ACTION_COMMANDS: dict[str, tuple[str, tuple[str, ...]]] = {
    "up": ("range-up", (*COMPOSE, "up", "-d", "juice-shop", "dvwa", "webgoat")),
    "down": ("range-down", (*COMPOSE, "--profile", "operator", "down")),
    "scan": ("range-scan", ("bash", str(ROOT / "bin" / "labscan"))),
    "report": ("report", ("python3", str(ROOT / "bin" / "sec-report"))),
    "kali-start": ("kali-start", (*COMPOSE, "--profile", "operator", "up", "-d", "kali")),
    "review": ("review", ("bash", str(ROOT / "bin" / "code-review"))),
    "validate": ("validate", ("bash", str(ROOT / "bin" / "validate-findings"))),
    "fuzz": ("fuzz", ("bash", str(ROOT / "bin" / "fuzz-run"))),
    "defend": ("defend", ("bash", str(ROOT / "bin" / "defense-run"))),
}


class Handler(SimpleHTTPRequestHandler):
    state: DashboardState
    actions: ActionManager

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB), **kwargs)

    def log_message(self, _format: str, *args: Any) -> None:
        return

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        )
        super().end_headers()

    def send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def request_origin_allowed(self) -> bool:
        if self.headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
            return False
        origin = self.headers.get("Origin")
        if not origin:
            return True
        host = self.headers.get("Host", "")
        parsed = urlparse(origin)
        return parsed.scheme in {"http", "https"} and bool(host) and parsed.netloc == host

    def _read_json_body(self) -> dict[str, Any] | None:
        if not self.request_origin_allowed():
            self.send_json({"error": "cross-origin request denied"}, 403)
            return None
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            self.send_json({"error": "application/json required"}, 415)
            return None
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            self.send_json({"error": "content length required"}, 411)
            return None
        try:
            length = int(raw_length)
        except ValueError:
            self.send_json({"error": "invalid content length"}, 400)
            return None
        if length < 1:
            self.send_json({"error": "empty request body"}, 400)
            return None
        if length > MAX_ACTION_BODY:
            self.send_json({"error": "request body too large"}, 413)
            return None
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_json({"error": "invalid json"}, 400)
            return None
        if not isinstance(payload, dict):
            self.send_json({"error": "invalid payload"}, 400)
            return None
        return payload

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/status":
            self.send_json(self.state.payload())
            return
        if path == "/api/activity":
            self.send_json({"activity": self.state.log.tail()})
            return
        if path == "/health":
            self.send_json({"ok": True, "platform": "APOTHEON ONE"})
            return
        super().do_GET()

    def _security_action(self, payload: dict[str, Any]) -> None:
        requested = payload.get("action")
        if not isinstance(requested, str):
            self.send_json({"error": "invalid payload"}, 400)
            return
        action = ACTION_COMMANDS.get(requested)
        if action is None:
            self.send_json({"error": "unsupported action"}, 400)
            return
        name, argv = action
        if not self.actions.submit(name, argv):
            self.send_json({"error": "another action is already running", "active": self.actions.active}, 409)
            return
        self.send_json({"ok": True, "action": requested}, 202)

    def _platform_action(self, payload: dict[str, Any]) -> None:
        operation = payload.get("operation")
        if not isinstance(operation, str):
            self.send_json({"error": "invalid platform operation"}, 400)
            return

        if operation == "create-project":
            name = str(payload.get("name") or "").strip().lower()
            profile = str(payload.get("profile") or "").strip()
            if not PROJECT_NAME.fullmatch(name):
                self.send_json({"error": "invalid project name"}, 400)
                return
            allowed_profiles = {str(row["name"]) for row in platform_api.profiles()}
            if profile not in allowed_profiles:
                self.send_json({"error": "unsupported profile"}, 400)
                return
            label = f"project-init:{name}"
            argv = (DPSR, "project", "init", name, "--profile", profile)
        elif operation == "publish-project":
            name = str(payload.get("project") or "").strip().lower()
            try:
                project = platform_api.project(name)
            except ValueError:
                self.send_json({"error": "unknown project"}, 404)
                return
            label = f"project-publish:{name}"
            argv = (DPSR, "project", "publish", str(project["name"]), "--visibility", "private")
        elif operation == "run-job":
            name = str(payload.get("project") or "").strip().lower()
            command = str(payload.get("command") or "").strip()
            try:
                project = platform_api.project(name)
            except ValueError:
                self.send_json({"error": "unknown project"}, 404)
                return
            commands = {str(item) for item in project.get("commands", [])}
            if command not in commands:
                self.send_json({"error": "unsupported project command"}, 400)
                return
            label = f"job:{name}:{command}"
            argv = (DPSR, "job", "run", str(project["name"]), command)
        else:
            self.send_json({"error": "unsupported platform operation"}, 400)
            return

        if not self.actions.submit(label, argv):
            self.send_json({"error": "another action is already running", "active": self.actions.active}, 409)
            return
        self.send_json({"ok": True, "operation": operation, "action": label}, 202)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in {"/api/action", "/api/platform/action"}:
            self.send_json({"error": "not found"}, 404)
            return
        payload = self._read_json_body()
        if payload is None:
            return
        if path == "/api/action":
            self._security_action(payload)
            return
        self._platform_action(payload)


def main() -> int:
    host = os.environ.get("SEC_DASHBOARD_HOST", "127.0.0.1")
    try:
        port = int(os.environ.get("SEC_DASHBOARD_PORT", "8765"))
    except ValueError:
        print("SEC_DASHBOARD_PORT must be an integer.", file=sys.stderr)
        return 2
    if not 1 <= port <= 65535:
        print("SEC_DASHBOARD_PORT must be between 1 and 65535.", file=sys.stderr)
        return 2

    activity = ActivityLog(ACTIVITY)
    actions = ActionManager(activity)
    state = DashboardState(activity, actions)
    Handler.state = state
    Handler.actions = actions

    try:
        with ThreadingHTTPServer((host, port), Handler) as server:
            activity.write(f"APOTHEON ONE Operations Console listening on http://{host}:{port}")
            print(f"APOTHEON ONE Operations Console: http://{host}:{port}")
            print("Keep the forwarded Codespaces port private. Ctrl-C to stop.")
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                return 0
    except OSError as exc:
        print(f"Unable to start APOTHEON ONE Operations Console: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
