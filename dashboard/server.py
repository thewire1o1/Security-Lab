#!/usr/bin/env python3
import json
import os
import re
import subprocess
import threading
import time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
WEB = Path(__file__).resolve().parent / "web"
PORT = int(os.environ.get("SEC_DASHBOARD_PORT", "8765"))
HOST = os.environ.get("SEC_DASHBOARD_HOST", "127.0.0.1")
COMPOSE = ["docker", "compose", "-f", str(ROOT / "lab" / "docker-compose.yml")]
ACTIVITY = ROOT / "reports" / "dashboard-activity.log"
ACTIVITY.parent.mkdir(parents=True, exist_ok=True)

SERVICES = {
    "juice-shop": {"container": "ai-lab-juice-shop", "port": 3000, "label": "Juice Shop"},
    "dvwa": {"container": "ai-lab-dvwa", "port": 8080, "label": "DVWA"},
    "webgoat": {"container": "ai-lab-webgoat", "port": 8081, "label": "WebGoat"},
    "kali": {"container": "ai-lab-kali", "port": None, "label": "Kali Operator"},
}


def log(message: str):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with ACTIVITY.open("a", encoding="utf-8") as fh:
        fh.write(f"[{stamp}] {message}\n")


def run(cmd, timeout=8):
    try:
        p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
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
    health = (state.get("Health") or {}).get("Status", "n/a")
    return {
        "running": bool(state.get("Running")),
        "status": state.get("Status", "unknown"),
        "health": health,
        "started": state.get("StartedAt"),
    }


def docker_stats():
    code, out, _ = run([
        "docker", "stats", "--no-stream",
        "--format", "{{json .}}",
        *[v["container"] for v in SERVICES.values()],
    ], timeout=5)
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
            pass
    return stats


def engagements():
    base = ROOT / "engagements"
    if not base.exists():
        return []
    return sorted([p.name for p in base.iterdir() if p.is_dir() and not p.name.startswith(".")])


def scan_history(limit=8):
    base = ROOT / "reports"
    if not base.exists():
        return []
    rows = []
    for p in sorted(base.glob("lab-*"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
        if p.is_dir():
            rows.append({"name": p.name, "modified": int(p.stat().st_mtime), "files": len(list(p.iterdir()))})
    return rows


def finding_counts():
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for path in (ROOT / "reports").glob("lab-*/nuclei.txt") if (ROOT / "reports").exists() else []:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for sev in counts:
            counts[sev] += len(re.findall(rf"\[{sev}\]", text, flags=re.I))
    return counts


def recent_activity(limit=50):
    if not ACTIVITY.exists():
        return []
    try:
        return ACTIVITY.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]
    except OSError:
        return []


def tool_presence():
    tools = ["nmap", "nuclei", "httpx", "subfinder", "naabu", "semgrep", "trivy", "gitleaks", "codex"]
    result = {}
    for tool in tools:
        code, out, _ = run(["bash", "-lc", f"command -v {tool} || true"], timeout=2)
        result[tool] = bool(out.strip()) and code == 0
    return result


def status_payload():
    stats = docker_stats()
    svc = {}
    for key, meta in SERVICES.items():
        state = container_state(meta["container"])
        state.update({
            "label": meta["label"],
            "port": meta["port"],
            "stats": stats.get(meta["container"], {}),
        })
        svc[key] = state
    online_targets = sum(1 for k in ("juice-shop", "dvwa", "webgoat") if svc[k]["running"])
    return {
        "timestamp": int(time.time()),
        "lab": "online" if online_targets == 3 else ("partial" if online_targets else "offline"),
        "services": svc,
        "engagements": engagements(),
        "history": scan_history(),
        "findings": finding_counts(),
        "tools": tool_presence(),
        "activity": recent_activity(),
    }


def background(name, cmd):
    def worker():
        log(f"ACTION {name}: started")
        try:
            proc = subprocess.Popen(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if proc.stdout:
                for line in proc.stdout:
                    line = line.rstrip()
                    if line:
                        log(f"{name}: {line}")
            rc = proc.wait()
            log(f"ACTION {name}: finished rc={rc}")
        except Exception as exc:
            log(f"ACTION {name}: failed: {exc}")
    threading.Thread(target=worker, daemon=True).start()


ACTIONS = {
    "up": lambda: background("lab-up", COMPOSE + ["up", "-d", "juice-shop", "dvwa", "webgoat"]),
    "down": lambda: background("lab-down", COMPOSE + ["--profile", "operator", "down"]),
    "scan": lambda: background("lab-scan", ["bash", str(ROOT / "bin" / "labscan")]),
    "report": lambda: background("report", ["python3", str(ROOT / "bin" / "sec-report")]),
    "kali-start": lambda: background("kali-start", COMPOSE + ["--profile", "operator", "up", "-d", "kali"]),
}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def log_message(self, fmt, *args):
        return

    def send_json(self, payload, code=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self.send_json({"error": "invalid json"}, 400)
            return
        action = payload.get("action")
        fn = ACTIONS.get(action)
        if not fn:
            self.send_json({"error": "unsupported action"}, 400)
            return
        fn()
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
