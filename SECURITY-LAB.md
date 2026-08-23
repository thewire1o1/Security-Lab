# AI Security Lab

A reproducible GitHub Codespaces security workstation with Codex, GPT-5.6 Sol, Docker-based vulnerable targets, recon tooling, web testing utilities, and report helpers.

## Quick start

After pulling the latest `codex-vm` branch, rebuild the Codespace so the Docker-in-Docker feature is applied. The rebuild automatically runs `.devcontainer/bootstrap.sh`.

Open a fresh terminal and use:

```bash
sol
```

Starts Codex with Daybreak Blue / GPT-5.6 Sol.

```bash
labup
labps
```

Starts the local vulnerable training stack:

- Juice Shop: `http://127.0.0.1:3000`
- DVWA: `http://127.0.0.1:8080`
- WebGoat: `http://127.0.0.1:8081`

```bash
labscan
```

Runs service discovery and template checks against the local lab and stores output in `reports/`.

```bash
recon example.com
recon example.com --deep
```

Baseline recon performs WHOIS, DNS, subdomain discovery, Nmap service discovery, and HTTP probing. `--deep` adds Nuclei checks.

```bash
headers https://example.com
```

Shows HTTP headers and TLS certificate information.

```bash
bash bin/doctor
```

Shows installed tools, Docker status, Codex login status, and local lab status.

## Toolset

### AI
- OpenAI Codex CLI
- Daybreak Blue / GPT-5.6 Sol shortcut (`sol`)

### Network / discovery
- Nmap
- Masscan
- Naabu
- Subfinder
- DNSx
- HTTPx
- Assetfinder
- WHOIS / dig / traceroute / netcat / socat

### Web
- Nuclei
- Katana
- FFUF
- SQLMap
- Nikto
- GAU
- WaybackURLs
- curl / OpenSSL helpers

### Credentials / protocols
- Hydra
- John the Ripper
- Impacket

### Code / application analysis
- Semgrep
- ripgrep
- Python / Go / Node.js toolchains

### Wordlists
- SecLists at `$SECLISTS`

## Workspace

- `lab/` vulnerable local services
- `bin/` helper commands
- `reports/` generated scan output (gitignored)
- `targets/` target-specific notes
- `notes/` working notes
- `loot/` captured training artifacts (gitignored)

## Persistence

The environment definition and tooling bootstrap live in the Git branch. If the Codespace is deleted, create another Codespace from `codex-vm`; the lab rebuilds itself automatically.
