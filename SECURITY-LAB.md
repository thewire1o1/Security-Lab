# AI Security Lab

A reproducible GitHub Codespaces security workstation with two layers:

1. A fast Debian-based host for Codex, GPT-5.6 Sol, ProjectDiscovery, Nmap, Semgrep, automation, notes, and reporting.
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
sec kali-build
sec kali
sec sol
sec new client-or-lab-name
sec update
sec update --full
```

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
