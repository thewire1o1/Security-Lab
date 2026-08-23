FROM kalilinux/kali-rolling:latest

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm-256color

RUN apt-get update \
 && apt-get -y full-upgrade \
 && apt-get install -y --no-install-recommends \
    kali-tools-top10 \
    bloodhound \
    enum4linux-ng \
    evil-winrm \
    exploitdb \
    feroxbuster \
    gobuster \
    hashcat \
    impacket-scripts \
    kerberoast \
    krbrelayx \
    ligolo-ng \
    mitm6 \
    peass \
    proxychains4 \
    recon-ng \
    seclists \
    testssl.sh \
    theharvester \
    whatweb \
    wafw00f \
    wpscan \
    tshark \
    smbclient \
    ldap-utils \
    snmp \
    nbtscan \
    onesixtyone \
    sshuttle \
    socat \
    netcat-openbsd \
    tmux zsh vim nano less man-db \
    git curl wget jq ripgrep fzf tree unzip zip \
    python3 python3-pip pipx \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
CMD ["sleep", "infinity"]
