(() => {
  const state = {
    catalog: null,
    run: null,
    selectedTarget: 'lab',
    selectedProfile: 'standard',
    pollTimer: null,
  };

  const targetAliases = {
    'Main Lab': 'lab',
    'DVWA': 'dvwa',
    'Vulnerable Web App': 'dvwa',
    'Juice Shop': 'juice-shop',
    'OWASP Juice Shop': 'juice-shop',
    'WebGoat': 'webgoat',
    'OWASP WebGoat': 'webgoat',
  };

  const fallbackCatalog = {
    targets: {
      lab: { label: 'Entire Training Lab', short: 'Local Lab', description: 'All intentionally vulnerable web applications in the isolated training lab.', technical: 'Juice Shop, DVWA, and WebGoat' },
      'juice-shop': { label: 'OWASP Juice Shop', short: 'Juice Shop', description: 'An intentionally vulnerable online store used for safe web security practice.', technical: 'OWASP Juice Shop' },
      dvwa: { label: 'Vulnerable Web App', short: 'DVWA', description: 'An intentionally vulnerable web application designed for safe security testing.', technical: 'DVWA' },
      webgoat: { label: 'OWASP WebGoat', short: 'WebGoat', description: 'An intentionally insecure application that teaches common web vulnerabilities.', technical: 'OWASP WebGoat' },
    },
    profiles: {
      quick: { label: 'Quick Check', description: 'Confirm reachability, identify services, and inspect the web response.', technical: 'Nmap plus HTTP inspection' },
      standard: { label: 'Standard Security Check', description: 'Discover services, inspect the app, and check known vulnerability patterns.', technical: 'Nmap, HTTP inspection, and Nuclei' },
      deep: { label: 'Deep Security Check', description: 'Run broader service inspection and vulnerability checks.', technical: 'Nmap scripts, service detection, and Nuclei' },
    },
    tools: {},
  };

  function create(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function catalog() {
    return state.catalog || fallbackCatalog;
  }

  function ensureUI() {
    let overlay = document.getElementById('apo-run-overlay');
    if (!overlay) {
      overlay = create('div', 'apo-overlay');
      overlay.id = 'apo-run-overlay';
      overlay.setAttribute('aria-hidden', 'true');

      const panel = create('section', 'apo-run-panel');
      panel.id = 'apo-run-panel';
      panel.setAttribute('role', 'dialog');
      panel.setAttribute('aria-modal', 'true');
      panel.setAttribute('aria-label', 'APOTHEON automation');
      overlay.appendChild(panel);
      document.body.appendChild(overlay);

      overlay.addEventListener('click', (event) => {
        if (event.target === overlay) closePanel();
      });
    }

    let peek = document.getElementById('apo-run-peek');
    if (!peek) {
      peek = create('button', 'apo-run-peek');
      peek.id = 'apo-run-peek';
      peek.type = 'button';
      peek.addEventListener('click', () => {
        if (state.run) renderRun(state.run, true);
      });
      document.body.appendChild(peek);
    }
    return overlay;
  }

  function openPanel() {
    const overlay = ensureUI();
    overlay.classList.add('open');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }

  function closePanel() {
    const overlay = document.getElementById('apo-run-overlay');
    if (!overlay) return;
    overlay.classList.remove('open');
    overlay.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }

  function panelShell(eyebrow, title) {
    const panel = document.getElementById('apo-run-panel');
    panel.replaceChildren();

    const head = create('div', 'apo-panel-head');
    const heading = create('div');
    heading.appendChild(create('div', 'apo-eyebrow', eyebrow));
    heading.appendChild(create('h2', 'apo-panel-title', title));
    head.appendChild(heading);

    const close = create('button', 'apo-close', '×');
    close.type = 'button';
    close.setAttribute('aria-label', 'Close');
    close.addEventListener('click', closePanel);
    head.appendChild(close);
    panel.appendChild(head);

    const body = create('div', 'apo-panel-body');
    panel.appendChild(body);
    return body;
  }

  function section(title, copy) {
    const node = create('section', 'apo-section');
    node.appendChild(create('h3', '', title));
    if (copy) node.appendChild(create('p', 'apo-section-copy', copy));
    return node;
  }

  function renderScanBuilder(target) {
    const data = catalog();
    if (target && data.targets[target]) state.selectedTarget = target;
    if (!data.targets[state.selectedTarget]) state.selectedTarget = 'lab';
    if (!data.profiles[state.selectedProfile]) state.selectedProfile = 'standard';

    openPanel();
    const body = panelShell('Security automation', 'Run a security check');

    const targetSection = section('1. What do you want to check?', 'Choose the thing APOTHEON should work on. Nothing starts until the target and check are clear.');
    const targetGrid = create('div', 'apo-choice-grid');
    Object.entries(data.targets).forEach(([key, row]) => {
      const button = create('button', `apo-choice${state.selectedTarget === key ? ' selected' : ''}`);
      button.type = 'button';
      button.appendChild(create('strong', '', row.label));
      button.appendChild(create('span', '', row.description));
      button.appendChild(create('small', '', row.technical));
      button.addEventListener('click', () => {
        state.selectedTarget = key;
        renderScanBuilder();
      });
      targetGrid.appendChild(button);
    });
    targetSection.appendChild(targetGrid);
    body.appendChild(targetSection);

    const profileSection = section('2. How thorough should it be?', 'The simple names describe the outcome. Technical details stay available underneath.');
    const profileGrid = create('div', 'apo-choice-grid');
    Object.entries(data.profiles).forEach(([key, row]) => {
      const button = create('button', `apo-choice${state.selectedProfile === key ? ' selected' : ''}`);
      button.type = 'button';
      button.appendChild(create('strong', '', row.label));
      button.appendChild(create('span', '', row.description));
      button.appendChild(create('small', '', row.technical));
      button.addEventListener('click', () => {
        state.selectedProfile = key;
        renderScanBuilder();
      });
      profileGrid.appendChild(button);
    });
    profileSection.appendChild(profileGrid);
    body.appendChild(profileSection);

    const selectedTarget = data.targets[state.selectedTarget];
    const selectedProfile = data.profiles[state.selectedProfile];
    const summary = create('div', 'apo-run-summary');
    summary.appendChild(create('strong', '', `${selectedProfile.label} · ${selectedTarget.label}`));
    summary.appendChild(create('span', '', `${selectedProfile.description} APOTHEON will show each stage as it happens and keep the technical implementation available on demand.`));
    body.appendChild(summary);

    const run = create('button', 'apo-run-primary', `Run ${selectedProfile.label}`);
    run.type = 'button';
    run.addEventListener('click', () => startScan(run));
    body.appendChild(run);
  }

  async function startScan(button) {
    button.disabled = true;
    button.textContent = 'Starting…';
    try {
      const response = await fetch('/api/action', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ action: 'scan', target: state.selectedTarget, profile: state.selectedProfile }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to start security check');
      state.run = data.run || null;
      if (state.run) renderRun(state.run, true);
      startRunPolling();
    } catch (error) {
      button.disabled = false;
      button.textContent = `Run ${catalog().profiles[state.selectedProfile]?.label || 'check'}`;
      showInlineError(error instanceof Error ? error.message : 'Unable to start security check');
    }
  }

  function showInlineError(message) {
    const body = document.querySelector('#apo-run-panel .apo-panel-body');
    if (!body) return;
    const box = create('div', 'apo-run-summary');
    box.style.borderLeftColor = 'var(--red)';
    box.appendChild(create('strong', '', 'Could not start automation'));
    box.appendChild(create('span', '', message));
    body.appendChild(box);
  }

  function runStateLabel(value) {
    return ({ queued: 'Queued', running: 'Running', succeeded: 'Complete', failed: 'Failed' })[value] || value || 'Unknown';
  }

  function renderRun(run, open) {
    state.run = run;
    ensureUI();
    updatePeek(run);
    if (!open && !document.getElementById('apo-run-overlay')?.classList.contains('open')) return;

    openPanel();
    const body = panelShell(run.state === 'succeeded' ? 'Automation complete' : 'Active run', run.title || 'Running automation');

    const meta = create('div', 'apo-run-meta');
    const target = create('span');
    target.append('Target: ');
    target.appendChild(create('b', '', run.target_label || 'APOTHEON ONE'));
    meta.appendChild(target);
    if (run.profile_label) {
      const profile = create('span');
      profile.append('Check: ');
      profile.appendChild(create('b', '', run.profile_label));
      meta.appendChild(profile);
    }
    const status = create('span');
    status.append('Status: ');
    status.appendChild(create('b', '', runStateLabel(run.state)));
    meta.appendChild(status);
    body.appendChild(meta);

    const progress = create('div', 'apo-progress-line');
    const progressFill = create('span');
    progressFill.style.width = `${Number(run.progress || 0)}%`;
    progress.appendChild(progressFill);
    body.appendChild(progress);

    if (run.description) {
      const summary = create('div', 'apo-run-summary');
      summary.appendChild(create('strong', '', run.state === 'succeeded' ? (run.summary || 'Run complete') : run.description));
      summary.appendChild(create('span', '', run.technical || 'APOTHEON is tracking this automation as a structured run.'));
      body.appendChild(summary);
    }

    const stagesSection = section('What is happening?', 'Tap any stage for a plain explanation of what APOTHEON is doing.');
    const stages = create('div', 'apo-stage-list');
    (run.stages || []).forEach((row) => {
      const button = create('button', `apo-stage ${row.state || 'pending'}`);
      button.type = 'button';
      const top = create('div', 'apo-stage-top');
      top.appendChild(create('span', 'apo-stage-dot'));
      top.appendChild(create('span', 'apo-stage-title', row.title || row.id));
      top.appendChild(create('span', 'apo-stage-state', row.state || 'pending'));
      button.appendChild(top);
      button.appendChild(create('p', 'apo-stage-detail', row.detail || 'No additional detail available.'));
      button.addEventListener('click', () => button.classList.toggle('expanded'));
      stages.appendChild(button);
    });
    stagesSection.appendChild(stages);
    body.appendChild(stagesSection);

    if (Array.isArray(run.technical_tail) && run.technical_tail.length) {
      const technicalSection = section('Technical details', 'Optional implementation output for people who want to inspect what ran underneath.');
      technicalSection.appendChild(create('div', 'apo-technical', run.technical_tail.join('\n')));
      body.appendChild(technicalSection);
    }

    if (run.state === 'succeeded' || run.state === 'failed') {
      const next = create('div', 'apo-run-summary');
      next.appendChild(create('strong', '', run.state === 'succeeded' ? 'What next?' : 'Run needs attention'));
      next.appendChild(create('span', '', run.state === 'succeeded'
        ? 'The evidence is saved in run history. Open Activity for the timeline, or run a different check against the same target.'
        : 'Open Technical details above to see the last execution messages, then adjust the target or check and try again.'));
      body.appendChild(next);
    }
  }

  function updatePeek(run) {
    const peek = ensureUI().parentElement?.querySelector('#apo-run-peek') || document.getElementById('apo-run-peek');
    if (!peek || !run) return;
    peek.replaceChildren();
    const text = create('div');
    text.appendChild(create('strong', '', run.title || 'APOTHEON automation'));
    const current = (run.stages || []).find((stage) => stage.id === run.current_stage);
    text.appendChild(create('span', '', current?.title || (run.state === 'succeeded' ? 'Completed. Tap to review.' : runStateLabel(run.state))));
    peek.appendChild(text);
    peek.appendChild(create('b', '', `${Number(run.progress || 0)}%`));
    peek.classList.add('visible');
  }

  async function refreshRun(open) {
    try {
      const response = await fetch('/api/run', { cache: 'no-store' });
      if (!response.ok) return;
      const data = await response.json();
      if (!data.run) return;
      const changed = !state.run || JSON.stringify(state.run) !== JSON.stringify(data.run);
      state.run = data.run;
      updatePeek(data.run);
      if (changed && (open || document.getElementById('apo-run-overlay')?.classList.contains('open'))) renderRun(data.run, open);
      if (data.run.state === 'running' || data.run.state === 'queued') startRunPolling();
    } catch (_error) {
      // Runtime status is supplemental; the main dashboard remains usable if this poll fails.
    }
  }

  function startRunPolling() {
    if (state.pollTimer) return;
    state.pollTimer = window.setInterval(async () => {
      await refreshRun(false);
      if (state.run && !['running', 'queued'].includes(state.run.state)) {
        window.clearInterval(state.pollTimer);
        state.pollTimer = null;
      }
    }, 1200);
  }

  function contextTarget() {
    const title = document.getElementById('detail-title')?.textContent?.trim() || '';
    return targetAliases[title] || '';
  }

  function renderInfo(eyebrow, title, description, technical, action) {
    openPanel();
    const body = panelShell(eyebrow, title);
    const info = create('div', 'apo-run-summary');
    info.appendChild(create('strong', '', 'What is this?'));
    info.appendChild(create('span', '', description));
    body.appendChild(info);

    const detail = section('Technical name', 'This is the implementation underneath the plain-language capability.');
    detail.appendChild(create('div', 'apo-technical', technical));
    body.appendChild(detail);

    if (action) {
      const button = create('button', 'apo-run-primary', action.label);
      button.type = 'button';
      button.addEventListener('click', action.run);
      body.appendChild(button);
    }
  }

  function targetInfo(key) {
    const row = catalog().targets[key];
    if (!row) return;
    renderInfo('Training target', row.label, row.description, row.technical, {
      label: 'Run a security check',
      run: () => renderScanBuilder(key),
    });
  }

  function toolInfo(tool) {
    const row = catalog().tools?.[tool];
    if (!row) return;
    renderInfo('Security capability', row.label, row.description, row.technical);
  }

  function enhanceDetail() {
    const page = document.getElementById('page-detail');
    const stage = page?.querySelector('.device-stage');
    if (!page || !stage) return;
    const key = contextTarget();
    const old = page.querySelector('.apo-object-intro');
    if (!key) {
      if (old) old.remove();
      return;
    }
    if (old?.dataset.target === key) return;
    if (old) old.remove();

    const row = catalog().targets[key];
    if (!row) return;
    const title = document.getElementById('detail-title');
    if (title && key === 'dvwa') title.textContent = row.label;

    const box = create('div', 'apo-object-intro');
    box.dataset.target = key;
    box.appendChild(create('strong', '', row.label));
    box.appendChild(create('p', '', row.description));
    const actions = create('div', 'apo-object-actions');
    const scan = create('button', 'primary-action', 'Scan this target');
    scan.type = 'button';
    scan.addEventListener('click', () => renderScanBuilder(key));
    actions.appendChild(scan);
    const explain = create('button', '', 'What is this?');
    explain.type = 'button';
    explain.addEventListener('click', () => targetInfo(key));
    actions.appendChild(explain);
    box.appendChild(actions);
    stage.parentNode.insertBefore(box, stage);
  }

  function enhanceServiceCards() {
    document.querySelectorAll('.resource-card[data-kind="services"]').forEach((card) => {
      const key = card.dataset.detailName;
      const row = catalog().targets[key];
      if (!row || card.dataset.apotheonExplained === '1') return;
      card.dataset.apotheonExplained = '1';
      const title = card.querySelector('.resource-title');
      if (title && key === 'dvwa') title.textContent = row.label;
      const meta = card.querySelector('.resource-meta');
      if (meta) {
        const description = create('span', 'apo-service-description', row.short || row.technical);
        description.title = row.description;
        meta.prepend(description);
      }
    });
  }

  function enhanceTools() {
    document.querySelectorAll('#tool-list .chip').forEach((chip) => {
      if (chip.dataset.apotheonTool) return;
      const tool = chip.textContent.trim();
      const row = catalog().tools?.[tool];
      if (!row) return;
      chip.dataset.apotheonTool = tool;
      chip.replaceChildren();
      const friendly = create('span', 'apo-tool-friendly');
      friendly.appendChild(create('span', '', row.label));
      friendly.appendChild(create('small', '', row.technical));
      chip.appendChild(friendly);
      chip.title = row.description;
    });
  }

  function applyEnhancements() {
    enhanceDetail();
    enhanceServiceCards();
    enhanceTools();
  }

  document.addEventListener('click', (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;

    const scanHome = target.closest('#scan-home');
    if (scanHome) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      renderScanBuilder();
      return;
    }

    const control = target.closest('.control');
    if (control && /run scan/i.test(control.textContent || '')) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      renderScanBuilder(contextTarget());
      return;
    }

    const tool = target.closest('#tool-list .chip[data-apotheon-tool]');
    if (tool) {
      event.preventDefault();
      event.stopPropagation();
      toolInfo(tool.dataset.apotheonTool);
    }
  }, true);

  let applyTimer = null;
  const observer = new MutationObserver(() => {
    if (applyTimer) return;
    applyTimer = window.setTimeout(() => {
      applyTimer = null;
      applyEnhancements();
    }, 60);
  });
  observer.observe(document.body, { childList: true, subtree: true, characterData: true });

  async function loadCatalog() {
    try {
      const response = await fetch('/api/catalog', { cache: 'no-store' });
      if (response.ok) state.catalog = await response.json();
    } catch (_error) {
      state.catalog = fallbackCatalog;
    }
    applyEnhancements();
  }

  ensureUI();
  loadCatalog();
  refreshRun(false);
  window.setInterval(() => refreshRun(false), 7000);
})();
