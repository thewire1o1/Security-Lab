#!/usr/bin/env bash
set -Eeuo pipefail

WORKSPACE="${PWD}"
TOOLS_HOME="$HOME/tools"
GO_BIN="$HOME/go/bin"
mkdir -p "$TOOLS_HOME" "$GO_BIN" "$WORKSPACE/reports" "$WORKSPACE/notes" "$WORKSPACE/targets" "$WORKSPACE/loot"

printf '\n[+] Bootstrapping AI Security Lab...\n'

sudo apt-get update -y

packages=(
  curl wget jq git ca-certificates gnupg lsb-release
  nmap masscan netcat-openbsd dnsutils whois traceroute iputils-ping
  tcpdump openssl socat proxychains4 tor
  tmux screen vim nano ripgrep fzf tree unzip zip
  python3 python3-pip python3-venv pipx
  golang-go build-essential libpcap-dev libssl-dev pkg-config
  sqlmap nikto hydra john
)

for pkg in "${packages[@]}"; do
  if ! dpkg -s "$pkg" >/dev/null 2>&1; then
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "$pkg" || printf '[!] Optional package failed: %s\n' "$pkg"
  fi
done

printf '\n[+] Installing Codex CLI...\n'
npm install -g @openai/codex

export PATH="$GO_BIN:$HOME/.local/bin:$PATH"

install_go() {
  local pkg="$1"
  printf '[+] Go tool: %s\n' "$pkg"
  GOBIN="$GO_BIN" go install "$pkg" || printf '[!] Go install failed: %s\n' "$pkg"
}

printf '\n[+] Installing recon and web tooling...\n'
install_go github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
install_go github.com/projectdiscovery/httpx/cmd/httpx@latest
install_go github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
install_go github.com/projectdiscovery/naabu/v2/cmd/naabu@latest
install_go github.com/projectdiscovery/dnsx/cmd/dnsx@latest
install_go github.com/projectdiscovery/katana/cmd/katana@latest
install_go github.com/ffuf/ffuf/v2@latest
install_go github.com/tomnomnom/waybackurls@latest
install_go github.com/tomnomnom/assetfinder@latest
install_go github.com/lc/gau/v2/cmd/gau@latest

printf '\n[+] Installing Python security tooling...\n'
pipx ensurepath >/dev/null 2>&1 || true
pipx install semgrep >/dev/null 2>&1 || pipx upgrade semgrep >/dev/null 2>&1 || true
pipx install impacket >/dev/null 2>&1 || pipx upgrade impacket >/dev/null 2>&1 || true

if [ ! -d "$TOOLS_HOME/SecLists/.git" ]; then
  printf '\n[+] Cloning SecLists...\n'
  git clone --depth 1 https://github.com/danielmiessler/SecLists.git "$TOOLS_HOME/SecLists" || true
fi

if command -v nuclei >/dev/null 2>&1; then
  nuclei -update-templates >/dev/null 2>&1 || true
fi

# Persistent shell conveniences.
BASH_MARKER='# >>> AI-SECURITY-LAB >>>'
if ! grep -qF "$BASH_MARKER" "$HOME/.bashrc" 2>/dev/null; then
  cat >> "$HOME/.bashrc" <<EOF

$BASH_MARKER
export PATH="$GO_BIN:$HOME/.local/bin:$WORKSPACE/bin:\$PATH"
export SECLISTS="$TOOLS_HOME/SecLists"
alias sol='codex --model gpt-daybreak-blue'
alias labup='docker compose -f $WORKSPACE/lab/docker-compose.yml up -d'
alias labdown='docker compose -f $WORKSPACE/lab/docker-compose.yml down'
alias labps='docker compose -f $WORKSPACE/lab/docker-compose.yml ps'
alias labscan='bash $WORKSPACE/bin/labscan'
alias recon='bash $WORKSPACE/bin/recon'
alias headers='bash $WORKSPACE/bin/headers'
$BASH_MARKER END
EOF
fi

chmod +x "$WORKSPACE"/bin/* 2>/dev/null || true

printf '\n[+] Installed tool summary\n'
for cmd in codex nmap masscan sqlmap nikto hydra john nuclei httpx subfinder naabu dnsx katana ffuf waybackurls assetfinder gau semgrep; do
  if command -v "$cmd" >/dev/null 2>&1; then
    printf '  [OK] %s\n' "$cmd"
  else
    printf '  [--] %s\n' "$cmd"
  fi
done

cat <<'BANNER'

============================================================
 AI Security Lab ready
------------------------------------------------------------
 sol       -> Codex with Daybreak Blue / GPT-5.6 Sol
 labup     -> start local vulnerable targets
 labps     -> show local lab targets
 labscan   -> scan the local training lab
 recon     -> authorized-target recon helper
 headers   -> HTTP/TLS quick check
============================================================

Reopen the terminal (or run: source ~/.bashrc) to load aliases.
BANNER
