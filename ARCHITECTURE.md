# APOTHEON ONE Architecture

> **Unified. Elevated.**  
> Development & Security Platform by Digital Paragon

APOTHEON ONE is a development and security platform built around one managed control plane and several deliberately separated execution domains. Web, API, mobile, CI, automation, and authorized security-research workloads share project and job infrastructure without collapsing their trust boundaries into one unrestricted environment.

## Platform layers

```text
Project profiles
    ↓
Provisioners + project registry
    ↓
APOTHEON ONE control plane
    ↓
Bounded jobs + runner selection
    ↓
Local / Docker / GitHub-hosted execution
```

The security profile adds a separate operator and training-range boundary beneath the same management layer.

## Control plane

The host-side Python and shell tooling under `security_lab/`, `bin/`, `dashboard/`, and `platform/` provides:

- profile discovery and project provisioning;
- persistent project registration and job state;
- runner selection and external job refresh;
- local service state and health collection;
- structured MCP operations;
- the private APOTHEON ONE web console;
- supervised recovery and lifecycle controls; and
- the security research and evidence workflow.

Stateful parsing, validation, persistence, path checks, and security-sensitive decision logic live in testable code. Shell remains limited to process composition and system-tool integration where appropriate.

## Project profiles

APOTHEON ONE currently ships these built-in profiles:

- `fullstack-web`
- `nextjs`
- `fastapi`
- `flutter`
- `react-native`
- `android`
- `ios`
- `security`

Profiles define stack metadata, capabilities, runner policy, commands, ports, and scaffold behavior. Framework provisioning is implemented by platform-specific provisioners rather than generic placeholder templates.

## Job and runner boundary

Project commands execute as persisted jobs with explicit lifecycle state. Commands use pre-tokenized argument vectors and working-directory validation so execution cannot silently escape the registered project root.

Runner selection reflects actual platform requirements:

- local execution for compatible bounded development tasks;
- Docker where container isolation is appropriate;
- GitHub Actions for hosted CI and external workloads;
- GitHub-hosted macOS for native iOS validation.

Long-running development servers are kept separate from synchronous bounded job execution.

## Security invariants

The following properties are design constraints:

- Intentionally vulnerable HTTP services bind to loopback on the host.
- The vulnerable training range uses an internal Docker network without direct external egress.
- The Kali operator plane is separate from the internal range and receives only the capabilities required for network research.
- Browser-initiated operations map to fixed server-side actions rather than arbitrary shell input.
- Remote automation uses a structured task surface with explicit execution limits.
- Project command working directories are constrained to the registered project root.
- Managed recursive project deletion is allowed only after proving the target is inside the managed project root.
- Persistent state is written atomically where partial writes could corrupt later analysis.
- Untrusted artifacts are triaged statically and are not executed by the triage workflow.
- Runtime evidence, private notes, credentials, and case output are excluded from normal source tracking.
- CI treats syntax, secret detection, filesystem/configuration findings, and static-analysis findings as merge gates.

Changes that weaken one of these invariants should be explicit and accompanied by a concrete operational requirement.

## Security operator plane

The Kali container is disposable by design. The repository is mounted at `/workspace`, while the operator home directory is backed by a dedicated Docker volume.

The operator receives `NET_ADMIN` and `NET_RAW` because selected network-analysis tools require them. Those capabilities are scoped to the operator container rather than the vulnerable applications.

The operator is attached to both the isolated training range and a separate egress network. Vulnerable targets are attached only to the isolated range.

## Training range

The default range contains intentionally vulnerable applications used for repeatable local validation:

```text
Juice Shop  http://127.0.0.1:3000
DVWA        http://127.0.0.1:8080
WebGoat     http://127.0.0.1:8081
```

Resource limits and `no-new-privileges` reduce accidental host impact. These controls constrain the environment but do not make intentionally vulnerable applications safe.

## Evidence and research state

Generated material is separated by purpose:

- `reports/` for scanner output, normalized summaries, validation state, and generated evidence;
- `cases/` for persistent investigation metadata, notes, tasks, evidence, and output;
- `engagements/` for scoped workspaces used in authorized assessments;
- `artifacts/` and `loot/` for transient research material excluded from normal source tracking.

## Private console

The APOTHEON ONE console binds to `127.0.0.1:8765` by default. In Codespaces it is intended to be exposed only through a private forwarded port.

The HTTP surface performs origin checks, bounds request bodies, requires JSON for state-changing operations, sends restrictive browser security headers, and maps user actions to preconstructed argument vectors. There is no general arbitrary-command endpoint.

## Automation surfaces

The platform exposes complementary management paths:

- the private web console for interactive operation;
- the compatibility CLI for direct terminal control;
- MCP for structured automation;
- an independent GitHub recovery bridge; and
- an external lifecycle controller outside the Codespace.

The recovery path remains independent from MCP so the MCP service can itself be repaired or restarted when unavailable.
