# APOTHEON ONE Platform

> **Unified. Elevated.**  
> Development & Security Platform by Digital Paragon

APOTHEON ONE expands the original security-research environment into a general development, automation, CI, and security control plane while preserving the security lab as a first-class isolated profile.

## Product model

A managed project has a platform profile and a `dpsr.toml` manifest. The manifest records project identity, runner type, named commands, working directories, timeouts, and service ports.

Project registry and job state live outside the controller repository. In Codespaces the defaults are:

- projects: `/workspaces/dpsr-projects`
- platform state: `/workspaces/.dpsr/platform`

Both paths can be overridden with `DPSR_PROJECTS_ROOT` and `DPSR_PLATFORM_STATE`.

## Built-in profiles

- `security`
- `fullstack-web`
- `nextjs`
- `fastapi`
- `flutter`
- `react-native`
- `android`
- `ios`

Profiles are data files under `platform/profiles/`. They define stack metadata, capabilities, default runner, commands, ports, and scaffold behavior.

## Provisioning

APOTHEON ONE includes framework-aware provisioners rather than generic placeholder scaffolds.

- **Next.js** uses the official project generator with explicit noninteractive options.
- **FastAPI** creates an isolated virtual environment, project dependencies, a health endpoint, and bounded validation jobs.
- **Full-stack web** composes Next.js and FastAPI with PostgreSQL, Dockerfiles, environment files, health routing, shared-package space, and infrastructure scaffolding.
- **Flutter** uses the official stable Flutter toolchain and generates mobile and web sources.
- **React Native** uses the current Community CLI with native Android and iOS projects.
- **Android** generates a native Kotlin project and routes compilation to hosted Linux CI.
- **iOS** generates SwiftUI and XcodeGen metadata and routes validation to a GitHub-hosted macOS runner.

See [Framework provisioning](../platform/PROVISIONING.md) and [Mobile provisioning](../platform/MOBILE.md).

## Jobs

Commands execute as persisted jobs with explicit lifecycle state:

```text
queued → running → succeeded | failed
```

Each job records its project, command, timestamps, return code, and bounded output. Job state survives terminal sessions.

## Runners

APOTHEON ONE separates workload identity from execution location.

- **Local** for compatible bounded project commands.
- **Docker** for isolated container execution.
- **GitHub Actions** for hosted and asynchronous workloads.
- **macOS hosted runners** for native iOS validation where Xcode is actually available.

Project commands use pre-tokenized argument vectors and validated working directories instead of shell interpolation.

## Repository publishing

Managed projects can be bound to repositories and published through the platform's repository integration. External GitHub Actions jobs are persisted and refreshed back into APOTHEON ONE job state so hosted execution remains visible from the same control plane.

## Control surfaces

APOTHEON ONE can be operated through:

- the private browser console;
- the compatibility CLI;
- structured MCP tools; and
- the independent recovery bridge for lifecycle repair.

The browser and MCP surfaces expose predefined operations rather than a general arbitrary shell.

## Project lifecycle

```text
select profile
    ↓
provision project
    ↓
write manifest
    ↓
register project
    ↓
verify stack
    ↓
run bounded job
    ↓
select local / Docker / hosted runner
    ↓
persist job state and output
```

## Managed deletion boundary

Removing a project from the registry leaves its files untouched.

Recursive project deletion is available only after the platform resolves and proves that the registered project is a child of the managed project root. Externally registered paths cannot be recursively deleted by that operation.

## Compatibility

The existing `dpsr` command remains the current CLI entry point so established scripts and security workflows continue to function. APOTHEON ONE is the product identity presented by the console and platform APIs.
