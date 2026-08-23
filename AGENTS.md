# AI Security Lab Guidance

This branch is a cloud security workstation for authorized testing, local vulnerable labs, code review, detection engineering, and defensive/offensive security work on systems the operator owns or is explicitly permitted to test.

## Defaults

- Prefer reproducible commands and save output under `reports/`.
- Local training targets live in `lab/docker-compose.yml`.
- Use `gpt-daybreak-blue` / GPT-5.6 Sol for Codex sessions when available.
- Never commit API keys, session tokens, passwords, cookies, SSH private keys, or other secrets.
- When a target is provided, keep commands scoped to that target and preserve evidence/output files.
- Before changing a system, capture the current state and make changes reversible when practical.

## Useful commands

- `labup` starts Juice Shop, DVWA, and WebGoat.
- `labps` shows lab status.
- `labscan` performs a local lab scan and saves reports.
- `recon <target>` performs baseline discovery.
- `recon <target> --deep` adds template-based checks.
- `headers <url>` shows HTTP headers and TLS certificate details.
- `sol` starts Codex with Daybreak Blue.

## Workspace layout

- `lab/` local vulnerable training apps
- `bin/` helper commands
- `reports/` scan and analysis output
- `notes/` working notes
- `targets/` target-specific scope notes
- `loot/` captured lab artifacts and evidence
