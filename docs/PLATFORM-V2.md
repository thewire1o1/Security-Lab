# DPSR Platform v2

## Purpose

DPSR Platform v2 expands the existing security-research environment into a general development and automation control plane. The security lab remains intact as a first-class profile rather than being replaced.

## Branch strategy

`master` remains the stable control-plane branch. Platform work is developed and validated on `platform-v2` and merged only after CI and runtime checks pass. The legacy `sec` command remains available for compatibility.

## Control surfaces

- `dpsr` is the umbrella platform CLI.
- `sec` remains the security/research compatibility CLI.
- MCP remains the structured automation surface.
- The GitHub recovery bridge remains separate from MCP.
- The external lifecycle controller remains outside the Codespace.

## Project model

A managed project contains a `dpsr.toml` manifest. The manifest declares:

- project identity and profile
- runner type
- named commands with argv, working directory, and timeout
- service ports

Project registry and job state are stored outside the controller repository. In Codespaces the defaults are:

- projects: `/workspaces/dpsr-projects`
- platform state: `/workspaces/.dpsr/platform`

Both paths can be overridden with `DPSR_PROJECTS_ROOT` and `DPSR_PLATFORM_STATE`.

## Profiles

The initial built-in profile catalog includes:

- `security`
- `fullstack-web`
- `nextjs`
- `fastapi`
- `flutter`
- `react-native`
- `android`
- `ios`

Profiles are data files under `platform/profiles/`. They define stack metadata, capabilities, default runner, commands, ports, and scaffold layout.

## Runners

Phase 1 provides executable local and Docker runners. The runner boundary executes pre-tokenized argv vectors without invoking a shell and prevents command working directories from escaping the project root.

External runner identities are reserved for GitHub Actions and Codespaces. Native iOS is intentionally classified as an external/macOS workload rather than pretending the Linux Codespace can build it locally.

## Jobs

Commands execute as persisted jobs with explicit lifecycle state:

`queued -> running -> succeeded|failed`

Each job records project, command, timestamps, return code, and bounded stdout/stderr. Job state persists independently from a terminal session.

## CLI

```text
dpsr platform
dpsr profile list
dpsr profile show NAME
dpsr project init NAME --profile PROFILE
dpsr project register PATH
dpsr project list
dpsr project show NAME
dpsr project verify NAME
dpsr job run PROJECT COMMAND
dpsr job list
dpsr job show ID
dpsr runner list
```

Existing security commands continue to work through `dpsr` and `sec` unchanged.

## Next implementation layers

1. Framework-native bootstrap providers for Next.js, FastAPI, Flutter, React Native, Android, and full-stack compositions.
2. GitHub Actions and Codespaces runner backends with queued asynchronous job execution.
3. Platform-aware dashboard pages for projects, jobs, previews, deployments, and logs.
4. Structured MCP tools for project discovery, job submission, job status, and artifact retrieval.
5. Shared service management for databases, package caches, preview URLs, build artifacts, deployments, and environment configuration.
6. Deployment providers and release pipelines.
7. Central metrics, logs, health history, notifications, and automated recovery policies.

The architecture deliberately keeps these layers above the existing supervisor, recovery bridge, MCP server, and external lifecycle controller so the hardened management plane does not need to be redesigned.
