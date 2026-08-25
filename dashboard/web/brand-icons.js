(() => {
  const profileRules = [
    [/native android|\bandroid\b/, "android"],
    [/flutter/, "flutter"],
    [/react native|\breact\b/, "react"],
    [/next\.?js|full-stack web/, "nextjs"],
    [/fastapi/, "fastapi"],
    [/native ios|swiftui|\bios\b|\bswift\b/, "apple"],
    [/security research|kali/, "kali"]
  ];

  const serviceRules = [
    [/kali/, "kali"],
    [/juice shop|webgoat/, "owasp"],
    [/dvwa/, "vulnweb"]
  ];

  const infrastructureRules = [
    [/^bridge$/, "bridge"],
    [/^mcp$/, "mcp"],
    [/^dashboard$/, "dashboard"]
  ];

  const toolIcons = new Map([
    ["nmap", "nmap"],
    ["nuclei", "target"],
    ["httpx", "network"],
    ["subfinder", "search"],
    ["naabu", "network"],
    ["semgrep", "code"],
    ["bandit", "shield"],
    ["pip-audit", "code"],
    ["trivy", "shield"],
    ["gitleaks", "key"],
    ["ffuf", "fuzz"],
    ["yara", "pattern"],
    ["radare2", "binary"],
    ["shellcheck", "terminal"]
  ]);

  function normalize(value) {
    return String(value || "").toLowerCase().replace(/\s+/g, " ").trim();
  }

  function matchRule(text, rules) {
    const match = rules.find(([pattern]) => pattern.test(text));
    return match ? match[1] : "";
  }

  function resourceIcon(card) {
    const kind = card.dataset.kind || "";
    const title = normalize(card.querySelector(".resource-title")?.textContent);
    const meta = normalize(card.querySelector(".resource-meta")?.textContent);
    const text = `${title} ${meta}`.trim();

    if (kind === "profiles" || kind === "projects") return matchRule(text, profileRules);
    if (kind === "services") return matchRule(text, serviceRules);
    if (kind === "infrastructure") return matchRule(title, infrastructureRules);
    return "";
  }

  function decorateResources() {
    document.querySelectorAll(".resource-card").forEach((card) => {
      const icon = resourceIcon(card);
      if (icon) card.dataset.brandIcon = icon;
      else card.removeAttribute("data-brand-icon");
    });
  }

  function decorateTools() {
    document.querySelectorAll("#tool-list .chip").forEach((chip) => {
      const key = normalize(chip.textContent);
      const icon = toolIcons.get(key) || "";
      if (icon) chip.dataset.toolIcon = icon;
      else chip.removeAttribute("data-tool-icon");
    });
  }

  let scheduled = false;
  function applyIcons() {
    scheduled = false;
    decorateResources();
    decorateTools();
  }

  function scheduleApply() {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(applyIcons);
  }

  const observer = new MutationObserver(scheduleApply);
  observer.observe(document.body, { childList: true, subtree: true });
  applyIcons();
})();
