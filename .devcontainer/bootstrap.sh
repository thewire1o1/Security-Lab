#!/usr/bin/env bash
set -Eeuo pipefail

WORKSPACE="${PWD}"
TOOLS_HOME="$HOME/tools"
GO_BIN="$HOME/go/bin"
mkdir -p "$TOOLS_HOME" "$GO_BIN" "$WORKSPACE/reports" "$WORKSPACE/notes" "$WORKSPACE/targets" "$WORKSPACE/loot" "$WORKSPACE/engagements"

printf '\n[+] Bootstrapping Security Lab...\n'
sudo apt-get update -y

packages=(
  curl wget jq git ca-certificates gnupg lsb-release unzip zip
  nmap masscan netcat-openbsd dnsutils whois traceroute iputils-ping
  tcpdump openssl socat proxychains4 tor
  tmux screen vim nano ripgrep fzf tree
  python3 python3-pip python3-venv pipx
  build-essential libpcap-dev libssl-dev pkg-config
  sqlmap hydra john
)

printf '[+] Installing host packages in one transaction...\n'
if ! sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${packages[@]}"; then
  printf '[!] Bulk package install had an error; retrying missing packages individually.\n'
  for pkg in "${packages[@]}"; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
      sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$pkg" || printf '[!] Optional package failed: %s\n' "$pkg"
    fi
  done
fi

printf '\n[+] Installing Codex CLI...\n'
npm install -g @openai/codex

# Installs current Go, ProjectDiscovery/PDTM, Nikto, and Impacket.
printf '\n[+] Installing core security tooling...\n'
bash "$WORKSPACE/bin/repair-tools" || true
export PATH="/usr/local/go/bin:$GO_BIN:$HOME/.local/bin:$WORKSPACE/bin:$PATH"

install_go() {
  local name="$1" pkg="$2"
  if ! command -v "$name" >/dev/null 2>&1; then
    printf '[+] Go tool: %s\n' "$name"
    GOBIN="$GO_BIN" /usr/local/go/bin/go install "$pkg" || printf '[!] Go install failed: %s\n' "$name"
  fi
}

install_go ffuf github.com/ffuf/ffuf/v2@latest
install_go waybackurls github.com/tomnomnom/waybackurls@latest
install_go assetfinder github.com/tomnomnom/assetfinder@latest
install_go gau github.com/lc/gau/v2/cmd/gau@latest

printf '\n[+] Installing Python security tooling...\n'
pipx ensurepath >/dev/null 2>&1 || true
pipx install semgrep >/dev/null 2>&1 || pipx upgrade semgrep >/dev/null 2>&1 || true

# SecLists is already installed inside the Kali operator image. Keeping a second
# multi-gigabyte checkout on the Codespace host wastes storage and rebuild time.
rm -rf "$TOOLS_HOME/SecLists" 2>/dev/null || true

# Let Docker pull the repository-linked GHCR image without an interactive login.
if command -v docker >/dev/null 2>&1 && [ -n "${GITHUB_TOKEN:-}" ] && [ -n "${GITHUB_USER:-}" ]; then
  printf '%s' "$GITHUB_TOKEN" | docker login ghcr.io -u "$GITHUB_USER" --password-stdin >/dev/null 2>&1 || true
fi

# Rename the old shell marker if this Codespace predates the cleanup.
sed -i 's/# >>> AI-SECURITY-LAB >>>/# >>> SECURITY-LAB >>>/g; s/# >>> AI-SECURITY-LAB >>> END/# >>> SECURITY-LAB >>> END/g' "$HOME/.bashrc" 2>/dev/null || true
BASH_MARKER='# >>> SECURITY-LAB >>>'
if ! grep -qF "$BASH_MARKER" "$HOME/.bashrc" 2>/dev/null; then
  cat >> "$HOME/.bashrc" <<EOF

$BASH_MARKER
export PATH="/usr/local/go/bin:$GO_BIN:$HOME/.local/bin:$WORKSPACE/bin:\$PATH"
alias sol='codex --model gpt-daybreak-blue'
alias labup='sec up'
alias labdown='sec down'
alias labps='sec ps'
alias labscan='sec scan'
alias labgui='sec gui'
alias labreport='sec report'
alias recon='bash $WORKSPACE/bin/recon'
alias headers='bash $WORKSPACE/bin/headers'
$BASH_MARKER END
EOF
fi

chmod +x "$WORKSPACE"/bin/* 2>/dev/null || true

# Package-manager caches have no value in a persistent Codespace.
sudo apt-get clean >/dev/null 2>&1 || true
npm cache clean --force >/dev/null 2>&1 || true
rm -rf "$HOME/.cache/pip"/* "$HOME/.cache/go-build"/* 2>/dev/null || true
bash "$WORKSPACE/bin/disk-guard" --auto || true

cat <<'BANNER'

============================================================
 Security Lab ready
------------------------------------------------------------
 sec help   -> control surface
 sec sol    -> Codex with GPT-5.6 Sol
 sec up     -> start vulnerable training targets
 sec gui    -> launch Mission Control web GUI
 sec report -> build latest HTML/JSON evidence report
 sec kali   -> open dedicated Kali operator shell
 sec new X  -> create engagement workspace
============================================================

Run: source ~/.bashrc && sec doctor
BANNER
