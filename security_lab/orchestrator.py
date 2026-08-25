from __future__ import annotations

import json
import subprocess  # nosec B404 - fixed argv execution only; shell evaluation is never used.
import threading
import time
from http.server import SimpleHTTPRequestHandler
from typing import Any
from urllib.parse import urlparse

from security_lab import dashboard as base
from security_lab.common import ROOT


TARGETS: dict[str, dict[str, Any]] = {
    "lab": {
        "label": "Entire Training Lab",
        "short": "Local Lab",
        "kind": "training range",
        "description": "All three intentionally vulnerable web applications running inside the isolated APOTHEON training lab.",
        "technical": "Juice Shop :3000, DVWA :8080, WebGoat :8081",
    },
    "juice-shop": {
        "label": "OWASP Juice Shop",
        "short": "Juice Shop",
        "kind": "training web app",
        "description": "An intentionally vulnerable online store used to safely practice and demonstrate web application security testing.",
        "technical": "OWASP Juice Shop on local port 3000",
        "service": "juice-shop",
    },
    "dvwa": {
        "label": "Vulnerable Web App",
        "short": "DVWA",
        "kind": "training web app",
        "description": "An intentionally vulnerable web application designed for safe, controlled security testing and training.",
        "technical": "Damn Vulnerable Web Application on local port 8080",
        "service": "dvwa",
    },
    "webgoat": {
        "label": "OWASP WebGoat",
        "short": "WebGoat",
        "kind": "training web app",
        "description": "An intentionally insecure application that teaches common web vulnerabilities through guided exercises.",
        "technical": "OWASP WebGoat on local port 8081",
        "service": "webgoat",
    },
}

PROFILES: dict[str, dict[str, Any]] = {
    "quick": {
        "label": "Quick Check",
        "description": "Confirm the target is reachable, identify exposed services, and inspect its web response.",
        "technical": "Nmap service detection plus HTTP header inspection",
        "tools": ["nmap", "curl"],
    },
    "standard": {
        "label": "Standard Security Check",
        "description": "Discover services, inspect the web application, check known vulnerability patterns, and organize the results.",
        "technical": "Nmap service detection, HTTP inspection, and Nuclei vulnerability templates",
        "tools": ["nmap", "curl", "nuclei"],
    },
    "deep": {
        "label": "Deep Security Check",
        "description": "Run broader service inspection and vulnerability checks for a more complete lab assessment.",
        "technical": "Nmap default scripts and service detection plus Nuclei vulnerability templates",
        "tools": ["nmap", "curl", "nuclei"],
    },
}

TOOLS: dict[str, dict[str, str]] = {
    "nmap": {"label": "Network Discovery", "description": "Finds reachable network services and identifies what is listening.", "technical": "Nmap"},
    "nuclei": {"label": "Web Vulnerability Checks", "description": "Checks a web target against known security patterns and misconfigurations.", "technical": "Nuclei"},
    "httpx": {"label": "Web Service Inspection", "description": "Identifies live web services and collects useful HTTP details.", "technical": "httpx"},
    "subfinder": {"label": "Subdomain Discovery", "description": "Finds known subdomains that belong to an authorized domain scope.", "technical": "Subfinder"},
    "naabu": {"label": "Port Discovery", "description": "Quickly identifies network ports that are accepting connections.", "technical": "Naabu"},
    "semgrep": {"label": "Source Code Analysis", "description": "Reviews source code for risky patterns and security mistakes.", "technical": "Semgrep"},
    "bandit": {"label": "Python Security Review", "description": "Checks Python source code for common security problems.", "technical": "Bandit"},
    "pip-audit": {"label": "Dependency Vulnerability Check", "description": "Checks installed Python dependencies for known vulnerabilities.", "technical": "pip-audit"},
    "trivy": {"label": "Container & Dependency Scan", "description": "Checks containers, packages, and project dependencies for known vulnerabilities.", "technical": "Trivy"},
    "gitleaks": {"label": "Secret Detection", "description": "Looks for passwords, tokens, keys, and other secrets accidentally stored in source code.", "technical": "Gitleaks"},
    "ffuf": {"label": "Content Discovery", "description": "Discovers hidden or unlinked web paths within an authorized target.", "technical": "ffuf"},
    "yara": {"label": "File Pattern Analysis", "description": "Matches files and data against known detection patterns.", "technical": "YARA"},
    "radare2": {"label": "Binary Analysis", "description": "Inspects compiled programs and firmware at a low level.", "technical": "radare2"},
    "shellcheck": {"label": "Shell Script Review", "description": "Finds mistakes and unsafe patterns in shell scripts.", "technical": "ShellCheck"},
}

