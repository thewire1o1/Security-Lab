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
sec sol         launch Codex with GPT-5.6 Sol
sec new NAME    create an engagement workspace
sec update      update tools/templates
sec update --full  update everything and rebuild Kali
```

The host Codespace stays relatively clean and fast. Heavy offensive tooling lives in a disposable Kali Rolling container attached to the same isolated Docker network as Juice Shop, DVWA, and WebGoat.

See `SECURITY-LAB.md` for the full layout.
