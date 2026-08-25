(() => {
  let lastRunId = '';
  let watchToken = 0;
  let cleanupBusy = false;

  function create(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function sleep(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  async function readRun() {
    try {
      const response = await fetch('/api/run', { cache: 'no-store' });
      if (!response.ok) return null;
      const payload = await response.json();
      return payload?.run || null;
    } catch (_error) {
      return null;
    }
  }

  function closeOverlay() {
    const overlay = document.getElementById('apo-run-overlay');
    if (!overlay) return;
    overlay.classList.remove('open');
    overlay.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }

  function openStarter(run) {
    const overlay = document.getElementById('apo-run-overlay');
    const panel = document.getElementById('apo-run-panel');
    if (!overlay || !panel || !run) return;

    panel.replaceChildren();
    const head = create('div', 'apo-panel-head');
    const heading = create('div');
    heading.appendChild(create('div', 'apo-eyebrow', 'Active run'));
    heading.appendChild(create('h2', 'apo-panel-title', run.title || 'Starting automation'));
    head.appendChild(heading);
    const close = create('button', 'apo-close', '×');
    close.type = 'button';
    close.setAttribute('aria-label', 'Close');
    close.addEventListener('click', closeOverlay);
    head.appendChild(close);
    panel.appendChild(head);

    const body = create('div', 'apo-panel-body');
    const meta = create('div', 'apo-run-meta');
    const target = create('span');
    target.append('Working on: ');
    target.appendChild(create('b', '', run.target_label || run.project || 'APOTHEON ONE'));
    meta.appendChild(target);
    const status = create('span');
    status.append('Status: ');
    status.appendChild(create('b', '', run.state === 'queued' ? 'Starting' : 'Running'));
    meta.appendChild(status);
    body.appendChild(meta);

    const progress = create('div', 'apo-progress-line');
    const fill = create('span');
    fill.style.width = `${Number(run.progress || 0)}%`;
    progress.appendChild(fill);
    body.appendChild(progress);

    const summary = create('div', 'apo-run-summary');
    summary.appendChild(create('strong', '', run.description || 'APOTHEON is starting the requested work.'));
    summary.appendChild(create('span', '', 'This view will update as each step starts and finishes.'));
    body.appendChild(summary);

    if (Array.isArray(run.stages) && run.stages.length) {
      const section = create('section', 'apo-section');
      section.appendChild(create('h3', '', 'What is happening?'));
      section.appendChild(create('p', 'apo-section-copy', 'Each step explains the outcome instead of requiring you to understand the tool underneath.'));
      const list = create('div', 'apo-stage-list');
      run.stages.forEach((stage) => {
        const row = create('div', `apo-stage ${stage.state || 'pending'}`);
        const top = create('div', 'apo-stage-top');
        top.appendChild(create('span', 'apo-stage-dot'));
        top.appendChild(create('span', 'apo-stage-title', stage.title || stage.id));
        top.appendChild(create('span', 'apo-stage-state', stage.state || 'pending'));
        row.appendChild(top);
        row.appendChild(create('p', 'apo-stage-detail', stage.detail || 'Waiting to start.'));
        list.appendChild(row);
      });
      section.appendChild(list);
      body.appendChild(section);
    }

    panel.appendChild(body);
    overlay.classList.add('open');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }

  async function watchForNewRun(beforeId) {
    const token = ++watchToken;
    for (let attempt = 0; attempt < 40; attempt += 1) {
      await sleep(attempt === 0 ? 120 : 250);
      if (token !== watchToken) return;
      const run = await readRun();
      if (!run) continue;
      lastRunId = run.id || lastRunId;
      if (run.id && run.id !== beforeId && ['queued', 'running'].includes(run.state)) {
        openStarter(run);
        return;
      }
      if (run.id && run.id !== beforeId && ['succeeded', 'failed'].includes(run.state)) {
        return;
      }
    }
  }

  function isRunStartingClick(target) {
    if (target.closest('[data-run-project], [data-publish-project], #create-project, #start-home')) return true;
    const control = target.closest('.control');
    if (!control) return false;
    const label = (control.textContent || '').toLowerCase();
    return !label.includes('security check') && !label.includes('run scan') && !label.includes('scan');
  }

  async function removeWrongNextStep() {
    if (cleanupBusy) return;
    const overlay = document.getElementById('apo-run-overlay');
    const body = document.querySelector('#apo-run-panel .apo-panel-body');
    if (!overlay?.classList.contains('open') || !body) return;
    cleanupBusy = true;
    try {
      const run = await readRun();
      if (!run || run.action === 'scan' || !['succeeded', 'failed'].includes(run.state)) return;
      body.querySelectorAll('.apo-run-summary').forEach((box) => {
        const heading = box.querySelector('strong')?.textContent?.trim() || '';
        if (heading === 'What next?' || heading === 'Run needs attention') box.remove();
      });
    } finally {
      cleanupBusy = false;
    }
  }

  document.addEventListener('click', (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target || !isRunStartingClick(target)) return;
    const before = lastRunId;
    watchForNewRun(before);
  }, true);

  const observer = new MutationObserver(() => window.requestAnimationFrame(removeWrongNextStep));
  observer.observe(document.body, { childList: true, subtree: true });

  async function syncRunId() {
    const run = await readRun();
    if (run?.id) lastRunId = run.id;
  }

  syncRunId();
  window.setInterval(syncRunId, 4000);
})();
