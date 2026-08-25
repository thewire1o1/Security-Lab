(() => {
  const homeTitle = document.querySelector("#page-home .brand-title");
  if (homeTitle) homeTitle.textContent = "Unified. Elevated.";
  document.title = "APOTHEON ONE · Unified. Elevated.";

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
      document.head.appendChild(insights);
    });
    document.head.appendChild(orchestrator);
  });
  document.head.appendChild(core);
})();
