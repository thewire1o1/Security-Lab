from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shutil
import signal
import subprocess  # nosec B404
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from security_lab.common import ROOT, utc_timestamp

API_BASE: Final = "https://api.github.com"
DEFAULT_REPO: Final = "thewire1o1/Security-Lab"
DEFAULT_OWNER: Final = "thewire1o1"
TITLE_PREFIX: Final = "[LAB-CMD]"
MAX_RESULT_BYTES: Final = 12_000
TOKEN_PATTERN: Final = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b",
    re.IGNORECASE,
)
TASK_PATTERN: Final = re.compile(r"^task:[ \t]*([a-z0-9-]+)[ \t]*$", re.MULTILINE)


class GitHubError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    root: Path = ROOT
    repo: str = os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPO)
    owner: str = os.environ.get("SEC_REMOTE_OWNER", DEFAULT_OWNER)
    poll_seconds: float = float(os.environ.get("SEC_REMOTE_POLL_SECONDS", "8"))

    @property
    def reports(self) -> Path:
        return self.root / "reports"

    @property
    def pidfile(self) -> Path:
        return self.root / ".remote-agent.pid"

    @property
    def lockfile(self) -> Path:
        return self.root / ".remote-agent.lock"

    @property
    def logfile(self) -> Path:
        return self.reports / "remote-agent.log"


