from __future__ import annotations

import argparse
import fcntl
import http.client
import json
import os
import re
import shutil
import signal
import ssl
import subprocess  # nosec B404
import sys
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from security_lab.common import ROOT, utc_timestamp

API_HOST: Final = "api.github.com"
DEFAULT_REPO: Final = "thewire1o1/Security-Lab"
DEFAULT_OWNER: Final = "thewire1o1"
TITLE_PREFIX: Final = "[LAB-CMD]"
MAX_RESULT_BYTES: Final = 12_000
TOKEN_PATTERN: Final = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b",
    re.IGNORECASE,
)
TASK_PATTERN: Final = re.compile(r"^task:[ \t]*([a-z0-9-]+)[ \t]*$", re.MULTILINE)
REPO_PATTERN: Final = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
OWNER_PATTERN: Final = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
CODESPACE_PATTERN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,127}$")
AGENT_CMDLINE_MARKER: Final = b"security_lab.remote_agent"
HTTP_METHODS: Final = frozenset({"GET", "POST", "PATCH", "DELETE"})


class GitHubError(RuntimeError):
    pass


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


def _poll_seconds() -> float:
    raw = _env("SEC_REMOTE_POLL_SECONDS", "8")
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError("SEC_REMOTE_POLL_SECONDS must be numeric.") from exc
    if not 1 <= value <= 300:
        raise ValueError("SEC_REMOTE_POLL_SECONDS must be between 1 and 300 seconds.")
    return value


def _tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


