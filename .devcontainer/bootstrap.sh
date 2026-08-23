#!/usr/bin/env bash
set -Eeuo pipefail

WORKSPACE="${PWD}"
TOOLS_HOME="$HOME/tools"
GO_BIN="$HOME/go/bin"
mkdir -p "$TOOLS_HOME" "$GO_BIN" "$WORKSPACE/reports" "$WORKSPACE/notes" "$WORKSPACE/targets" "$WORKSPACE/loot" "$WORKSPACE/engagements"

printf '\n[+] Bootstrapping AI Security Lab...\n'
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

for pkg in "${packages[@]}"; do
  if ! dpkg -s "$pkg" >/dev/null 2>&1; then
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "$pkg" || printf '[!] Optional package failed: %s\n' "$pkg"
  fi
done

printf '\n[+] Installing Codex CLI...\n'
npm install -g @openai/codex

# Installs current Go, ProjectDiscovery/PDTM, Nikto, and Impacket.
printf '\n[+] Installing core security tooling...\n'
bash "$WORKSPACE/bin/repair-tools" || true
export PATH="/usr/local/go/bin:$GO_BIN:$HOME/.local/bin:$PATH"

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

if [ ! -d "$TOOLS_HOME/SecLists/.git" ]; then
  printf '\n[+] Cloning SecLists...\n'
  git clone --depth 1 https://github.com/danielmiessler/SecLists.git "$TOOLS_HOME/SecLists" || true
fi

# Ignore executable-bit changes in this Codespace. GitHub's Contents API stores
# these helper scripts as ordinary text files, and every helper is invoked via bash.
git config core.fileMode false || true

BASH_MARKER='# >>> AI-SECURITY-LAB >>>'
if grep -qF "$BASH_MARKER" "$HOME/.bashrc" 2>/dev/null; then
  # Replace the managed block so existing Codespaces get updated behavior.
  python3 - "$HOME/.bashrc" <<'PY'
from pathlib import Path
import re, sys
p = Path(sys.argv[1])
s = p.read_text()
s = re.sub(r'\n# >>> AI-SECURITY-LAB >>>.*?# <<< AI-SECURITY-LAB <<<\n?', '\n', s, flags=re.S)
p.write_text(s)
PY
fi

cat >> "$HOME/.bashrc" <<EOF

# >>> AI-SECURITY-LAB >>>
export PATH="/usr/local/go/bin:$GO_BIN:$HOME/.local/bin:\$PATH"
export SECLISTS="$TOOLS_HOME/SecLists"
sec() { bash "$WORKSPACE/bin/sec" "\$@"; }
alias sol='codex --model gpt-daybreak-blue'
alias labup='bash $WORKSPACE/bin/sec up'
alias labdown='bash $WORKSPACE/bin/sec down'
alias labps='bash $WORKSPACE/bin/sec ps'
alias labscan='bash $WORKSPACE/bin/sec scan'
alias recon='bash $WORKSPACE/bin/recon'
alias headers='bash $WORKSPACE/bin/headers'
# <<< AI-SECURITY-LAB <<<
EOF

cat <<'BANNER'

============================================================
 AI Security Lab ready
------------------------------------------------------------
 sec help   -> control surface
 sec sol    -> Codex with GPT-5.6 Sol
 sec up     -> start vulnerable training targets
 sec kali   -> open dedicated Kali operator shell
 sec new X  -> create engagement workspace
============================================================

Run: source ~/.bashrc && sec doctor
BANNER
