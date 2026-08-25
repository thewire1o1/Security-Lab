(() => {
  const homeTitle = document.querySelector("#page-home .brand-title");
  if (homeTitle) homeTitle.textContent = "Unified. Elevated.";
  document.title = "APOTHEON ONE · Unified. Elevated.";

  const core = document.createElement("script");
  core.src = "/app-base.js";
  core.async = false;
  document.head.appendChild(core);
})();
