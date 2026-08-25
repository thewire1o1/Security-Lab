(() => {
  const applyDevelopmentEntry = () => {
    const devCard = document.querySelector('#home-grid .hero-card[data-home-filter="projects"]');
    if (!devCard) return;

    const metric = devCard.querySelector('.hero-metric');
    const label = devCard.querySelector('.hero-label');
    const foot = devCard.querySelector('.hero-foot span:first-child');
    if (!metric || metric.textContent.trim() !== '0' || !foot) return;

    const profileMatch = foot.textContent.match(/(?:·|\b)(\d+)\s+profiles?\b/i);
    if (!profileMatch) return;

    devCard.dataset.homeFilter = 'profiles';
    metric.textContent = profileMatch[1];
    if (label) label.textContent = 'starter profiles';
    foot.textContent = 'Choose a profile to create your first project';

    devCard.onclick = () => {
      if (typeof setPage === 'function') setPage('systems');
      document.querySelector('.segment[data-filter="profiles"]')?.click();
    };
  };

  const improveProjectEmptyState = () => {
    const list = document.getElementById('resource-list');
    const projectsActive = document.querySelector('.segment[data-filter="projects"].active');
    if (!list || !projectsActive) return;

    const empty = list.querySelector('.empty');
    if (!empty || !/No resources in this view/i.test(empty.textContent)) return;

    empty.classList.add('empty-projects');
    empty.innerHTML = '<strong>No projects yet</strong><span>Start from a development profile. APOTHEON will create the project here with its stack and commands ready to use.</span><button type="button" class="secondary" data-browse-profiles>Browse profiles</button>';
    empty.querySelector('[data-browse-profiles]')?.addEventListener('click', () => {
      document.querySelector('.segment[data-filter="profiles"]')?.click();
    });
  };

  const apply = () => {
    applyDevelopmentEntry();
    improveProjectEmptyState();
  };

  const observer = new MutationObserver(apply);
  observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  window.addEventListener('load', apply, { once: true });
  apply();
})();
