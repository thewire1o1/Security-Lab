# APOTHEON ONE Wake Controller

> **Unified. Elevated.**  
> Development & Security Platform by Digital Paragon

The wake controller runs in GitHub Actions and is independent of the Codespace runtime.

An owner-authored issue with the exact compatibility trigger below starts a wake request:

```text
[DPSR-WAKE] start Codespace
```

The trigger string is retained for compatibility with the existing external controller. The workflow selects the most recently used Codespace associated with this repository and starts it through the GitHub Codespaces lifecycle API. The workflow requires the repository Actions secret `DPSR_CODESPACES_TOKEN`.

The Codespace `postStartCommand` runs `bin/wake-bootstrap`, which attempts to populate that encrypted Actions secret from an existing GitHub CLI login that already has Codespaces access. It then starts the remote agent, MCP sidecar, and APOTHEON ONE console.

The GitHub issue bridge remains the recovery/control path after the Codespace is online. The wake controller exists specifically for the state where no process inside the Codespace can respond.
