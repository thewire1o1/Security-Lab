# AI Security Lab

A reproducible GitHub Codespaces security workstation with two layers:

1. A fast Debian-based host for Codex, GPT-5.6 Sol, ProjectDiscovery, Nmap, Semgrep, automation, notes, reporting, and Mission Control.
2. A disposable Kali Rolling operator container for the heavyweight offensive stack.

## Control surface

```bash
source ~/.bashrc
sec help
```

Useful commands:

```bash
sec doctor
sec up
sec ps
sec scan
sec gui
sec report
sec kali-build
sec kali
sec mcp-setup
sec ai-kali
sec sol
sec new client-or-lab-name
sec update
sec update --full
```

Short aliases installed by the devcontainer include `labup`, `labdown`, `labps`, `labscan`, `labgui`, and `labreport`.

## Mission Control GUI

```bash
sec gui
```

Mission Control binds to `127.0.0.1:8765`. The devcontainer automatically forwards and labels port 8765 for Codespaces. Codespaces forwarded ports are private by default.

Mission Control provides:

- live status for Juice Shop, DVWA, WebGoat, and Kali
- container CPU and memory telemetry
- visual Codex → Kali → target network topology
- host tool-presence inventory
- scan history and Nuclei severity totals
- live activity log
- allowlisted local Start / Stop / Scan / Report actions
- responsive browser UI for desktop, tablet, and phone

The backend does not accept arbitrary shell commands from the browser. Actions map to a fixed server-side allowlist.

## Local training targets

`sec up` starts:

- Juice Shop: `http://127.0.0.1:3000`
- DVWA: `http://127.0.0.1:8080`
- WebGoat: `http://127.0.0.1:8081`

All targets and the Kali operator container share the private `security-lab` Docker network.

## Kali operator layer

Build once:

```bash
sec kali-build
```

Enter whenever needed:

```bash
sec kali
```

The Kali image is based on `kalilinux/kali-rolling` and includes Kali's top-10 metapackage plus focused operator tooling for AD, pivoting, exploitation, web testing, credential work, reporting, container/code scanning, and AI-assisted workflows.

Highlights include Metasploit, NetExec, Responder, BloodHound, Impacket scripts, enum4linux-ng, Evil-WinRM, ExploitDB, Ligolo-ng, Kerberoast tooling, mitm6, PEASS, Recon-ng, SecLists, testssl.sh, WhatWeb, WAFW00F, WPScan, tshark, Trivy, Gitleaks, Kali MCP Server, Metasploit MCP, and HexStrike AI.

The repository is mounted at `/workspace` inside Kali. Kali's `/root` home is persistent in its own Docker volume, while the container itself stays disposable.

Kali intentionally runs as root because raw-socket and network-administration capabilities are required by the operator toolset. That design is documented as an explicit Trivy exception. The container remains isolated on the lab Docker network, and its MCP API is not published as a Codespaces port.

## Codex + Kali MCP mode

The Kali container starts its MCP API on `127.0.0.1:5000` *inside the container only*. It is not published as a Codespaces port.

Configure Codex once:

```bash
sec mcp-setup
```

Then launch Sol with the Kali MCP bridge ready:

```bash
sec ai-kali
```

`sec ai-kali` starts the operator container if needed, checks the local Kali MCP API, and launches Codex on GPT-5.6 Sol. The MCP bridge itself is invoked through `docker compose exec`, so the API does not need to be exposed publicly.

## Evidence and reports

Run the local training scan:

```bash
sec scan
```

This stores timestamped Nmap, HTTP header, and Nuclei artifacts under `reports/lab-*`.

Generate the latest report:

```bash
sec report
```

Outputs:

```text
reports/mission-control-report.html
reports/mission-control-report.json
```

The HTML report includes severity totals, Nuclei evidence, the latest Nmap excerpt, timestamps, and the fixed localhost training scope.

## Host toolset

### AI
- OpenAI Codex CLI
- GPT-5.6 Sol shortcut (`sec sol` / `sol`)

### Discovery / web
- Nmap, Masscan
- ProjectDiscovery PDTM
- Nuclei, HTTPx, Subfinder, Naabu, DNSx, Katana
- FFUF, GAU, WaybackURLs, Assetfinder
- Nikto, SQLMap

### Credentials / protocols
- Hydra
- John the Ripper
- Impacket

### Code / application analysis
- Semgrep
- ripgrep
- Python / current Go / Node.js

### Wordlists
- SecLists at `$SECLISTS`

## Engagement workspaces

```bash
sec new example
```

Creates:

```text
engagements/example/
  scope/targets.txt
  notes/timeline.md
  evidence/
  reports/
  loot/
```

Evidence, reports, and loot are ignored by git by default.

## Existing helpers

```bash
recon example.com
recon example.com --deep
headers https://example.com
labscan
```

Recon stores timestamped output under `reports/`.

## Continuous validation

`.github/workflows/ci.yml` validates Python and shell syntax, validates the Docker Compose definition, scans repository history with Gitleaks, and runs Trivy filesystem checks for high/critical vulnerabilities, secrets, and misconfiguration.

## Public showcase

`docs/index.html` is the static GitHub Pages showcase for the project. Repository Pages must be enabled before GitHub serves it publicly.

## Updating

Fast update:

```bash
sec update
```

Also rebuild the Kali Rolling image:

```bash
sec update --full
```

## Persistence

The environment definition lives in git. A deleted Codespace can be recreated from the branch and bootstrapped again. Heavy Kali tooling is intentionally separated from the host so the Codespace remains maintainable instead of becoming an un-debuggable pile of packages.
