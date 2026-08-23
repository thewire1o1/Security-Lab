#!/usr/bin/env python3
import json
import os
import re
import shutil
import subprocess  # nosec B404
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
WEB = Path(__file__).resolve().parent / "web"
PORT = int(os.environ.get("SEC_DASHBOARD_PORT", "8765"))
HOST = os.environ.get("SEC_DASHBOARD_HOST", "127.0.0.1")
MAX_ACTION_BODY = 4096
COMPOSE = ["docker", "compose", "-f", str(ROOT / "lab" / "docker-compose.yml")]
ACTIVITY = ROOT / "reports" / "dashboard-activity.log"
ACTIVITY.parent.mkdir(parents=True, exist_ok=True)
ACTION_LOCK = threading.Lock()
ACTIVE_ACTION = None

SERVICES = {
    "juice-shop": {"container": "sec-lab-juice-shop", "port": 3000, "label": "Juice Shop"},
    "dvwa": {"container": "sec-lab-dvwa", "port": 8080, "label": "DVWA"},
    "webgoat": {"container": "sec-lab-webgoat", "port": 8081, "label": "WebGoat"},
    "kali": {"container": "sec-lab-kali", "port": None, "label": "Kali Operator"},
}


def log(message):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with ACTIVITY.open("a", encoding="utf-8") as fh:
        fh.write(f"[{stamp}] {message}\n")


def run(cmd, timeout=8):
    try:
        p = subprocess.run(  # nosec B603
            cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout
        )
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except Exception as exc:
        return 1, "", str(exc)


def container_state(name):
    code, out, _ = run(["docker", "inspect", "-f", "{{json .State}}", name], timeout=3)
    if code or not out:
        return {"running": False, "status": "offline", "health": "unknown"}
    try:
        state = json.loads(out)
    except json.JSONDecodeError:
        return {"running": False, "status": "unknown", "health": "unknown"}
    return {
        "running": bool(state.get("Running")),
        "status": state.get("Status", "unknown"),
        "health": (state.get("Health") or {}).get("Status", "n/a"),
        "started": state.get("StartedAt"),
    }


def docker_stats():
    code, out, _ = run(
        [
            "docker",
            "stats",
            "--no-stream",
            "--format",
            "{{json .}}",
            *[v["container"] for v in SERVICES.values()],
        ],
        timeout=5,
    )
    stats = {}
    if code:
        return stats
    for line in out.splitlines():
        try:
            row = json.loads(line)
            stats[row.get("Name", "")] = {
                "cpu": row.get("CPUPerc", "0%"),
                "memory": row.get("MemUsage", "0B / 0B"),
                "memory_percent": row.get("MemPerc", "0%"),
                "net": row.get("NetIO", "0B / 0B"),
            }
        except json.JSONDecodeError:
            continue
    return stats


def count_dirs(name):
    base = ROOT / name
    if not base.exists():
        return 0
    return sum(1 for p in base.iterdir() if p.is_dir() and not p.name.startswith("."))


def latest_json(pattern, filename):
    base = ROOT / "reports"
    if not base.exists():
        return {}
    runs = [p for p in base.glob(pattern) if p.is_dir()]
    runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for run_dir in runs:
        path = run_dir / filename
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data["_run"] = run_dir.name
                return data
            except (OSError, json.JSONDecodeError):
                continue
    return {}


