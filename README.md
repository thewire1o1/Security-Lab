# AI Security Lab

Cloud-native pentest and security research workstation for GitHub Codespaces.

## Start here

```bash
source ~/.bashrc
sec doctor
```

Core control command:

```text
sec up          start the local vulnerable lab
sec scan        scan the local lab
sec kali-build  build the dedicated Kali operator image
sec kali        enter the Kali operator shell
sec mcp-setup   connect Codex to Kali through MCP
sec ai-kali     launch GPT-5.6 Sol with Kali MCP ready
sec sol         launch plain Codex with GPT-5.6 Sol
sec new NAME    create an engagement workspace
sec update      update tools/templates
sec update --full  update everything and rebuild Kali
```

The host Codespace stays relatively clean and fast. Heavy offensive tooling lives in a disposable Kali Rolling container attached to the same isolated Docker network as Juice Shop, DVWA, and WebGoat.

The Kali layer also includes Kali's packaged MCP bridge, Metasploit MCP, HexStrike AI, Trivy, and Gitleaks. `sec ai-kali` starts the Kali operator container and gives Codex access to the Kali MCP bridge without exposing the Kali API port publicly.

See `SECURITY-LAB.md` for the full layout.
