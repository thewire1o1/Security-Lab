# Security Lab

A reproducible GitHub Codespaces security workstation with a maintainable host, a disposable Kali operator layer, isolated vulnerable targets, defensive automation, research-state tracking, evidence collection, and a private Mission Control interface.

## Core workflow

```bash
source ~/.bashrc
sec doctor
sec up
sec defend
sec gui
```

`sec defend` creates a timestamped run under `reports/defense-*` and executes inventory, repository review, bounded fuzzing, and baseline validation.

## Repository review

```bash
sec review
```

The review stage uses available local analyzers to inspect source, configuration, dependencies, credentials, and filesystem content. Current integrations include Semgrep, Bandit, Gitleaks, Trivy, and pip-audit when a Python requirements file is present.

Each run produces machine-readable JSON plus a normalized `summary.json` with severity counts.

## Validation and retest

```bash
sec validate
```

Validation compares the newest defensive summary with the prior run. `validation.json` records severity deltas, whether high-severity findings regressed, and whether the current run improved.

## Fuzzing

```bash
sec fuzz
```

The default fuzz stage performs bounded web-content fuzzing against the three local training targets when they are online. Executable custom harnesses under `fuzz/harnesses/` are also discovered and run with a fixed timeout.

## Static artifact triage

```bash
sec triage sample.bin
```

The triage workflow records SHA-256, file type, filesystem metadata, strings, and available binary-analysis output. YARA, Binwalk, readelf, objdump, and metadata extraction are used when installed. Files are inspected statically and are not executed.

## Research state

```bash
sec research new case-name
sec research note case-name "Observation"
sec research task case-name "Next experiment"
sec research status case-name
sec research close case-name
```

Each case keeps state in `cases/<name>/` with separate notes, tasks, evidence, and output directories. This makes multi-session vulnerability research reproducible instead of depending on terminal history.

## External review hook

`sec engine` is a generic local hook. When `SEC_ANALYSIS_COMMAND` is configured outside the repository, the command receives a review summary path as its argument. The repository does not require a specific external service.

## Mission Control

```bash
sec gui
```

Mission Control binds to `127.0.0.1:8765` and exposes fixed local actions for the training range and defensive pipeline. It reports:

- Juice Shop, DVWA, WebGoat, and Kali status
- container CPU and memory telemetry
- current finding severity totals
- latest pipeline stage state
- stored run history
- research-case count
- host tool inventory
- live activity log

The HTTP backend does not accept arbitrary shell commands.

## Kali operator layer

```bash
sec kali-build
sec kali
```

The operator image is based on Kali Rolling. It includes network and web assessment tooling, identity and protocol tooling, reverse-engineering utilities, static artifact triage, YARA, Binwalk, GDB, radare2, AFL++, Clang, LLVM, Trivy, and Gitleaks.

The repository is mounted at `/workspace`. The container is disposable, while `/root` persists in its own Docker volume.

## Local training range

```text
Juice Shop  http://127.0.0.1:3000
DVWA        http://127.0.0.1:8080
WebGoat     http://127.0.0.1:8081
```

All targets and the operator container share the private `security-lab` Docker network.

## Continuous validation

`.github/workflows/ci.yml` performs syntax checks, ShellCheck, Compose validation, Gitleaks history scanning, Trivy filesystem scanning, Semgrep, and Bandit.

## Persistence

Environment definitions live in git. Runtime evidence, cases, artifacts, and private material remain outside normal source tracking through `.gitignore`.