CATALOG = {
    "targets": TARGETS,
    "profiles": PROFILES,
    "tools": TOOLS,
    "principle": "Choose a target, choose an outcome, watch the work, understand the result.",
}


def _generic_metadata(name: str) -> dict[str, Any]:
    rows = (
        ("range-up", "Starting Training Lab", "Local training lab", "Starts the intentionally vulnerable practice applications."),
        ("range-down", "Stopping Training Lab", "Local training lab", "Stops the local practice applications."),
        ("report", "Building Security Report", "Current evidence", "Collects the latest security evidence into a report."),
        ("review", "Reviewing Source Code", "Repository", "Checks source code for security and quality problems."),
        ("validate", "Validating Findings", "Current findings", "Re-checks findings to separate confirmed issues from noise."),
        ("fuzz", "Running Input Testing", "Authorized lab scope", "Exercises application inputs to find unexpected behavior."),
        ("defend", "Running Defensive Review", "Repository and lab", "Runs the defensive analysis pipeline and organizes findings."),
        ("kali-start", "Starting Security Workstation", "Kali Operator", "Starts the isolated Kali security workstation."),
        ("project-init:", "Creating Project", "Development workspace", "Creates a project from the selected starter profile."),
        ("project-publish:", "Publishing Project", "Private repository", "Publishes the selected project as a private repository."),
        ("job:", "Running Project Automation", "Development project", "Runs the selected project command and tracks its completion."),
    )
    for prefix, title, target, description in rows:
        if name == prefix or name.startswith(prefix):
            return {"title": title, "target_label": target, "description": description, "action": name}
    return {"title": "Running Automation", "target_label": "APOTHEON ONE", "description": "Runs the selected automation and tracks its completion.", "action": name}


def _scan_stages(profile: str) -> list[dict[str, str]]:
    return [
        {"id": "scope", "title": "Confirm target", "detail": "Lock the run to the selected local training target.", "state": "pending"},
        {"id": "discover", "title": "Discover services", "detail": "Network Discovery identifies reachable services with Nmap.", "state": "pending"},
        {"id": "inspect", "title": "Inspect application", "detail": "Read the target web response and collect basic application details.", "state": "pending"},
        {"id": "weakness", "title": "Check security weaknesses", "detail": "Web Vulnerability Checks use Nuclei when the selected profile includes them.", "state": "pending" if profile != "quick" else "skipped"},
        {"id": "summarize", "title": "Organize results", "detail": "Save the evidence and make the run available in APOTHEON history.", "state": "pending"},
    ]


