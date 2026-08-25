(() => {
  const homeTitle = document.querySelector("#page-home .brand-title");
  if (homeTitle) homeTitle.textContent = "Unified. Elevated.";
  document.title = "APOTHEON ONE · Unified. Elevated.";

  const brandStyles = document.createElement("link");
  brandStyles.rel = "stylesheet";
  brandStyles.href = "/brand-icons.css";
  document.head.appendChild(brandStyles);

  const core = document.createElement("script");
  core.src = "/app-base.js";
  core.async = false;
  core.addEventListener("load", () => {
    const brandIcons = document.createElement("script");
    brandIcons.src = "/brand-icons.js";
    brandIcons.async = false;
    document.head.appendChild(brandIcons);
  });
  document.head.appendChild(core);
})();
