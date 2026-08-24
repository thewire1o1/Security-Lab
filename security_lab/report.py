from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

from security_lab.common import REPORTS, SEVERITIES, newest_directories, utc_timestamp, write_json_atomic

DEFAULT_HTML: Final = REPORTS / "dpsr-evidence-report.html"
DEFAULT_JSON: Final = REPORTS / "dpsr-evidence-report.json"
SCOPE: Final = ("127.0.0.1:3000", "127.0.0.1:8080", "127.0.0.1:8081")


@dataclass(frozen=True)
class Finding:
    severity: str
    text: str


def newest_scan(reports: Path = REPORTS) -> Path | None:
    scans = newest_directories(reports, "lab-*")
    return scans[0] if scans else None


def nuclei_findings(scan: Path | None) -> list[Finding]:
    if scan is None:
        return []
    path = scan / "nuclei.txt"
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    findings: list[Finding] = []
    for raw in lines:
        severity = "info"
        for candidate in SEVERITIES:
            if re.search(rf"\[{candidate}\]", raw, flags=re.IGNORECASE):
                severity = candidate
                break
        findings.append(Finding(severity=severity, text=raw.strip()))
    return findings


def nmap_excerpt(scan: Path | None, limit: int = 12_000) -> str:
    if scan is None:
        return "No scan data available."
    path = scan / "nmap-local.nmap"
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return "No Nmap text output available."


def build_payload(scan: Path | None, findings: list[Finding]) -> dict[str, object]:
    raw_counts = Counter(finding.severity for finding in findings)
    counts = {severity: raw_counts.get(severity, 0) for severity in SEVERITIES}
    return {
        "generated": utc_timestamp(),
        "source_scan": scan.name if scan else None,
        "scope": list(SCOPE),
        "counts": counts,
        "findings": [asdict(finding) for finding in findings],
    }


def render_html(payload: dict[str, object], nmap_text: str) -> str:
    """Render evidence while treating every scanner-derived string as untrusted input."""
    findings = payload.get("findings")
    counts = payload.get("counts")
    if not isinstance(findings, list) or not isinstance(counts, dict):
        raise TypeError("report payload must contain list 'findings' and mapping 'counts'")

    rows = "".join(
        "<tr>"
        f"<td><span class='sev {html.escape(str(item['severity']))}'>{html.escape(str(item['severity']).upper())}</span></td>"
        f"<td><code>{html.escape(str(item['text']))}</code></td>"
        "</tr>"
        for item in findings
        if isinstance(item, dict) and "severity" in item and "text" in item
    ) or "<tr><td colspan='2'>No Nuclei findings were present in the latest stored scan.</td></tr>"

    metric_cards = "".join(
        f"<div class='metric'><b>{int(counts.get(severity, 0))}</b><span>{severity.upper()}</span></div>"
        for severity in SEVERITIES
    )
    generated = html.escape(str(payload.get("generated") or "unknown"))
    scan_name = html.escape(str(payload.get("source_scan") or "none"))
    escaped_nmap = html.escape(nmap_text)
    scope = " · ".join(html.escape(item) for item in SCOPE)

    return f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>DPSR Evidence Report</title>
<style>
body{{margin:0;background:#070a0f;color:#eaf3ff;font-family:Inter,system-ui,sans-serif}}main{{max-width:1100px;margin:auto;padding:42px 24px}}h1{{font-size:34px;margin-bottom:4px}}.sub{{color:#91a3b8}}.metrics{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:28px 0}}.metric{{border:1px solid #213148;background:#0d141e;border-radius:12px;padding:16px;text-align:center}}.metric b{{display:block;font-size:28px}}.metric span{{color:#91a3b8;font-size:10px}}section{{border:1px solid #1b2a3d;background:#0c121b;border-radius:14px;margin:16px 0;overflow:hidden}}h2{{font-size:13px;letter-spacing:.09em;padding:15px 18px;margin:0;border-bottom:1px solid #1b2a3d}}.body{{padding:18px}}table{{width:100%;border-collapse:collapse}}td,th{{padding:10px;border-bottom:1px solid #172435;text-align:left;vertical-align:top;font-size:12px}}code,pre{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}pre{{white-space:pre-wrap;background:#05080c;padding:14px;border-radius:10px;overflow:auto;color:#b9c9d9}}.sev{{font-size:9px;font-weight:800;padding:5px 7px;border-radius:999px;border:1px solid #33485e}}.critical{{color:#ff4d67}}.high{{color:#ff8b5c}}.medium{{color:#ffd166}}.low{{color:#65f59a}}.info{{color:#52e6ff}}@media(max-width:700px){{.metrics{{grid-template-columns:repeat(2,1fr)}}}}
</style>
</head>
<body><main>
<div class='sub'>DIGITAL PARAGON SECURITY RESEARCH / THEWIRE1O1</div>
<h1>DPSR Evidence Report</h1>
<div class='sub'>Generated {generated} · source scan {scan_name}</div>
<div class='metrics'>{metric_cards}</div>
<section><h2>EXECUTIVE SUMMARY</h2><div class='body'>This report summarizes the latest stored scan of the intentionally vulnerable local training range. Scope is limited to Juice Shop, DVWA, and WebGoat bound to loopback.</div></section>
<section><h2>FINDINGS</h2><div class='body'><table><thead><tr><th>Severity</th><th>Evidence</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<section><h2>NMAP EVIDENCE</h2><div class='body'><pre>{escaped_nmap}</pre></div></section>
<section><h2>SCOPE</h2><div class='body'><code>{scope}</code></div></section>
</main></body></html>"""


def generate_report(
    reports: Path = REPORTS,
    html_output: Path = DEFAULT_HTML,
    json_output: Path = DEFAULT_JSON,
) -> Path:
    reports.mkdir(parents=True, exist_ok=True)
    scan = newest_scan(reports)
    findings = nuclei_findings(scan)
    payload = build_payload(scan, findings)
    write_json_atomic(json_output, payload)
    html_output.write_text(render_html(payload, nmap_excerpt(scan)), encoding="utf-8")
    return html_output


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a DPSR evidence report from the latest local scan.")
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    args = parser.parse_args()
    output = generate_report(html_output=args.html.resolve(), json_output=args.json.resolve())
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
