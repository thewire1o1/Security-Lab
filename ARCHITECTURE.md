# DPSR Architecture

Digital Paragon Security Research is structured as a controlled research environment rather than a general-purpose attack platform. The design keeps orchestration, operator tooling, vulnerable targets, and evidence storage in separate trust domains so the assumptions around each component remain reviewable.

## Security invariants

The following properties are treated as design constraints rather than deployment preferences:

- Intentionally vulnerable HTTP services bind to loopback on the host.
- The vulnerable training range uses an internal Docker network without direct external egress.
- The Kali operator plane is separate from the internal range and receives only the capabilities required for network research.
- Browser-initiated operations map to a fixed server-side allowlist; request data is never interpolated into a shell command.
- Remote automation accepts a fixed task vocabulary and bounds command execution with explicit timeouts.
- Persistent state is written atomically where partial writes could corrupt later analysis.
- Untrusted artifacts are triaged statically. Triage does not execute supplied files.
- Runtime evidence, private notes, credentials, and case output are excluded from normal source tracking.
- CI treats syntax, secret detection, filesystem/configuration findings, and static-analysis findings as merge gates.

Changes that weaken one of these invariants should be explicit in review and accompanied by a concrete operational requirement.

## Control plane

The control plane is the host-side Python and shell tooling under `security_lab/`, `bin/`, and `dashboard/`.

Its responsibilities are intentionally narrow:

- orchestrate the local training range;
- collect service and tool state;
- normalize scanner output;
- maintain research-case metadata;
- produce evidence artifacts;
- expose allowlisted operations through the local web console; and
- coordinate bounded remote maintenance tasks.

Shell is retained for process composition and system tooling. Stateful parsing, validation, persistence, and security-sensitive decision logic live in Python where they can be unit tested directly.

## Operator plane

The Kali container is disposable by design. The repository is mounted at `/workspace`, while the operator home directory is backed by a dedicated Docker volume.

The operator receives `NET_ADMIN` and `NET_RAW` because several network-analysis tools require those capabilities. Those capabilities are scoped to the operator container rather than the vulnerable applications.

The operator is attached to both the isolated training range and a separate egress network. Vulnerable targets are attached only to the isolated range.

## Training range

The default range contains intentionally vulnerable applications used for repeatable local validation:

```text
Juice Shop  http://127.0.0.1:3000
DVWA        http://127.0.0.1:8080
WebGoat     http://127.0.0.1:8081
```

Resource limits and `no-new-privileges` are applied to reduce accidental host impact. These controls do not make the applications safe; they constrain the environment in which intentionally unsafe software runs.

## Evidence and research state

Generated material is separated by purpose:

- `reports/` — scanner output, normalized summaries, validation state, and generated evidence;
- `cases/` — persistent investigation metadata, notes, tasks, evidence, and output;
- `engagements/` — scoped workspaces for authorized assessments;
- `artifacts/` and `loot/` — transient research material excluded from normal source tracking.

Structured state uses JSON where machine processing matters and Markdown/plain text where human review is the primary use case.

## Defensive pipeline

`dpsr defend` coordinates the defensive workflow:

1. capture repository and runtime inventory;
2. run source, secret, configuration, and filesystem analyzers;
3. execute bounded local fuzzing and custom harnesses;
4. compare normalized findings with the previous baseline; and
5. finalize a machine-readable pipeline record.

An external review hook may be configured locally. The repository does not hard-code a provider or transmit findings unless the operator explicitly configures that integration.

## Operations console

The console binds to `127.0.0.1:8765` by default. In Codespaces it is intended to be exposed only through a private forwarded port.

The HTTP surface performs origin checks, bounds request bodies, requires JSON for state-changing operations, sends restrictive browser security headers, and maps user actions to preconstructed argv tuples. There is no endpoint for arbitrary command execution.

## Commenting standard

Source comments document **security assumptions, invariants, protocol constraints, and non-obvious failure behavior**. They should not narrate straightforward code.

Scanner suppressions are kept local to the exact expression that requires them and include enough context for a reviewer to determine why the flagged primitive is safe in this usage. If the safety argument cannot be stated precisely, the suppression should not exist.
