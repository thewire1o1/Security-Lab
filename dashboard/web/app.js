(() => {
  const THEME_KEY = "apotheon-theme";
  const storedTheme = localStorage.getItem(THEME_KEY);
  let activeTheme = storedTheme === "light" ? "light" : "dark";

  const applyTheme = (theme) => {
    activeTheme = theme === "light" ? "light" : "dark";
    document.documentElement.dataset.theme = activeTheme;
    document.documentElement.style.colorScheme = activeTheme;
    localStorage.setItem(THEME_KEY, activeTheme);

    const themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) themeColor.content = activeTheme === "dark" ? "#05070a" : "#e7ebef";

    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      const dark = activeTheme === "dark";
      button.classList.toggle("on", dark);
      button.setAttribute("aria-pressed", String(dark));
      button.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
      const icon = button.querySelector("[data-theme-icon]");
      const label = button.querySelector("[data-theme-label]");
      if (icon) icon.textContent = dark ? "☾" : "☀";
      if (label) label.textContent = dark ? "Dark" : "Light";
    });
  };

  document.documentElement.dataset.theme = activeTheme;

  const homeTitle = document.querySelector("#page-home .brand-title");
  if (homeTitle) homeTitle.textContent = "APOTHEON ONE";
  const homeKicker = document.querySelector("#page-home .brand-kicker");
  if (homeKicker) homeKicker.innerHTML = '<span class="brand-dot"></span>Unified. Elevated.';
  document.title = "APOTHEON ONE · Unified. Elevated.";

  const homeGrid = document.getElementById("home-grid");
  const quickStrip = document.querySelector("#page-home .quick-strip");
  const quickHead = quickStrip?.previousElementSibling;
  if (homeGrid && quickStrip && quickHead?.classList.contains("section-head")) {
    quickHead.style.marginTop = "12px";
    homeGrid.parentNode.insertBefore(quickHead, homeGrid);
    homeGrid.parentNode.insertBefore(quickStrip, homeGrid);
  }

  const scanLabel = document.querySelector("#scan-home span");
  if (scanLabel) scanLabel.textContent = "Security check";

  const platformStatus = document.getElementById("platform-status");
  if (platformStatus && !document.querySelector("#page-home .topbar-actions")) {
    const actions = document.createElement("div");
    actions.className = "topbar-actions";
    platformStatus.parentNode.insertBefore(actions, platformStatus);

    const themeButton = document.createElement("button");
    themeButton.type = "button";
    themeButton.className = "theme-switch";
    themeButton.dataset.themeToggle = "true";
    themeButton.innerHTML = '<span data-theme-icon aria-hidden="true">☾</span><span data-theme-label>Dark</span>';
    actions.appendChild(themeButton);
    actions.appendChild(platformStatus);
  }

  const appearanceLabel = Array.from(document.querySelectorAll("#page-settings .setting b"))
    .find((node) => node.textContent.trim() === "Appearance");
  const appearanceSetting = appearanceLabel?.closest(".setting");
  if (appearanceSetting) {
    appearanceLabel.textContent = "Dark mode";
    const description = appearanceSetting.querySelector("small");
    if (description) description.textContent = "Switch between dark and light interface themes.";
    const oldValue = appearanceSetting.querySelector(".setting-value");
    const themeToggle = document.createElement("button");
    themeToggle.type = "button";
    themeToggle.className = "toggle theme-setting-toggle";
    themeToggle.dataset.themeToggle = "true";
    themeToggle.setAttribute("aria-label", "Toggle dark mode");
    if (oldValue) oldValue.replaceWith(themeToggle);
    else appearanceSetting.appendChild(themeToggle);
  }

  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    button.addEventListener("click", () => applyTheme(activeTheme === "dark" ? "light" : "dark"));
  });
  applyTheme(activeTheme);

  const brandStyles = document.createElement("link");
  brandStyles.rel = "stylesheet";
  brandStyles.href = "/brand-icons.css";
  document.head.appendChild(brandStyles);

  const uxStyles = document.createElement("link");
  uxStyles.rel = "stylesheet";
  uxStyles.href = "/ux-polish.css";
  document.head.appendChild(uxStyles);

  const orchestratorStyles = document.createElement("link");
  orchestratorStyles.rel = "stylesheet";
  orchestratorStyles.href = "/orchestrator.css";
  document.head.appendChild(orchestratorStyles);

  const insightStyles = document.createElement("link");
  insightStyles.rel = "stylesheet";
  insightStyles.href = "/insights.css";
  document.head.appendChild(insightStyles);

  const guidedStyles = document.createElement("link");
  guidedStyles.rel = "stylesheet";
  guidedStyles.href = "/guided-ui.css";
  document.head.appendChild(guidedStyles);

  const projectOutputStyles = document.createElement("link");
  projectOutputStyles.rel = "stylesheet";
  projectOutputStyles.href = "/project-output.css";
  document.head.appendChild(projectOutputStyles);

  const finalPolishStyles = document.createElement("link");
  finalPolishStyles.rel = "stylesheet";
  finalPolishStyles.href = "/final-polish.css";
  document.head.appendChild(finalPolishStyles);

  const core = document.createElement("script");
  core.src = "/app-base.js";
  core.async = false;
  core.addEventListener("load", () => {
    const brandIcons = document.createElement("script");
    brandIcons.src = "/brand-icons.js";
    brandIcons.async = false;
    document.head.appendChild(brandIcons);

    const uxBehavior = document.createElement("script");
    uxBehavior.src = "/ux-behavior.js";
    uxBehavior.async = false;
    document.head.appendChild(uxBehavior);

    const orchestrator = document.createElement("script");
    orchestrator.src = "/orchestrator.js";
    orchestrator.async = false;
    orchestrator.addEventListener("load", () => {
      const runPeekBehavior = document.createElement("script");
      runPeekBehavior.src = "/run-peek-behavior.js";
      runPeekBehavior.async = false;
      document.head.appendChild(runPeekBehavior);

      const insights = document.createElement("script");
      insights.src = "/insights.js";
      insights.async = false;
      insights.addEventListener("load", () => {
        const guided = document.createElement("script");
        guided.src = "/guided-ui.js";
        guided.async = false;
        guided.addEventListener("load", () => {
          const runFlow = document.createElement("script");
          runFlow.src = "/run-flow.js";
          runFlow.async = false;
          document.head.appendChild(runFlow);

          const projectOutput = document.createElement("script");
          projectOutput.src = "/project-output.js";
          projectOutput.async = false;
          document.head.appendChild(projectOutput);
        });
        document.head.appendChild(guided);
      });
      document.head.appendChild(insights);
    });
    document.head.appendChild(orchestrator);
  });
  document.head.appendChild(core);
})();
