# Contributing to APOTHEON ONE

APOTHEON ONE combines development orchestration, hosted execution, security research, and recovery infrastructure. Changes should preserve that integration rather than optimizing one subsystem at the expense of another.

## Engineering rules

- Keep public identity as **APOTHEON ONE** with **Unified. Elevated.** and Digital Paragon in the maker position.
- Preserve documented compatibility contracts such as `dpsr`, `DPSR_*`, and `dpsr.toml` unless a migration is included.
- Keep browser, MCP, and remote-control surfaces structured and allowlisted. Do not introduce arbitrary shell execution through those interfaces.
- Keep recursive filesystem operations bounded to managed roots.
- Keep intentionally vulnerable services isolated and locally bound by default.
- Prefer explicit argv execution over shell interpolation.
- Add or update regression tests when behavior or a security boundary changes.
- Keep workflow permissions at the minimum required level and pin third-party GitHub Actions to immutable commit SHAs.

## Local verification

Run the same core checks expected by CI:

```bash
python3 -m compileall -q security_lab tests dashboard bin/sec-report
python3 -m unittest discover -s tests -v

for f in bin/* .devcontainer/*.sh; do
  [ -f "$f" ] || continue
  head -n 1 "$f" | grep -q 'bash' || continue
  bash -n "$f"
done

docker compose -f lab/docker-compose.yml --profile operator config --quiet
```

When ShellCheck is available:

```bash
for f in bin/* .devcontainer/*.sh; do
  [ -f "$f" ] || continue
  head -n 1 "$f" | grep -q 'bash' || continue
  shellcheck -S error -e SC1090,SC1091 "$f"
done
```

For a full environment check inside the configured workspace:

```bash
dpsr doctor
```

## Change boundaries

### Platform and provisioning

Changes under `security_lab/platform/` should maintain persistent project/job state, runner separation, safe path handling, explicit timeouts, and deterministic project manifests.

### Security system

Changes to the defensive pipeline, Kali operator plane, research cases, triage, fuzzing, or training range should document any new capability and its trust boundary.

### Recovery and automation

Changes to MCP, the GitHub issue bridge, wake workflows, or Codespace lifecycle controls require particular scrutiny because those components can operate when the primary runtime is unavailable.

### Public surfaces

README, documentation, workflow names, console labels, generated metadata, and diagnostic text are part of the product interface. The identity regression tests intentionally fail when historical product names reappear on primary public surfaces.

## Pull requests

A useful pull request explains:

1. what capability or defect changed
2. which trust boundary or compatibility contract is affected
3. how the change was validated
4. whether generated projects, hosted runners, or recovery behavior changed
5. whether documentation needs to move with the code

Large architectural changes should be split into reviewable units while keeping the repository runnable at each step.

## Security reports

Do not disclose exploitable vulnerabilities in a public pull request or issue. Follow [SECURITY.md](SECURITY.md).
