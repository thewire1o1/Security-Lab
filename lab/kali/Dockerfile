FROM kalilinux/kali-rolling@sha256:1a2eb0501a2dbe8aa8f513b0791699dbd9b539696768f40b2cbe1dead2fb0d67

LABEL org.opencontainers.image.source="https://github.com/thewire1o1/Security-Lab"
LABEL org.opencontainers.image.description="APOTHEON ONE security research Kali operator image by Digital Paragon"

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm-256color
ENV PIP_NO_CACHE_DIR=1

RUN apt-get update \
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
    trivy \
    gitleaks \
    smbclient \
    ldap-utils \
    snmp \
    nbtscan \
    onesixtyone \
    sshuttle \
    socat \
    netcat-openbsd \
    yara \
    radare2 \
    binwalk \
    clamav \
    strace \
    ltrace \
    gdb \
    patchelf \
    afl++ \
    clang \
    llvm \
    file \
    binutils \
    tmux zsh vim nano less man-db \
    git curl wget jq ripgrep fzf tree unzip zip \
    python3 python3-pip pipx python3-pytest \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /workspace
# Root is intentional in the disposable operator container; target services do not inherit this privilege.
# nosemgrep: dockerfile.security.missing-user.missing-user
CMD ["sleep", "infinity"]
