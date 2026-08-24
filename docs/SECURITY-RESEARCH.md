# APOTHEON ONE Security Research Subsystem

> APOTHEON ONE · **Unified. Elevated.** · by Digital Paragon

APOTHEON ONE keeps its security research environment as a first-class subsystem with separate trust boundaries, dedicated operator tooling, persistent research state, reproducible evidence, and controlled automation.

The security profile is designed for isolated training targets, owned systems, and explicitly authorized research.

## Trust model

The environment separates four concerns:

1. **Control plane** — orchestration, project state, reporting, MCP, console actions, and supervised recovery.
2. **Operator plane** — disposable Kali tooling with explicit network capabilities.
3. **Training range** — intentionally vulnerable services on an isolated Docker network.
4. **Evidence plane** — reports, findings, research cases, engagement state, triage output, and validation artifacts.

Key invariants:

- vulnerable HTTP services bind to loopback on the host;
- vulnerable targets do not receive direct external egress;
- the Kali operator container is distinct from the target applications;
- browser operations map to fixed server-side actions;
- remote issue-based automation selects a fixed task vocabulary;
- command execution uses explicit argv and bounded timeouts;
- supplied artifacts are triaged statically and are not executed by the triage workflow;
- private runtime evidence, credentials, and transient research material stay outside normal source tracking.

## Training range

The default local range contains:

```text
OWASP Juice Shop  http://127.0.0.1:3000
DVWA              http://127.0.0.1:8080
WebGoat           http://127.0.0.1:8081
```

The vulnerable applications are attached to an internal Docker network. Resource limits and `no-new-privileges` are applied to reduce accidental host impact, while the applications remain intentionally vulnerable for training and validation.

## Kali operator plane

The operator image is based on Kali Rolling and includes a broad research toolchain.

### Web, discovery, and reconnaissance

- Kali top ten tool set
- feroxbuster
- gobuster
- WhatWeb
- WAFW00F
- WPScan
- testssl.sh
- theHarvester
- Recon-ng
- SecLists
- ExploitDB

### Identity, Windows, and directory services

- BloodHound
- Impacket
- enum4linux-ng
- Evil-WinRM
- Kerberoast
- krbrelayx
- mitm6
- smbclient
- LDAP utilities

### Network, traffic, and pivoting

- Ligolo-ng
- proxychains4
- sshuttle
- socat
- netcat
- tshark
- SNMP tooling
- nbtscan
- onesixtyone

### Reverse engineering and artifact inspection

- YARA
- radare2
- Binwalk
- GDB
- strace
- ltrace
- patchelf
- file
- binutils
- ClamAV

### Fuzzing and compilation

- AFL++
- Clang
- LLVM

### Validation

- Trivy
- Gitleaks

The operator receives `NET_ADMIN` and `NET_RAW` because some network-analysis tooling requires them. Those capabilities remain scoped to the disposable operator container rather than the vulnerable target services.

## Defensive pipeline

`dpsr defend` creates a timestamped evidence run and coordinates the security-analysis workflow.

The pipeline records repository/runtime inventory, normalized findings, fuzz results, baseline state, and final stage status.

### Repository analysis

`dpsr review` runs the available analyzers and normalizes their output:

- Semgrep
- Gitleaks
- Trivy vulnerability/secret/misconfiguration scanning
- Bandit
- pip-audit when Python requirements are present

Unavailable analyzers are recorded as unavailable rather than silently treated as successful coverage.

### Validation and baselines

`dpsr validate` compares the current normalized finding set with previous state and records regression information. The pipeline distinguishes a complete validation from a run with no prior baseline.

### Fuzzing

`dpsr fuzz` executes bounded fuzz work and custom executable harnesses. Fuzz results are summarized and included in the pipeline record.

## Static artifact triage

`dpsr triage FILE` creates a dedicated evidence directory and performs static inspection without executing the supplied artifact.

Current collection includes:

- `file` identification
- `stat` filesystem metadata
- bounded printable-string extraction
- ExifTool metadata when available
- recursive YARA matching against local rules
- `readelf` structure
- `objdump` binary/object headers
- Binwalk embedded-content discovery
- normalized triage summary output

## Research cases

Research cases keep investigation state outside terminal history.

```bash
dpsr research new parser-review
dpsr research note parser-review "Reproduced malformed-input crash"
dpsr research task parser-review "Minimize crashing input"
dpsr research status parser-review
```

Cases maintain explicit state, notes, tasks, evidence, and output directories under `cases/`.

## Engagement workspaces

`dpsr new NAME` creates a scoped engagement workspace under `engagements/` for authorized assessment work. Engagement state is separated from general reports and research cases.

## Recon and range utilities

The security command surface includes dedicated entry points for:

- range lifecycle
- local range scanning
- reconnaissance
- Kali image build and operator shell
- code review
- validation
- fuzzing
- static triage
- evidence report generation
- engagement creation
- research-case management

## Evidence and persistence

Generated material is separated by purpose:

```text
reports/       scanner output, summaries, validation, pipeline records
cases/         persistent research cases, notes, tasks, evidence
engagements/   scoped authorized assessment workspaces
artifacts/     transient supplied or generated research material
loot/          transient research output excluded from normal source tracking
```

Structured state is written in machine-readable formats where automation matters and human-readable formats where review matters.

## Automation boundaries

### Console

The web console binds locally by default. State-changing actions are mapped to fixed server-side operations rather than accepting arbitrary shell commands.

### MCP

The MCP sidecar exposes structured tools for approved platform and security operations. Repository-path controls and lifecycle separation keep sensitive operations bounded.

### Out-of-band bridge

The GitHub issue bridge is independent of MCP and supports fixed recovery and maintenance tasks. Its allowlist includes diagnostics, status, sync, bootstrap, defensive analysis, validation, fuzzing, reporting, range lifecycle, Kali image refresh, system updates, disk maintenance, and Codespace lifecycle operations.

### Wake controller

Codespace wake/restart logic runs in GitHub Actions rather than inside the Codespace, preserving a recovery path when the runtime itself is unavailable.

## Continuous validation

The controller repository uses CI gates covering:

- Python compilation
- unit tests
- shell syntax
- ShellCheck
- Docker Compose validation
- Gitleaks
- Trivy
- Semgrep
- Bandit

Security assumptions and trust boundaries are intended to remain reviewable in source control alongside the code that enforces them.
