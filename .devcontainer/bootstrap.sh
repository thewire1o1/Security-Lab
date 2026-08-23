#!/usr/bin/env bash
set -Eeuo pipefail

WORKSPACE="${PWD}"
TOOLS_HOME="$HOME/tools"
GO_BIN="$HOME/go/bin"
mkdir -p "$TOOLS_HOME" "$GO_BIN" "$WORKSPACE/reports" "$WORKSPACE/notes" "$WORKSPACE/targets" "$WORKSPACE/loot" "$WORKSPACE/engagements" "$WORKSPACE/artifacts" "$WORKSPACE/cases" "$WORKSPACE/fuzz/harnesses"

printf '\n[+] Bootstrapping Security Lab...\n'
sudo apt-get update -y

packages=(
  curl wget jq git gh ca-certificates gnupg lsb-release unzip zip
  nmap masscan netcat-openbsd dnsutils whois traceroute iputils-ping
  tcpdump openssl socat proxychains4 tor
  tmux screen vim nano ripgrep fzf tree
  python3 python3-pip python3-venv pipx
  build-essential libpcap-dev libssl-dev pkg-config
  sqlmap hydra john shellcheck file binutils yara libimage-exiftool-perl
)

printf '[+] Installing host packages...\n'
if ! sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${packages[@]}"; then
  for pkg in "${packages[@]}"; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
      sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$pkg" || printf '[!] Optional package failed: %s\n' "$pkg"
    fi
  done
fi

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

pipx ensurepath >/dev/null 2>&1 || true
pipx install semgrep >/dev/null 2>&1 || pipx upgrade semgrep >/dev/null 2>&1 || true
pipx install pip-audit >/dev/null 2>&1 || pipx upgrade pip-audit >/dev/null 2>&1 || true
pipx install bandit >/dev/null 2>&1 || pipx upgrade bandit >/dev/null 2>&1 || true

rm -rf "$TOOLS_HOME/SecLists" 2>/dev/null || true

if command -v docker >/dev/null 2>&1 && [ -n "${GITHUB_TOKEN:-}" ] && [ -n "${GITHUB_USER:-}" ]; then
  printf '%s' "$GITHUB_TOKEN" | docker login ghcr.io -u "$GITHUB_USER" --password-stdin >/dev/null 2>&1 || true
fi

sed -i '/SECURITY-LAB/,/SECURITY-LAB.*END/d' "$HOME/.bashrc" 2>/dev/null || true
cat >> "$HOME/.bashrc" <<EOF

# >>> SECURITY-LAB >>>
export PATH="/usr/local/go/bin:$GO_BIN:$HOME/.local/bin:$WORKSPACE/bin:\$PATH"
alias labup='sec up'
alias labdown='sec down'
alias labps='sec ps'
alias labscan='sec scan'
alias labgui='sec gui'
alias labreport='sec report'
alias recon='bash $WORKSPACE/bin/recon'
alias headers='bash $WORKSPACE/bin/headers'
# >>> SECURITY-LAB >>> END
EOF

chmod +x "$WORKSPACE"/bin/* 2>/dev/null || true

sudo apt-get clean >/dev/null 2>&1 || true
npm cache clean --force >/dev/null 2>&1 || true
rm -rf "$HOME/.cache/pip"/* "$HOME/.cache/go-build"/* 2>/dev/null || true
bash "$WORKSPACE/bin/disk-guard" --auto || true

cat <<'BANNER'

============================================================
 Security Lab ready
------------------------------------------------------------
 sec help       control surface
 sec up         start vulnerable training targets
 sec gui        launch Mission Control
 sec defend     run the defensive pipeline
 sec review     run repository security review
 sec validate   compare and validate findings
 sec fuzz       fuzz local training targets and harnesses
 sec triage     statically triage a file
 sec research   manage persistent research cases
 sec kali       open dedicated Kali operator shell
============================================================

Run: source ~/.bashrc && sec doctor
BANNER
