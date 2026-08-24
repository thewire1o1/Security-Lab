from __future__ import annotations

import argparse
import json
import os
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

CLIENT_ID = "178c6fc778ccc68e1d6a"
DEVICE_CODE_URL = "https://github.com/login/device/code"
TOKEN_URL = "https://github.com/login/oauth/access_token"
API_URL = "https://api.github.com"
REPOSITORY = "thewire1o1/Security-Lab"
REQUESTED_SCOPE = "public_repo"
FORBIDDEN_SCOPES = {
    "repo",
    "codespace",
    "workflow",
    "admin:org",
    "write:org",
    "delete_repo",
}


def request_json(url: str, data: dict[str, str] | None = None, token: str = "") -> tuple[dict[str, Any], Any]:
    body = urllib.parse.urlencode(data).encode("utf-8") if data is not None else None
    headers = {
        "Accept": "application/json" if "github.com/login/" in url else "application/vnd.github+json",
        "User-Agent": "dpsr-bridge-auth",
    }
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            return payload, response.headers
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"GitHub returned HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"GitHub request failed: {exc}") from exc


def write_status(path: Path, **payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def install_token(path: Path, token: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, stat.S_IRWXU)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(token)
            handle.write("\n")
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def validate_token(token: str) -> tuple[str, list[str]]:
    user, headers = request_json(f"{API_URL}/user", token=token)
    login = str(user.get("login") or "")
    scopes = sorted({scope.strip() for scope in str(headers.get("X-OAuth-Scopes") or "").split(",") if scope.strip()})
    if REQUESTED_SCOPE not in scopes:
        raise RuntimeError(f"Bridge token is missing required scope {REQUESTED_SCOPE!r}; received {scopes!r}.")
    forbidden = sorted(set(scopes) & FORBIDDEN_SCOPES)
    if forbidden:
        raise RuntimeError(f"Bridge token received forbidden scopes: {forbidden!r}.")
    request_json(f"{API_URL}/repos/{REPOSITORY}/issues?state=open&per_page=1", token=token)
    return login, scopes


def run(status_file: Path, token_file: Path) -> int:
    write_status(status_file, state="requesting")
    try:
        device, _ = request_json(DEVICE_CODE_URL, {"client_id": CLIENT_ID, "scope": REQUESTED_SCOPE})
        device_code = str(device.get("device_code") or "")
        user_code = str(device.get("user_code") or "")
        verification_uri = str(device.get("verification_uri") or "https://github.com/login/device")
        expires_in = int(device.get("expires_in") or 900)
        interval = max(int(device.get("interval") or 5), 5)
        if not device_code or not user_code:
            raise RuntimeError("GitHub device authorization response was incomplete.")

        deadline = time.monotonic() + expires_in
        write_status(
            status_file,
            state="waiting",
            user_code=user_code,
            verification_uri=verification_uri,
            expires_in=expires_in,
            requested_scope=REQUESTED_SCOPE,
        )

        while time.monotonic() < deadline:
            token_payload, _ = request_json(
                TOKEN_URL,
                {
                    "client_id": CLIENT_ID,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
            )
            access_token = str(token_payload.get("access_token") or "")
            if access_token:
                login, scopes = validate_token(access_token)
                install_token(token_file, access_token)
                write_status(
                    status_file,
                    state="ready",
                    login=login,
                    scopes=scopes,
                    token_file=str(token_file),
                )
                return 0

            error = str(token_payload.get("error") or "")
            if error == "authorization_pending":
                time.sleep(interval)
                continue
            if error == "slow_down":
                interval += 5
                time.sleep(interval)
                continue
            if error:
                description = str(token_payload.get("error_description") or error)
                raise RuntimeError(description)
            time.sleep(interval)

        raise RuntimeError("Bridge authorization expired before approval.")
    except Exception as exc:
        write_status(status_file, state="error", error=str(exc))
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status-file", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    args = parser.parse_args()
    return run(args.status_file.expanduser().resolve(), args.token_file.expanduser().resolve())


if __name__ == "__main__":
    raise SystemExit(main())