@dataclass(frozen=True)
class Config:
    root: Path = ROOT
    repo: str = field(default_factory=lambda: _env("GITHUB_REPOSITORY", DEFAULT_REPO))
    owner: str = field(default_factory=lambda: _env("SEC_REMOTE_OWNER", DEFAULT_OWNER))
    poll_seconds: float = field(default_factory=_poll_seconds)

    def __post_init__(self) -> None:
        resolved_root = self.root.resolve()
        if not REPO_PATTERN.fullmatch(self.repo):
            raise ValueError(f"Invalid repository name: {self.repo!r}")
        if not OWNER_PATTERN.fullmatch(self.owner):
            raise ValueError(f"Invalid GitHub owner: {self.owner!r}")
        if not 1 <= self.poll_seconds <= 300:
            raise ValueError("poll_seconds must be between 1 and 300 seconds.")
        object.__setattr__(self, "root", resolved_root)

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

        explicit = _env("SEC_GITHUB_TOKEN", "")
        if explicit:
            self._token = explicit
            return explicit

        gh_token = self._token_from_gh()
        if gh_token:
            self._token = gh_token
            return gh_token

        for variable in ("GH_TOKEN", "GITHUB_TOKEN"):
            value = _env(variable, "")
            if value:
                self._token = value
                return value

        credential = self._token_from_git_credential()
        if credential:
            self._token = credential
            return credential

        raise GitHubError("GitHub authentication is unavailable.")

    def _token_from_gh(self) -> str:
        gh = shutil.which("gh")
        if gh is None:
            return ""
        env = os.environ.copy()
        env.pop("GH_TOKEN", None)
        env.pop("GITHUB_TOKEN", None)
        try:
            result = subprocess.run(  # nosec B603
                [gh, "auth", "token", "--hostname", "github.com"],
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
        git = shutil.which("git")
        if git is None:
            return ""
        request = "protocol=https\nhost=github.com\n\n"
        try:
            result = subprocess.run(  # nosec B603
                [git, "credential", "fill"],
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
        normalized_method = method.upper()
        if normalized_method not in HTTP_METHODS:
            raise ValueError(f"Unsupported GitHub API method: {method!r}")
        if not path.startswith("/") or "://" in path or "\\" in path:
            raise ValueError(f"Invalid GitHub API path: {path!r}")

        token = self.resolve_token()
        body: bytes | None = None
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "security-lab-remote-agent",
        }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        connection = http.client.HTTPSConnection(  # nosemgrep: python.lang.security.audit.httpsconnection-detected.httpsconnection-detected
            API_HOST,
            timeout=30,
            context=_tls_context(),
        )
        try:
            connection.request(normalized_method, path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read()
        except (OSError, http.client.HTTPException) as exc:
            raise GitHubError(f"GitHub API request failed: {exc}") from exc
        finally:
            connection.close()

        if response.status >= 400:
            detail = raw.decode("utf-8", errors="replace")[:1000]
            raise GitHubError(f"GitHub API returned HTTP {response.status}: {detail}")
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
        return frozenset(self.specs) | {
            "codespace-list",
            "codespace-create",
            "codespace-retire-current",
        }

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
        except (GitHubError, KeyError, OSError, TypeError, ValueError) as exc:
            return 1, self._sanitize(str(exc))

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
            output = "\n".join(
                part for part in (result.stdout.strip(), result.stderr.strip()) if part
            )
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
        if not isinstance(payload, dict):
            raise GitHubError("Codespaces list response had an unexpected shape.")
        items = payload.get("codespaces") or []
        if not isinstance(items, list):
            raise GitHubError("Codespaces list response had an unexpected shape.")

        rows: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            repository = item.get("repository") or {}
            machine = item.get("machine") or {}
            rows.append(
                "\t".join(
                    str(value or "")
                    for value in (
                        item.get("name"),
                        item.get("display_name"),
                        repository.get("full_name") if isinstance(repository, dict) else "",
                        item.get("state"),
                        machine.get("display_name") if isinstance(machine, dict) else "",
                        item.get("web_url"),
                    )
                )
            )
        return "\n".join(rows)

    @staticmethod
    def _machine_resources(item: dict[str, Any]) -> tuple[int, int, int] | None:
        try:
            cpus = int(item.get("cpus"))
            memory = int(item.get("memory_in_bytes"))
            storage = int(item.get("storage_in_bytes"))
        except (TypeError, ValueError):
            return None
        if not item.get("name") or cpus <= 0 or memory <= 0 or storage <= 0:
            return None
        return cpus, memory, storage

    def _codespace_create(self) -> str:
        payload = self.client.request("GET", f"/repos/{self.config.repo}/codespaces/machines") or {}
        if not isinstance(payload, dict):
            raise GitHubError("Codespaces machine response had an unexpected shape.")

        candidates: list[tuple[tuple[int, int, int], dict[str, Any]]] = []
        for item in payload.get("machines") or []:
            if not isinstance(item, dict):
                continue
            resources = self._machine_resources(item)
            if resources is not None:
                candidates.append((resources, item))
        if not candidates:
            raise GitHubError("No valid Codespaces machine type is currently available.")

        _, machine = min(candidates, key=lambda candidate: candidate[0])
        created = self.client.request(
            "POST",
            f"/repos/{self.config.repo}/codespaces",
            {
                "ref": "master",
                "machine": machine["name"],
                "devcontainer_path": ".devcontainer/devcontainer.json",
            },
        ) or {}
        if not isinstance(created, dict):
            raise GitHubError("Codespace creation response had an unexpected shape.")
        created_machine = created.get("machine") or {}
        result = {
            "name": created.get("name"),
            "display_name": created.get("display_name"),
            "state": created.get("state"),
            "web_url": created.get("web_url"),
            "machine": (
                created_machine.get("display_name")
                if isinstance(created_machine, dict)
                else None
            ),
        }
        return json.dumps(result, indent=2, sort_keys=True)

    def _schedule_retire_current(self) -> str:
        current = _env("CODESPACE_NAME", "")
        if not CODESPACE_PATTERN.fullmatch(current):
            raise ValueError("Current Codespace name is unavailable or invalid.")
        self.config.reports.mkdir(parents=True, exist_ok=True)
        log_path = self.config.reports / "codespace-retire.log"
        with log_path.open("a", encoding="utf-8") as log:
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
        return (
            f"Scheduling retirement of current Codespace: {current}\n"
            "Deletion scheduled in 20 seconds."
        )

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
        pid = self._read_pid()
        if pid is not None and self._pid_is_agent(pid):
            print(f"remote-agent already running: {pid}")
            return 0
        self.config.pidfile.unlink(missing_ok=True)
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
        if pid is None or not self._pid_is_agent(pid):
            self.config.pidfile.unlink(missing_ok=True)
            print("remote-agent is not running.")
            return 0

        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            self.config.pidfile.unlink(missing_ok=True)
            print(f"remote-agent stopped: {pid}")
            return 0

        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and self._pid_is_agent(pid):
            time.sleep(0.1)
        if self._pid_is_agent(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.config.pidfile.unlink(missing_ok=True)
        print(f"remote-agent stopped: {pid}")
        return 0

    def status(self) -> int:
        pid = self._read_pid()
        if pid is not None and self._pid_is_agent(pid):
            print(f"remote-agent running: {pid}")
            return 0
        self.config.pidfile.unlink(missing_ok=True)
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

        try:
            number = int(issue.get("number") or 0)
        except (TypeError, ValueError):
            return
        if number <= 0:
            return

        body = str(issue.get("body") or "")
        task = parse_task(body)
        if not task:
            self._reject(number, "invalid-task", "Rejected: missing or ambiguous `task:` field.")
            return
        if task not in self.runner.allowed_tasks:
            self._reject(number, task, f"Rejected: task `{task}` is not allowlisted.")
            return
        if task == "codespace-retire-current":
            expected = f"confirm: {_env('CODESPACE_NAME', 'missing')}"
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
            indented_output = output.replace("\n", "\n    ")
            result_body = (
                f"Task: {task}\n"
                f"Exit code: {returncode}\n"
                f"Codespace: {_env('CODESPACE_NAME', 'unknown')}\n"
                f"UTC: {utc_timestamp()}\n\n"
                f"Output:\n\n    {indented_output}"
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

    @classmethod
    def _pid_is_agent(cls, pid: int) -> bool:
        if not cls._pid_exists(pid):
            return False
        try:
            cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
        except OSError:
            return False
        return AGENT_CMDLINE_MARKER in cmdline


def delete_codespace(config: Config, name: str, delay: float) -> int:
    if not CODESPACE_PATTERN.fullmatch(name):
        raise ValueError("Invalid Codespace name.")
    if not 0 <= delay <= 3600:
        raise ValueError("delay must be between 0 and 3600 seconds.")
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
    try:
        config = Config()
        if args.command == "delete-codespace":
            return delete_codespace(config, args.name, args.delay)

        agent = RemoteAgent(config)
        if args.command == "start":
            return agent.start()
        if args.command == "stop":
            return agent.stop()
        if args.command == "status":
            return agent.status()
        return agent.run_foreground()
    except (GitHubError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