def finding_counts():
    summary = latest_json("defense-*", "summary.json")
    sev = summary.get("severity")
    if isinstance(sev, dict):
        return {k: int(sev.get(k, 0)) for k in ("critical", "high", "medium", "low", "info")}
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    base = ROOT / "reports"
    if not base.exists():
        return counts
    paths = sorted(base.glob("lab-*/nuclei.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not paths:
        return counts
    text = paths[0].read_text(encoding="utf-8", errors="ignore")
    for sev_name in counts:
        counts[sev_name] = len(re.findall(rf"\[{sev_name}\]", text, flags=re.I))
    return counts


def scan_history(limit=10):
    base = ROOT / "reports"
    if not base.exists():
        return []
    prefixes = ("lab-", "defense-", "fuzz-", "triage-")
    rows = []
    for p in sorted(base.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not p.is_dir() or not p.name.startswith(prefixes):
            continue
        rows.append(
            {
                "name": p.name,
                "modified": int(p.stat().st_mtime),
                "files": sum(1 for x in p.rglob("*") if x.is_file()),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def recent_activity(limit=60):
    if not ACTIVITY.exists():
        return []
    try:
        return ACTIVITY.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]
    except OSError:
        return []


def tool_presence():
    tools = [
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
    ]
    return {tool: shutil.which(tool) is not None for tool in tools}


def current_action():
    with ACTION_LOCK:
        return ACTIVE_ACTION


def status_payload():
    stats = docker_stats()
    services = {}
    for key, meta in SERVICES.items():
        state = container_state(meta["container"])
        state.update(
            {
                "label": meta["label"],
                "port": meta["port"],
                "stats": stats.get(meta["container"], {}),
            }
        )
        services[key] = state
    online_targets = sum(1 for key in ("juice-shop", "dvwa", "webgoat") if services[key]["running"])
    pipeline = latest_json("defense-*", "pipeline.json")
    validation = latest_json("defense-*", "validation.json")
    return {
        "timestamp": int(time.time()),
        "lab": "online" if online_targets == 3 else ("partial" if online_targets else "offline"),
        "services": services,
        "engagements": count_dirs("engagements"),
        "cases": count_dirs("cases"),
        "history": scan_history(),
        "findings": finding_counts(),
        "tools": tool_presence(),
        "activity": recent_activity(),
        "pipeline": pipeline,
        "validation": validation,
        "active_action": current_action(),
    }


def background(name, cmd):
    global ACTIVE_ACTION
    with ACTION_LOCK:
        if ACTIVE_ACTION is not None:
            return False
        ACTIVE_ACTION = name

    def worker():
        global ACTIVE_ACTION
        log(f"ACTION {name}: started")
        try:
            proc = subprocess.Popen(  # nosec B603
                cmd,
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            if proc.stdout:
                for line in proc.stdout:
                    line = line.rstrip()
                    if line:
                        log(f"{name}: {line}")
            rc = proc.wait()
            log(f"ACTION {name}: finished rc={rc}")
        except Exception as exc:
            log(f"ACTION {name}: failed: {exc}")
        finally:
            with ACTION_LOCK:
                ACTIVE_ACTION = None

    threading.Thread(target=worker, daemon=True).start()
    return True


ACTIONS = {
    "up": lambda: background("lab-up", COMPOSE + ["up", "-d", "juice-shop", "dvwa", "webgoat"]),
    "down": lambda: background("lab-down", COMPOSE + ["--profile", "operator", "down"]),
    "scan": lambda: background("lab-scan", ["bash", str(ROOT / "bin" / "labscan")]),
    "report": lambda: background("report", ["python3", str(ROOT / "bin" / "sec-report")]),
    "kali-start": lambda: background("kali-start", COMPOSE + ["--profile", "operator", "up", "-d", "kali"]),
    "review": lambda: background("review", ["bash", str(ROOT / "bin" / "code-review")]),
    "validate": lambda: background("validate", ["bash", str(ROOT / "bin" / "validate-findings")]),
    "fuzz": lambda: background("fuzz", ["bash", str(ROOT / "bin" / "fuzz-run")]),
    "defend": lambda: background("defend", ["bash", str(ROOT / "bin" / "defense-run")]),
}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def log_message(self, fmt, *args):
        return

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'",
        )
        super().end_headers()

    def send_json(self, payload, code=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def request_origin_allowed(self):
        site = self.headers.get("Sec-Fetch-Site", "").lower()
        if site == "cross-site":
            return False
        origin = self.headers.get("Origin")
        if not origin:
            return True
        host = self.headers.get("Host", "")
        parsed = urlparse(origin)
        return parsed.scheme in ("http", "https") and bool(host) and parsed.netloc == host

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/status":
            self.send_json(status_payload())
            return
        if path == "/api/activity":
            self.send_json({"activity": recent_activity()})
            return
        if path == "/health":
            self.send_json({"ok": True})
            return
        super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/action":
            self.send_json({"error": "not found"}, 404)
            return
        if not self.request_origin_allowed():
            self.send_json({"error": "cross-origin request denied"}, 403)
            return
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            self.send_json({"error": "application/json required"}, 415)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json({"error": "invalid content length"}, 400)
            return
        if length < 1 or length > MAX_ACTION_BODY:
            self.send_json({"error": "request body too large"}, 413)
            return
        try:
            payload = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            self.send_json({"error": "invalid json"}, 400)
            return
        if not isinstance(payload, dict):
            self.send_json({"error": "invalid payload"}, 400)
            return
        action = payload.get("action")
        fn = ACTIONS.get(action)
        if not fn:
            self.send_json({"error": "unsupported action"}, 400)
            return
        if not fn():
            self.send_json({"error": "another action is already running", "active": current_action()}, 409)
            return
        self.send_json({"ok": True, "action": action}, 202)


def main():
    log(f"Mission Control listening on http://{HOST}:{PORT}")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Mission Control: http://{HOST}:{PORT}")
    print("Keep the forwarded Codespaces port private. Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
