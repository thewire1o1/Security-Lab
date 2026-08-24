<div align="center">

# APOTHEON ONE

### Unified. Elevated.

**Development & Security Platform**  
by **Digital Paragon** · *Information Technology Excellence*

Created by **TheWire1o1** · James Porath

[![APOTHEON ONE CI](https://github.com/thewire1o1/Security-Lab/actions/workflows/ci.yml/badge.svg)](https://github.com/thewire1o1/Security-Lab/actions/workflows/ci.yml)

**Build · Validate · Research · Recover**

[Architecture](ARCHITECTURE.md) · [Platform](docs/PLATFORM.md) · [Security](docs/SECURITY-RESEARCH.md) · [Contributing](CONTRIBUTING.md) · [Security Policy](SECURITY.md)

</div>

---

## What APOTHEON ONE is

**APOTHEON ONE is a unified engineering control plane for building, validating, running, automating, securing, and researching software across full-stack web, mobile, hosted CI, containerized infrastructure, and isolated security environments.**

It began as a serious security lab and expanded without sacrificing the boundaries that made the original system useful. Development, security, automation, recovery, and execution now operate as one platform rather than a pile of disconnected scripts.

**APOTHEON** represents elevation toward the highest attainable form. **ONE** represents convergence: one environment, one control plane, one coherent system. **Unified. Elevated.** is the operating principle behind the platform.

### The four operating planes

| Plane | Responsibility |
| --- | --- |
| **Control** | Private console, CLI, MCP, project registry, job state, orchestration |
| **Execution** | Local processes, Docker, GitHub-hosted Linux/macOS runners, generated project CI |
| **Security** | Isolated training range, Kali operator environment, defensive analysis, fuzzing, triage, research state |
| **Recovery** | Out-of-band GitHub bridge, wake controller, Codespace lifecycle, environment repair |

The point is not to make every subsystem identical. The point is to make them **coherent, observable, bounded, and operable from one architecture**.

---

## Capability map

| System | What it does |
| --- | --- |
| **Full-stack provisioning** | Generates integrated Next.js + FastAPI systems with PostgreSQL, Dockerfiles, Compose, environment scaffolding, health routing, and bounded verification jobs |
| **Framework-native development** | Uses real framework toolchains instead of placeholder project templates |
| **Mobile engineering** | Provisions Flutter, React Native, native Android, and native iOS projects with runner selection based on actual platform requirements |
| **Project registry** | Persists project identity, profile, repository binding, commands, services, runner type, and lifecycle state |
| **Job engine** | Tracks queued, running, succeeded, and failed work with timestamps, bounded output, return codes, and hosted-run identity |
| **Hosted execution** | Publishes managed projects, dispatches GitHub Actions, discovers delayed run IDs, and refreshes external job state |
| **Private console** | Presents operational state across projects, development, mobile, security, jobs, infrastructure, and activity |
| **Structured MCP** | Exposes typed platform and repository operations without turning the browser or MCP surface into an arbitrary shell |
| **Security research system** | Runs isolated vulnerable targets, a disposable Kali operator plane, recon, defensive analysis, fuzzing, triage, validation, cases, and evidence workflows |
| **Recovery plane** | Keeps critical wake and repair capability outside the runtime it manages |

---

## Architecture

```text
                                   GITHUB
                    ┌──────────────────────────────┐
                    │ Repositories · Actions · CI │
                    └───────────────┬──────────────┘
                                    │
                         hosted execution / recovery
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                         APOTHEON ONE CONTROL PLANE                    │
│                                                                        │
│      Private Console              CLI                 MCP              │
│             │                     │                    │               │
│             └─────────────────────┼────────────────────┘               │
│                                   │                                    │
│        ┌──────────────────────────┼──────────────────────────┐         │
│        │                          │                          │         │
│  Project Registry          Persistent Jobs             Runner Layer    │
│        │                          │              local · Docker · hosted│
└────────┼──────────────────────────┼──────────────────────────┼─────────┘
         │                          │                          │
         ▼                          ▼                          ▼
┌────────────────┐        ┌────────────────┐        ┌────────────────────┐
│ Web / API      │        │ Mobile         │        │ Security Profile   │
│ Full-stack     │        │ iOS / Android  │        │ isolated research  │
└────────────────┘        └────────────────┘        └─────────┬──────────┘
                                                             │
                              ┌──────────────────────────────┼─────────────────────┐
                              ▼                              ▼                     ▼
                       Kali Operator                  Training Range          Evidence State
                                                     Juice Shop             Reports
                                                     DVWA                   Cases
                                                     WebGoat                Engagements
                                                                            Artifacts
```

Development and security share orchestration, observability, job persistence, and automation. Vulnerable targets and operator tooling retain explicit trust boundaries instead of being flattened into the same privilege domain.

For the security model and invariants, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

# Development system

## Full-stack web

The `fullstack-web` profile creates an integrated application system:

- Next.js under `apps/web`
- FastAPI under `apps/api`
- PostgreSQL in `compose.yaml`
- ignored local `.env`
- credential-free `.env.example`
- Dockerfiles for both application tiers
- backend health routing through `API_INTERNAL_URL`
- shared package, infrastructure, and tooling areas
- bounded `lint`, `test`, `build`, and container-build jobs

The generated stack is intended to be operated and verified, not merely scaffolded.

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

## FastAPI

The FastAPI profile creates a project-local virtual environment, installs isolated dependencies, writes a health endpoint and test, and exposes bounded verification through the same persistent job model used by the rest of the platform.

## Mobile

APOTHEON ONE treats mobile as real native work rather than pretending every build belongs inside one Linux container.

| Profile | Provisioning / execution model |
| --- | --- |
| **Flutter** | Stable Flutter SDK, Android/iOS/web sources, analyze/test/web build, generated CI support |
| **React Native** | Community CLI, npm dependencies, native Android/iOS projects, local lint/test validation |
| **Android** | Kotlin, API 37, AGP 9.3, Gradle 9.5, native build routed to GitHub-hosted Ubuntu |
| **iOS** | SwiftUI + XcodeGen, simulator build routed to GitHub-hosted macOS with signing disabled for CI |

---

# Persistent execution

Managed projects declare their execution contract in `dpsr.toml`:

```text
identity + profile
        │
        ├── commands as pre-tokenized argv
        ├── bounded working directories
        ├── explicit timeouts
        ├── service ports
        └── runner identity
```

Jobs persist through an explicit lifecycle:

```text
queued → running → succeeded | failed
```

This is deliberately different from terminal history. Project and job state survives shell sessions, and hosted jobs retain external workflow identity so the control plane can reconcile them later.

The `dpsr` command, `DPSR_*` variables, and `dpsr.toml` remain compatibility contracts. They are not the public product identity.

---

# Security system

Security is a complete APOTHEON ONE subsystem, not a decorative feature attached to the development platform.

## Isolated training range

| Target | Host binding |
| --- | --- |
| OWASP Juice Shop | `127.0.0.1:3000` |
| DVWA | `127.0.0.1:8080` |
| WebGoat | `127.0.0.1:8081` |

The intentionally vulnerable applications are placed on an internal Docker network and are not given direct external egress. Host bindings remain local by default.

## Disposable Kali operator plane

The operator environment is separate from vulnerable targets and carries the capabilities required for authorized research without granting those capabilities to the target services.

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
`Trivy` · `Gitleaks` · Semgrep · Bandit · `pip-audit`

## Defensive pipeline

```bash
dpsr defend
```

A defensive run records:

1. repository and runtime inventory
2. Semgrep source analysis
3. Gitleaks secret detection
4. Trivy vulnerability, secret, and misconfiguration analysis
5. Bandit Python security analysis
6. `pip-audit` when Python requirements are present
7. normalized scanner coverage and finding severity
8. bounded fuzzing results
9. validation baseline and regression state
10. optional external review status
11. final machine-readable pipeline state

Individual stages remain callable:

```bash
dpsr review
dpsr validate
dpsr fuzz
dpsr report
```

## Static artifact triage

```bash
dpsr triage path/to/sample
```

Triage is static and does not execute the supplied artifact. It can collect hashes, file identification, filesystem metadata, printable strings, ExifTool metadata, YARA results, ELF/object structure, and embedded-content discovery.

## Research state

Cases survive terminal sessions with explicit notes, tasks, evidence, and output directories:

```bash
dpsr research new parser-review
dpsr research note parser-review "Reproduced malformed-input crash"
dpsr research task parser-review "Minimize crashing input"
dpsr research status parser-review
```

Scoped engagement workspaces remain separate from runtime reports and case state.

---

# Security engineering posture

APOTHEON ONE treats repository security controls as executable engineering, not README promises.

Current controls include:

- Python compilation and unit regression tests
- shell syntax validation and ShellCheck
- Docker Compose validation
- Gitleaks secret scanning
- Trivy vulnerability, secret, and misconfiguration scanning
- Semgrep static analysis
- Bandit Python security analysis
- CodeQL semantic analysis for Python and JavaScript/TypeScript
- dependency review on pull requests
- Dependabot updates
- least-privilege workflow permissions
- immutable commit pinning for third-party GitHub Actions
- CI concurrency cancellation and job timeouts
- identity regression tests preventing historical public branding from reappearing

Security disclosure and scope are documented in [SECURITY.md](SECURITY.md).

---

# Automation and recovery

## Structured MCP

The MCP sidecar exposes structured operations for platform state, repositories, projects, jobs, service status, and approved lifecycle actions. It does not accept arbitrary shell text and interpolate it into commands.

## Out-of-band GitHub bridge

The issue-based recovery path is separate from MCP. It uses a fixed task vocabulary and explicit execution timeouts so critical operations remain available even if the normal process is unhealthy.

## Wake controller

Codespace wake and recovery logic runs in GitHub Actions, outside the Codespace it manages. The recovery path therefore does not depend on the primary runtime being responsive.

---

# Control surface

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
dpsr kali-build                refresh the security operator image
dpsr gui                       launch the private APOTHEON ONE console
dpsr mcp ACTION                manage the MCP sidecar
```

---

# Repository map

```text
platform/                  profile definitions + platform documentation
security_lab/platform/     provisioning, jobs, runners, registry, mobile, GitHub Actions
security_lab/              security pipeline, research, reporting, MCP, recovery, console backend
lab/                       isolated training range + security operator image
bin/                       platform/security command entry points
dashboard/                 private APOTHEON ONE console
docs/                      platform, recovery, bridge, and public presentation
.github/workflows/         CI, semantic analysis, dependency review, image, wake, recovery
tests/                     regression coverage for platform and control-plane behavior
```

---

# Documentation

- [Platform architecture](docs/PLATFORM.md)
- [Security research subsystem](docs/SECURITY-RESEARCH.md)
- [Trust boundaries and security architecture](ARCHITECTURE.md)
- [Framework provisioning](platform/PROVISIONING.md)
- [Mobile provisioning](platform/MOBILE.md)
- [MCP bridge](docs/MCP_BRIDGE.md)
- [Wake controller](docs/WAKE-CONTROLLER.md)
- [Contribution guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)

---

<div align="center">

**APOTHEON ONE** · **Unified. Elevated.**  
Development & Security Platform by **Digital Paragon**  
*Information Technology Excellence*

Created by **TheWire1o1** · James Porath

</div>
