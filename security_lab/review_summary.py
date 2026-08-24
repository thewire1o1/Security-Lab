from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from security_lab.common import SEVERITIES, read_json, write_json_atomic

_SEVERITY_ALIASES = {
    "critical": "critical",
    "high": "high",
    "error": "high",
    "medium": "medium",
    "warning": "medium",
    "low": "low",
    "info": "info",
    "note": "info",
    "unknown": "info",
}
_PRIMARY_TOOLS = ("semgrep", "gitleaks", "trivy", "bandit")


def normalize_severity(value: Any) -> str:
    return _SEVERITY_ALIASES.get(str(value or "info").strip().lower(), "info")


def _increment(counts: dict[str, int], severity: Any) -> None:
    counts[normalize_severity(severity)] += 1


def summarize_review(output_dir: Path) -> dict[str, Any]:
    semgrep = read_json(output_dir / "semgrep.json", {"results": [], "errors": []})
    gitleaks = read_json(output_dir / "gitleaks.json", [])
    trivy = read_json(output_dir / "trivy.json", {"Results": []})
    bandit = read_json(output_dir / "bandit.json", {"results": []})

    severity = {name: 0 for name in SEVERITIES}
    availability = {tool: not (output_dir / f"{tool}.unavailable").exists() for tool in _PRIMARY_TOOLS}

    semgrep_results = semgrep.get("results", []) if isinstance(semgrep, dict) else []
    semgrep_errors = semgrep.get("errors", []) if isinstance(semgrep, dict) else []
    for finding in semgrep_results:
        extra = finding.get("extra") or {}
        _increment(severity, extra.get("severity"))

    bandit_results = bandit.get("results", []) if isinstance(bandit, dict) else []
    for finding in bandit_results:
        _increment(severity, finding.get("issue_severity"))

    gitleaks_results = gitleaks if isinstance(gitleaks, list) else []
    for _ in gitleaks_results:
        _increment(severity, "high")

    trivy_vulnerabilities = 0
    trivy_misconfigurations = 0
    trivy_secrets = 0
    trivy_results = trivy.get("Results", []) if isinstance(trivy, dict) else []
    for result in trivy_results or []:
        for finding in result.get("Vulnerabilities") or []:
            trivy_vulnerabilities += 1
            _increment(severity, finding.get("Severity"))
        for finding in result.get("Misconfigurations") or []:
            trivy_misconfigurations += 1
            _increment(severity, finding.get("Severity"))
        for finding in result.get("Secrets") or []:
            trivy_secrets += 1
            _increment(severity, finding.get("Severity") or "high")

    summary = {
        "timestamp": int(time.time()),
        "severity": severity,
        "total": sum(severity.values()),
        "coverage": {
            "available": sorted(tool for tool, present in availability.items() if present),
            "missing": sorted(tool for tool, present in availability.items() if not present),
            "complete": all(availability.values()),
        },
        "tools": {
            "semgrep": {"findings": len(semgrep_results), "errors": len(semgrep_errors)},
            "gitleaks": {"findings": len(gitleaks_results)},
            "bandit": {"findings": len(bandit_results)},
            "trivy": {
                "vulnerabilities": trivy_vulnerabilities,
                "misconfigurations": trivy_misconfigurations,
                "secrets": trivy_secrets,
            },
        },
    }
    write_json_atomic(output_dir / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize security scanner results.")
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    summary = summarize_review(args.output_dir.resolve())
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
