# APOTHEON ONE

### Unified. Elevated.

**Development & Security Platform**  
by **Digital Paragon** · *Information Technology Excellence*

Created by **TheWire1o1** · James Porath

[![APOTHEON ONE CI](https://github.com/thewire1o1/Security-Lab/actions/workflows/ci.yml/badge.svg)](https://github.com/thewire1o1/Security-Lab/actions/workflows/ci.yml)

**APOTHEON ONE is a unified engineering control plane for building, validating, running, automating, and researching software across full-stack web, mobile, hosted CI, and isolated security environments.**

It combines framework-native provisioning, persistent project and job state, local/Docker/GitHub-hosted execution, a private operations console, structured MCP automation, out-of-band recovery, and a complete security research environment behind one reviewed control plane.

The platform began as a serious security lab. That system remains intact. APOTHEON ONE expands it into a broader engineering environment without reducing the security side to a demo or removing the boundaries that made it useful.

**APOTHEON** represents elevation toward the highest attainable form. **ONE** represents convergence: one environment, one control plane, and one coherent system. **Unified. Elevated.** compresses both ideas into the operating philosophy of the platform.

---

## What APOTHEON ONE contains

| System | Production behavior |
| --- | --- |
| **Full-stack provisioning** | Generates integrated Next.js + FastAPI projects with PostgreSQL, Dockerfiles, Compose, environment scaffolding, health routing, and bounded build/test/lint jobs |
| **Framework-native projects** | Provisions Next.js and FastAPI through real framework toolchains rather than placeholder directory templates |
| **Mobile engineering** | Generates Flutter, React Native, native Android, and native iOS projects with Linux/macOS runner routing based on actual platform requirements |
| **Project registry** | Tracks managed projects, manifests, profiles, repository bindings, commands, runner type, ports, and persistent lifecycle state |
| **Job engine** | Persists queued/running/succeeded/failed jobs with timestamps, return codes, bounded output, and external workflow identity |
| **GitHub Actions runner** | Publishes managed projects, dispatches generated workflows, discovers delayed run IDs, and refreshes external job state |
| **Private console** | Unified views for Overview, Projects, Development, Mobile, Security, Jobs, Infrastructure, and Activity |
| **MCP control plane** | Exposes structured project, job, repository, platform, security, and lifecycle operations without an arbitrary browser shell |
| **Recovery plane** | Keeps wake/recovery control outside the Codespace runtime so the environment can be recovered even when the main process is unavailable |
| **Security research environment** | Isolated vulnerable targets, disposable Kali operator plane, defensive analysis, recon, fuzzing, static artifact triage, research cases, engagements, validation, and evidence generation |

---

# Platform architecture

```text
                              GITHUB
                 ┌────────────────────────────┐
                 │ Actions · Repositories · CI│
                 └──────────────┬─────────────┘
                                │
                     hosted jobs / recovery
                                │
┌───────────────────────────────▼────────────────────────────────┐
│                    APOTHEON ONE CONTROL PLANE                  │
│                                                                │
│   Private Console         CLI                MCP               │
│         │                 │                   │                │
│         └─────────────────┼───────────────────┘                │
│                           │                                    │
│       ┌───────────────────┼─────────────────────┐              │
│       │                   │                     │              │
│  Project Registry     Persistent Jobs      Runner Layer        │
│       │                   │             local · Docker · hosted│
└───────┼───────────────────┼─────────────────────┼──────────────┘
        │                   │                     │
        ▼                   ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌──────────────────────┐
│ Web / API     │   │ Mobile        │   │ Security Profile     │
│ Full-stack    │   │ iOS / Android │   │ isolated research    │
└───────────────┘   └───────────────┘   └──────────┬───────────┘
                                                   │
                              ┌────────────────────┼──────────────────┐
                              ▼                    ▼                  ▼
                         Kali Operator       Training Range      Evidence State
                                              Juice Shop         Reports / Cases
                                              DVWA               Engagements
                                              WebGoat            Artifacts
```

The general development plane and security profile share orchestration, observability, job persistence, and automation. The vulnerable range and operator environment retain explicit trust boundaries.

---

# Development platform

## Full-stack web

The `fullstack-web` profile creates an integrated application rather than a pair of unrelated sample folders:

- Next.js application under `apps/web`
- FastAPI service under `apps/api`
- PostgreSQL service and persistent volume in `compose.yaml`
- generated local database credentials in ignored `.env`
- credential-free `.env.example`
- Dockerfiles for both application tiers
- Next.js backend-health route wired through `API_INTERNAL_URL`
- shared package and infrastructure areas
- bounded `lint`, `test`, `build`, and separate `container-build` jobs

Ordinary verification validates the application and Compose definition without forcing a full image build every time.

## Next.js

Provisioning uses the official `create-next-app` flow with explicit noninteractive configuration:

- TypeScript
- ESLint
- Tailwind CSS
- App Router
- `src/` layout
- Turbopack
- npm
- nested Git initialization disabled

APOTHEON ONE then registers and verifies the generated project through its bounded job layer.

## FastAPI

The FastAPI profile creates an isolated virtual environment, installs project-local dependencies, writes a health endpoint and pytest health check, and exposes bounded lint/test execution through the same persistent job model.

## Mobile

Mobile projects are treated as first-class workloads rather than pretending every build can happen inside one Linux container.

| Profile | Provisioning / execution model |
| --- | --- |
| **Flutter** | Uses a stable Flutter SDK, generates Android/iOS/web sources, runs analyze/test/web build locally, and emits CI support |
| **React Native** | Uses the React Native Community CLI, installs npm dependencies, keeps native Android/iOS projects, and runs local lint/test validation |
| **Android** | Generates native Kotlin with API 37, Android Gradle Plugin 9.3, Gradle 9.5, and routes native compilation to Ubuntu GitHub Actions |
| **iOS** | Generates SwiftUI + XcodeGen metadata and routes simulator builds to a GitHub-hosted macOS runner with signing disabled for CI |

Failed managed-project provisioning is cleaned only inside the managed project root. Externally registered project paths are not recursively removed by the provisioner.

---

# Persistent execution model

A managed project declares its platform contract in `dpsr.toml`:

```text
identity + profile
        │
        ├── commands (pre-tokenized argv)
        ├── working directories
        ├── execution timeouts
        ├── service ports
        └── runner identity
```

Project jobs follow an explicit persistent lifecycle:

```text
queued → running → succeeded | failed
```

Commands execute without shell interpolation inside bounded project roots. Native or platform-specific work can be routed to GitHub-hosted runners instead of faking support inside the Linux control plane.

Project and job state persists outside terminal sessions, giving the platform a durable operational view rather than relying on shell history.

---

# Security research system

Security is a complete APOTHEON ONE subsystem, not a feature tile attached to the development platform.

## Isolated training range

The default range contains three intentionally vulnerable applications for repeatable local research and validation:

| Target | Host binding |
| --- | --- |
| OWASP Juice Shop | `127.0.0.1:3000` |
| DVWA | `127.0.0.1:8080` |
| WebGoat | `127.0.0.1:8081` |

The vulnerable applications are attached to an internal Docker network and are not given direct external egress. Host bindings remain local by default.

## Disposable Kali operator plane

The operator environment is a dedicated Kali Rolling container separated from the vulnerable applications. It carries the capabilities required for network research without granting those capabilities to the target services.

The current image includes tooling across the following domains.

**Web / discovery**

`kali-tools-top10` · `feroxbuster` · `gobuster` · `whatweb` · `wafw00f` · `wpscan` · `testssl.sh` · `theHarvester` · `Recon-ng` · `SecLists`

**Identity / Windows / directory services**

`BloodHound` · `Impacket` · `enum4linux-ng` · `Evil-WinRM` · `Kerberoast` · `krbrelayx` · `mitm6` · `smbclient` · LDAP tooling

**Network / pivoting / inspection**

`Ligolo-ng` · `proxychains4` · `sshuttle` · `socat` · `netcat` · `tshark` · SNMP tooling · `nbtscan` · `onesixtyone`

**Reverse engineering / artifact analysis**

`YARA` · `radare2` · `Binwalk` · `GDB` · `strace` · `ltrace` · `patchelf` · `file` · `binutils` · ClamAV

**Fuzzing / compilation**

`AFL++` · `Clang` · `LLVM`

**Security validation**

`Trivy` · `Gitleaks`

## Defensive analysis pipeline

`dpsr defend` coordinates a reproducible defensive run and writes timestamped evidence under `reports/`.

The pipeline records:

1. repository and runtime inventory
2. Semgrep source analysis
3. Gitleaks credential/secret detection
4. Trivy vulnerability, secret, and misconfiguration scanning
5. Bandit Python security analysis
6. `pip-audit` when a Python requirements file is present
7. normalized finding summaries and severity counts
8. bounded fuzzing results
9. baseline comparison and regression state
10. optional locally configured external review status
11. final machine-readable pipeline state

Individual stages remain callable when isolating a result:

```bash
dpsr review
dpsr validate
dpsr fuzz
dpsr report
```

## Static artifact triage

Supplied files are inspected statically. The triage path does not execute the submitted artifact.

Current triage captures:

- file identification
- filesystem metadata
- printable strings
- ExifTool metadata when available
- recursive YARA matching against local rules
- ELF structure via `readelf`
- object/binary headers through `objdump`
- embedded-content discovery with Binwalk
- normalized triage summaries and evidence output

```bash
dpsr triage path/to/sample
```

## Fuzzing

APOTHEON ONE supports bounded fuzz execution and custom executable harnesses. Harness output is written into the current run and summarized into the same evidence model as the rest of the defensive pipeline.

## Research cases

Research state survives terminal sessions. Cases carry explicit notes, tasks, evidence, and output directories rather than relying on shell history or scratch files.

```bash
dpsr research new parser-review
dpsr research note parser-review "Reproduced malformed-input crash"
dpsr research task parser-review "Minimize crashing input"
dpsr research status parser-review
```

## Engagement workspaces

Scoped engagement workspaces are separate from runtime reports and cases, giving authorized assessment work its own persistent boundary.

## Recon and range operations

The repository retains dedicated `recon`, `labscan`, range lifecycle, Kali lifecycle, engagement, reporting, and research entry points in addition to the unified platform CLI.

---

# Automation and recovery

## Structured MCP

The MCP sidecar exposes structured tools for platform state, repository operations, projects, jobs, service status, and approved lifecycle actions. Browser and MCP surfaces do not accept arbitrary shell text and interpolate it into commands.

## Out-of-band GitHub bridge

APOTHEON ONE keeps a separate GitHub issue-based recovery path outside the MCP process. It can remain usable when MCP itself is unhealthy and uses a fixed task vocabulary with explicit execution timeouts.

Current remote tasks include environment diagnostics, status, repository sync, bootstrap, defensive analysis, validation, fuzzing, reporting, training-range lifecycle, Kali image refresh, system updates, disk maintenance, and Codespace lifecycle operations.

## Wake controller

Codespace wake/restart control runs in GitHub Actions, outside the Codespace it manages. That keeps the recovery path available when nothing inside the environment can answer.

---

# Continuous validation

The controller repository is continuously checked with:

- Python compilation
- unit tests
- shell syntax validation
- ShellCheck
- Docker Compose validation
- Gitleaks
- Trivy
- Semgrep
- Bandit

Security findings and environment validation are part of the repository workflow rather than a documentation-only policy.

---

# Control surfaces

```text
dpsr platform                  platform summary
dpsr profile list              built-in project profiles
dpsr project init              provision a managed project
dpsr project register          register an existing project
dpsr project verify            execute profile verification
dpsr job run                   run a bounded project command
dpsr job list                  inspect persistent job history
dpsr runner list               inspect execution backends

dpsr up                        start the isolated training range
dpsr down                      stop the training range
dpsr scan                      scan the local training range
dpsr defend                    run the complete defensive pipeline
dpsr review                    repository security analysis
dpsr validate                  compare findings with baseline
dpsr fuzz                      bounded fuzzing + custom harnesses
dpsr triage FILE               static artifact triage
dpsr research ...              persistent research cases
dpsr new NAME                  create an engagement workspace
dpsr kali                      enter the operator plane
dpsr kali-build                refresh the Kali image
dpsr gui                       launch the private APOTHEON ONE console
dpsr mcp ACTION                manage the MCP sidecar
```

The lower-level `sec` command and `dpsr` / `DPSR_*` compatibility identifiers remain where existing automation depends on them. They are implementation contracts, not the public product identity.

---

# Repository map

```text
platform/                  profile definitions + platform documentation
security_lab/platform/     provisioning, jobs, runners, registry, mobile, GitHub Actions
security_lab/              security pipeline, research, reporting, MCP, recovery, console backend
lab/                       isolated training range + Kali operator image
bin/                       platform/security command entry points
dashboard/                 private APOTHEON ONE console
docs/                      platform, recovery, bridge, and public presentation
.github/workflows/         CI, Kali image, wake and recovery automation
tests/                     regression coverage for platform and control-plane behavior
```

---

# Documentation

- [APOTHEON ONE platform architecture](docs/PLATFORM.md)
- [Security research subsystem](docs/SECURITY-RESEARCH.md)
- [Trust boundaries and security architecture](ARCHITECTURE.md)
- [Framework provisioning](platform/PROVISIONING.md)
- [Mobile provisioning](platform/MOBILE.md)
- [MCP bridge](docs/MCP_BRIDGE.md)
- [Wake controller](docs/WAKE-CONTROLLER.md)

---

**APOTHEON ONE** · **Unified. Elevated.**  
A Development & Security Platform by **Digital Paragon**.  
*Information Technology Excellence.*

Created by **TheWire1o1** · James Porath
