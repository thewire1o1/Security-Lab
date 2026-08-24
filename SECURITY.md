# APOTHEON ONE Security Policy

Security defects in APOTHEON ONE are handled as engineering issues with coordinated disclosure. The intentionally vulnerable training range is not itself a vulnerability in the platform when it behaves within its documented isolation boundaries.

## Supported branch

Security fixes target the current `master` branch. Historical commits, abandoned development branches, and disposable generated fixtures are not maintained as supported releases.

## Report a vulnerability

Do not publish exploitable details in a public issue, discussion, or pull request.

Use GitHub private vulnerability reporting for this repository when that option is available. If private reporting is unavailable, open a minimal issue requesting a private contact path and do not include exploit details, credentials, sensitive logs, or proof-of-concept material in the public issue.

A useful report includes:

- affected component and file path
- exact commit or revision tested
- required configuration and preconditions
- reproducible steps
- security boundary crossed
- realistic impact
- proof of concept when it can be shared safely
- suggested remediation, if known

## In scope

Examples include:

- arbitrary command execution through a surface intended to be allowlisted or structured
- path traversal or managed-root escape
- credential or token exposure
- cross-origin or authorization bypass in the private console or MCP surface
- unsafe repository, runner, or workflow dispatch behavior
- isolation failures that expose intentionally vulnerable targets beyond their documented boundary
- recovery-plane actions that exceed their declared task vocabulary
- unsafe generated project defaults introduced by APOTHEON ONE itself

## Intentionally vulnerable components

OWASP Juice Shop, DVWA, WebGoat, and similar training targets are present specifically for authorized research. Vulnerabilities inside those applications are expected and should be reported to their upstream projects, not as APOTHEON ONE defects.

An APOTHEON ONE security issue exists when platform behavior breaks the containment or trust boundary around those targets, exposes them contrary to configuration, or grants unintended capability to another component.

## Disclosure expectations

Please allow reasonable time to reproduce, remediate, validate, and release a fix before public disclosure. Reports are evaluated on reproducibility, boundary impact, and practical exploitability.

## Authorized use

APOTHEON ONE is intended for owned systems, isolated training environments, and explicitly authorized security work. Repository tooling does not grant authorization to test third-party systems.