class GitHubClient:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._token: str | None = None

    def resolve_token(self) -> str:
        if self._token:
            return self._token

        explicit = os.environ.get("SEC_GITHUB_TOKEN", "").strip()
        if explicit:
            self._token = explicit
            return explicit

        gh_token = self._token_from_gh()
        if gh_token:
            self._token = gh_token
            return gh_token

        for variable in ("GH_TOKEN", "GITHUB_TOKEN"):
            value = os.environ.get(variable, "").strip()
            if value:
                self._token = value
                return value

        credential = self._token_from_git_credential()
        if credential:
            self._token = credential
            return credential

        raise GitHubError("GitHub authentication is unavailable.")

    def _token_from_gh(self) -> str:
        if shutil.which("gh") is None:
            return ""
        env = os.environ.copy()
        env.pop("GH_TOKEN", None)
        env.pop("GITHUB_TOKEN", None)
        try:
            result = subprocess.run(  # nosec B603
                ["gh", "auth", "token", "--hostname", "github.com"],
                cwd=self.config.root,
                env=env,
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return result.stdout.strip() if result.returncode == 0 else ""

    def _token_from_git_credential(self) -> str:
        request = "protocol=https\nhost=github.com\n\n"
        try:
            result = subprocess.run(  # nosec B603
                ["git", "credential", "fill"],
                cwd=self.config.root,
                input=request,
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
        except (OSError, subprocess.TimeoutExpired):
            return ""
        if result.returncode != 0:
            return ""
        for line in result.stdout.splitlines():
            if line.startswith("password="):
                return line.partition("=")[2].strip()
        return ""

    def request(self, method: str, path: str, payload: Any | None = None) -> Any:
        token = self.resolve_token()
        body = None
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "security-lab-remote-agent",
        }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            f"{API_BASE}{path}", data=body, headers=headers, method=method.upper()
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise GitHubError(f"GitHub API returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise GitHubError(f"GitHub API request failed: {exc.reason}") from exc

        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GitHubError("GitHub API returned invalid JSON.") from exc


@dataclass(frozen=True)
class TaskSpec:
    argv: tuple[str, ...]
    timeout: float | None = None


class TaskRunner:
    def __init__(self, config: Config, client: GitHubClient) -> None:
        self.config = config
        self.client = client
        root = str(config.root)
        self.specs: dict[str, TaskSpec] = {
            "doctor": TaskSpec(("bash", f"{root}/bin/doctor"), 120),
            "status": TaskSpec(("bash", f"{root}/bin/sec", "ps"), 120),
            "sync": TaskSpec(("git", "-C", root, "pull", "--ff-only", "origin", "master"), 180),
            "bootstrap": TaskSpec(("bash", f"{root}/.devcontainer/bootstrap.sh"), 3600),
            "defend": TaskSpec(("bash", f"{root}/bin/defense-run"), 3600),
            "review": TaskSpec(("bash", f"{root}/bin/code-review"), 1800),
            "validate": TaskSpec(("bash", f"{root}/bin/validate-findings"), 300),
            "fuzz": TaskSpec(("bash", f"{root}/bin/fuzz-run"), 900),
            "report": TaskSpec(("python3", f"{root}/bin/sec-report"), 300),
            "lab-up": TaskSpec(("bash", f"{root}/bin/sec", "up"), 600),
            "lab-down": TaskSpec(("bash", f"{root}/bin/sec", "down"), 600),
            "kali-build": TaskSpec(("bash", f"{root}/bin/sec", "kali-build"), 3600),
            "update": TaskSpec(("bash", f"{root}/bin/update-all"), 3600),
            "disk": TaskSpec(("bash", f"{root}/bin/disk-guard", "--auto"), 300),
        }

    @property
    def allowed_tasks(self) -> frozenset[str]:
        return frozenset((*self.specs, "codespace-list", "codespace-create", "codespace-retire-current"))

    def run(self, task: str) -> tuple[int, str]:
        try:
            if task == "codespace-list":
                return 0, self._codespace_list()
            if task == "codespace-create":
                return 0, self._codespace_create()
            if task == "codespace-retire-current":
                return 0, self._schedule_retire_current()
            spec = self.specs[task]
            return self._run_process(spec)
        except (GitHubError, KeyError, OSError, ValueError) as exc:
            return 1, str(exc)

    def _run_process(self, spec: TaskSpec) -> tuple[int, str]:
        try:
            result = subprocess.run(  # nosec B603
                list(spec.argv),
                cwd=self.config.root,
                text=True,
                capture_output=True,
                timeout=spec.timeout,
                check=False,
            )
            output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
            return result.returncode, self._sanitize(output)
        except subprocess.TimeoutExpired as exc:
            output = "\n".join(
                part
                for part in (
                    exc.stdout if isinstance(exc.stdout, str) else "",
                    exc.stderr if isinstance(exc.stderr, str) else "",
                    f"Timed out after {spec.timeout} seconds.",
                )
                if part
            )
            return 124, self._sanitize(output)

    def _codespace_list(self) -> str:
        payload = self.client.request("GET", "/user/codespaces?per_page=100") or {}
        rows = []
        for item in payload.get("codespaces", []):
            rows.append(
                "\t".join(
                    str(value or "")
                    for value in (
                        item.get("name"),
                        item.get("display_name"),
                        (item.get("repository") or {}).get("full_name"),
                        item.get("state"),
                        (item.get("machine") or {}).get("display_name"),
                        item.get("web_url"),
                    )
                )
            )
        return "\n".join(rows)

    def _codespace_create(self) -> str:
        payload = self.client.request("GET", f"/repos/{self.config.repo}/codespaces/machines") or {}
        machines = payload.get("machines") or []
        if not machines:
            raise GitHubError("No Codespaces machine type is currently available.")
        machine = min(
            machines,
            key=lambda item: (
                int(item.get("cpus") or 0),
                int(item.get("memory_in_bytes") or 0),
                int(item.get("storage_in_bytes") or 0),
            ),
        )
        created = self.client.request(
            "POST",
            f"/repos/{self.config.repo}/codespaces",
            {
                "ref": "master",
                "machine": machine["name"],
                "devcontainer_path": ".devcontainer/devcontainer.json",
            },
        ) or {}
        result = {
            "name": created.get("name"),
            "display_name": created.get("display_name"),
            "state": created.get("state"),
            "web_url": created.get("web_url"),
            "machine": (created.get("machine") or {}).get("display_name"),
        }
        return json.dumps(result, indent=2, sort_keys=True)

    def _schedule_retire_current(self) -> str:
        current = os.environ.get("CODESPACE_NAME", "").strip()
        if not current:
            raise ValueError("Current Codespace name is unavailable.")
        self.config.reports.mkdir(parents=True, exist_ok=True)
        log = (self.config.reports / "codespace-retire.log").open("a", encoding="utf-8")
        subprocess.Popen(  # nosec B603
            [
                sys.executable,
                "-m",
                "security_lab.remote_agent",
                "delete-codespace",
                "--name",
                current,
                "--delay",
                "20",
            ],
            cwd=self.config.root,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
        log.close()
        return f"Scheduling retirement of current Codespace: {current}\nDeletion scheduled in 20 seconds."

    def _sanitize(self, text: str) -> str:
        token = self.client._token
        if token:
            text = text.replace(token, "[REDACTED]")
        return TOKEN_PATTERN.sub("[REDACTED]", text)[-MAX_RESULT_BYTES:]


def parse_task(body: str) -> str | None:
    matches = TASK_PATTERN.findall(body)
    return matches[0] if len(matches) == 1 else None


class RemoteAgent:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.client = GitHubClient(config)
        self.runner = TaskRunner(config, self.client)
        self._stop_requested = False

    def start(self) -> int:
        if self._pid_alive():
            print(f"remote-agent already running: {self._read_pid()}")
            return 0
        self.client.resolve_token()
        self.config.reports.mkdir(parents=True, exist_ok=True)
        with self.config.logfile.open("a", encoding="utf-8") as log:
            process = subprocess.Popen(  # nosec B603
                [sys.executable, "-m", "security_lab.remote_agent", "run"],
                cwd=self.config.root,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
        self.config.pidfile.write_text(f"{process.pid}\n", encoding="utf-8")
        print(f"remote-agent started: {process.pid}")
        return 0

    def stop(self) -> int:
        pid = self._read_pid()
        if pid is None or not self._pid_alive():
            self.config.pidfile.unlink(missing_ok=True)
            print("remote-agent is not running.")
            return 0
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if not self._pid_exists(pid):
                break
            time.sleep(0.1)
        self.config.pidfile.unlink(missing_ok=True)
        print(f"remote-agent stopped: {pid}")
        return 0

    def status(self) -> int:
        pid = self._read_pid()
        if pid is not None and self._pid_alive():
            print(f"remote-agent running: {pid}")
            return 0
        print("remote-agent stopped.")
        return 1

    def run_foreground(self) -> int:
        self.config.reports.mkdir(parents=True, exist_ok=True)
        with self.config.lockfile.open("w", encoding="utf-8") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print("remote-agent already has an active worker.", file=sys.stderr)
                return 1

            self.client.resolve_token()
            self.config.pidfile.write_text(f"{os.getpid()}\n", encoding="utf-8")
            signal.signal(signal.SIGTERM, self._request_stop)
            signal.signal(signal.SIGINT, self._request_stop)
            print(f"[{utc_timestamp()}] remote-agent online for {self.config.repo}", flush=True)
            try:
                while not self._stop_requested:
                    self._poll_once()
                    self._sleep_interruptibly(self.config.poll_seconds)
            finally:
                if self._read_pid() == os.getpid():
                    self.config.pidfile.unlink(missing_ok=True)
        return 0

    def _poll_once(self) -> None:
        query = urllib.parse.urlencode(
            {"state": "open", "creator": self.config.owner, "per_page": "20"}
        )
        try:
            issues = self.client.request("GET", f"/repos/{self.config.repo}/issues?{query}")
        except GitHubError as exc:
            print(f"[{utc_timestamp()}] poll failed: {exc}", flush=True)
            return
        if not isinstance(issues, list):
            return
        for issue in issues:
            if isinstance(issue, dict) and "pull_request" not in issue:
                self._process_issue(issue)

    def _process_issue(self, issue: dict[str, Any]) -> None:
        title = str(issue.get("title") or "")
        author = str((issue.get("user") or {}).get("login") or "")
        if not title.startswith(TITLE_PREFIX) or author != self.config.owner:
            return

        number = int(issue.get("number") or 0)
        body = str(issue.get("body") or "")
        task = parse_task(body)
        if not task:
            self._reject(number, "invalid-task", "Rejected: missing or ambiguous `task:` field.")
            return
        if task not in self.runner.allowed_tasks:
            self._reject(number, task, f"Rejected: task `{task}` is not allowlisted.")
            return
        if task == "codespace-retire-current":
            expected = f"confirm: {os.environ.get('CODESPACE_NAME', 'missing')}"
            if expected not in body.splitlines():
                self._reject(
                    number,
                    task,
                    f"Rejected: retiring the current Codespace requires exact confirmation: `{expected}`.",
                )
                return

        try:
            self._set_title(number, f"[LAB-RUNNING] {task}")
            returncode, output = self.runner.run(task)
            result = "OK" if returncode == 0 else "FAIL"
            result_body = (
                f"Task: {task}\n"
                f"Exit code: {returncode}\n"
                f"Codespace: {os.environ.get('CODESPACE_NAME', 'unknown')}\n"
                f"UTC: {utc_timestamp()}\n\n"
                f"Output:\n\n    {output.replace(chr(10), chr(10) + '    ')}"
            )
            self._comment(number, result_body)
            self._close(number, f"[LAB-{result}] {task}")
        except GitHubError as exc:
            print(f"[{utc_timestamp()}] issue {number} failed: {exc}", flush=True)

    def _reject(self, number: int, task: str, message: str) -> None:
        try:
            self._comment(number, message)
            self._close(number, f"[LAB-REJECTED] {task}")
        except GitHubError as exc:
            print(f"[{utc_timestamp()}] issue {number} rejection failed: {exc}", flush=True)

    def _comment(self, number: int, body: str) -> None:
        self.client.request(
            "POST", f"/repos/{self.config.repo}/issues/{number}/comments", {"body": body}
        )

    def _set_title(self, number: int, title: str) -> None:
        self.client.request("PATCH", f"/repos/{self.config.repo}/issues/{number}", {"title": title})

    def _close(self, number: int, title: str) -> None:
        self.client.request(
            "PATCH",
            f"/repos/{self.config.repo}/issues/{number}",
            {"state": "closed", "state_reason": "completed", "title": title},
        )

    def _request_stop(self, _signum: int, _frame: Any) -> None:
        self._stop_requested = True

    def _sleep_interruptibly(self, seconds: float) -> None:
        deadline = time.monotonic() + max(seconds, 0)
        while not self._stop_requested and time.monotonic() < deadline:
            time.sleep(min(0.25, max(deadline - time.monotonic(), 0)))

    def _read_pid(self) -> int | None:
        try:
            value = int(self.config.pidfile.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None
        return value if value > 1 else None

    @staticmethod
    def _pid_exists(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def _pid_alive(self) -> bool:
        pid = self._read_pid()
        return pid is not None and self._pid_exists(pid)


def delete_codespace(config: Config, name: str, delay: float) -> int:
    if delay > 0:
        time.sleep(delay)
    encoded = urllib.parse.quote(name, safe="")
    GitHubClient(config).request("DELETE", f"/user/codespaces/{encoded}")
    print(f"Deleted Codespace: {name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Security Lab remote command agent.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("start", "stop", "status", "run"):
        subparsers.add_parser(command)
    delete = subparsers.add_parser("delete-codespace")
    delete.add_argument("--name", required=True)
    delete.add_argument("--delay", type=float, default=0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = Config()
    if args.command == "delete-codespace":
        try:
            return delete_codespace(config, args.name, args.delay)
        except GitHubError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    agent = RemoteAgent(config)
    try:
        if args.command == "start":
            return agent.start()
        if args.command == "stop":
            return agent.stop()
        if args.command == "status":
            return agent.status()
        return agent.run_foreground()
    except GitHubError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
