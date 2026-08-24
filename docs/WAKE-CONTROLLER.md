# DPSR Wake Controller

The wake controller runs in GitHub Actions and is independent of the Codespace runtime.

An owner-authored issue with the exact title below triggers a wake request:

```text
[DPSR-WAKE] start Codespace
```

The workflow selects the most recently used Codespace associated with this repository and starts it through the GitHub Codespaces lifecycle API. The workflow requires the repository Actions secret `DPSR_CODESPACES_TOKEN`.

The Codespace `postStartCommand` runs `bin/wake-bootstrap`, which attempts to populate that encrypted Actions secret from an existing GitHub CLI login that already has Codespaces access. It then starts the remote agent, MCP sidecar, and operations console.

The GitHub issue bridge remains the recovery/control path after the Codespace is online. The wake controller exists specifically for the state where no process inside the Codespace can respond.