class OrchestratorActionManager(base.ActionManager):
    def __init__(self, log: base.ActivityLog) -> None:
        super().__init__(log)
        self._run_lock = threading.Lock()
        self._run: dict[str, Any] | None = None
        self._sequence = 0

    def snapshot(self) -> dict[str, Any] | None:
        with self._run_lock:
            if self._run is None:
                return None
            return json.loads(json.dumps(self._run))

    def submit(self, name: str, argv: tuple[str, ...]) -> bool:
        metadata = _generic_metadata(name)
        stages = [{"id": "execute", "title": metadata["title"], "detail": metadata["description"], "state": "pending"}]
        return self.submit_run(name, argv, metadata, stages)

    def submit_run(
        self,
        name: str,
        argv: tuple[str, ...],
        metadata: dict[str, Any],
        stages: list[dict[str, str]],
    ) -> bool:
        with self._lock:
            if self._active is not None:
                return False
            self._active = name
        with self._run_lock:
            self._sequence += 1
            run_id = f"run-{int(time.time())}-{self._sequence}"
            self._run = {
                "id": run_id,
                "name": name,
                "state": "queued",
                "started_at": int(time.time()),
                "finished_at": None,
                "progress": 0,
                "current_stage": None,
                "technical_tail": [],
                "stages": [dict(stage) for stage in stages],
                **metadata,
            }
        threading.Thread(target=self._worker_run, args=(name, argv), daemon=True).start()
        return True

    def _set_run_state(self, state: str, **updates: Any) -> None:
        with self._run_lock:
            if self._run is None:
                return
            self._run["state"] = state
            self._run.update(updates)
            self._recalculate_progress_locked()

    def _append_technical(self, line: str) -> None:
        with self._run_lock:
            if self._run is None:
                return
            tail = self._run.setdefault("technical_tail", [])
            tail.append(line[:500])
            del tail[:-24]

    def _apply_stage(self, stage_id: str, state: str, title: str, detail: str) -> None:
        with self._run_lock:
            if self._run is None:
                return
            stages = self._run.get("stages", [])
            for stage in stages:
                if stage.get("id") == stage_id:
                    stage.update({"state": state, "title": title or stage.get("title"), "detail": detail or stage.get("detail")})
                    break
            if state == "running":
                self._run["current_stage"] = stage_id
            self._recalculate_progress_locked()

    def _recalculate_progress_locked(self) -> None:
        if self._run is None:
            return
        stages = self._run.get("stages", [])
        if not stages:
            self._run["progress"] = 0
            return
        complete = sum(stage.get("state") in {"completed", "skipped"} for stage in stages)
        running = any(stage.get("state") == "running" for stage in stages)
        value = (complete + (0.45 if running else 0.0)) / len(stages) * 100
        if self._run.get("state") in {"succeeded", "failed"}:
            value = 100
        self._run["progress"] = max(0, min(100, round(value)))

    def _worker_run(self, name: str, argv: tuple[str, ...]) -> None:
        self.log.write(f"ACTION {name}: started")
        self._set_run_state("running")
        with self._run_lock:
            if self._run and self._run.get("stages"):
                first = self._run["stages"][0]
                if first.get("state") == "pending":
                    first["state"] = "running"
                    self._run["current_stage"] = first.get("id")
                self._recalculate_progress_locked()
        returncode = 126
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
                    if not line:
                        continue
                    if line.startswith("APOTHEON_STAGE|"):
                        parts = line.split("|", 4)
                        if len(parts) == 5:
                            _, stage_id, state, title, detail = parts
                            self._apply_stage(stage_id, state, title, detail)
                            continue
                    self._append_technical(line)
                    self.log.write(f"{name}: {line}")
            returncode = process.wait()
            self.log.write(f"ACTION {name}: finished rc={returncode}")
        except OSError as exc:
            self._append_technical(str(exc))
            self.log.write(f"ACTION {name}: failed: {exc}")
        finally:
            final_state = "succeeded" if returncode == 0 else "failed"
            with self._run_lock:
                if self._run is not None:
                    for stage in self._run.get("stages", []):
                        if stage.get("state") == "running":
                            stage["state"] = "completed" if returncode == 0 else "failed"
                        elif stage.get("state") == "pending" and returncode == 0:
                            stage["state"] = "completed"
                    self._run["state"] = final_state
                    self._run["finished_at"] = int(time.time())
                    self._run["current_stage"] = None
                    self._run["summary"] = "Automation completed successfully." if returncode == 0 else f"Automation stopped with exit code {returncode}."
                    self._recalculate_progress_locked()
            with self._lock:
                self._active = None


class OrchestratorDashboardState(base.DashboardState):
    def payload(self) -> dict[str, Any]:
        payload = super().payload()
        payload["orchestrator"] = CATALOG
        payload["run"] = self.actions.snapshot() if isinstance(self.actions, OrchestratorActionManager) else None
        services = payload.get("services", {})
        for key, target in TARGETS.items():
            if key in services:
                services[key]["description"] = target["description"]
                services[key]["technical"] = target["technical"]
                services[key]["friendly_label"] = target["label"]
        return payload


class OrchestratorHandler(base.Handler):
    actions: OrchestratorActionManager

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; script-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        )
        SimpleHTTPRequestHandler.end_headers(self)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/catalog":
            self.send_json(CATALOG)
            return
        if path == "/api/run":
            self.send_json({"run": self.actions.snapshot()})
            return
        super().do_GET()

    def _security_action(self, payload: dict[str, Any]) -> None:
        requested = payload.get("action")
        if requested != "scan":
            super()._security_action(payload)
            return

        target = str(payload.get("target") or "lab").strip().lower()
        profile = str(payload.get("profile") or "standard").strip().lower()
        if target not in TARGETS:
            self.send_json({"error": "unsupported scan target"}, 400)
            return
        if profile not in PROFILES:
            self.send_json({"error": "unsupported scan profile"}, 400)
            return

        target_row = TARGETS[target]
        profile_row = PROFILES[profile]
        label = f"scan:{target}:{profile}"
        argv = ("bash", str(ROOT / "bin" / "labscan"), target, profile)
        metadata = {
            "action": "scan",
            "title": f"Scanning {target_row['label']}",
            "target": target,
            "target_label": target_row["label"],
            "profile": profile,
            "profile_label": profile_row["label"],
            "description": profile_row["description"],
            "technical": profile_row["technical"],
            "tools": profile_row["tools"],
        }
        if not self.actions.submit_run(label, argv, metadata, _scan_stages(profile)):
            self.send_json({"error": "another action is already running", "active": self.actions.active}, 409)
            return
        self.send_json({"ok": True, "action": "scan", "target": target, "profile": profile, "run": self.actions.snapshot()}, 202)


def main() -> int:
    base.ActionManager = OrchestratorActionManager
    base.DashboardState = OrchestratorDashboardState
    base.Handler = OrchestratorHandler
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
