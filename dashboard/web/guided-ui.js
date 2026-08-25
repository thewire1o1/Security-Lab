(() => {
  const profileCopy = {
    android: { label: 'Android App', description: 'Create an app for Android phones and tablets.', output: 'Android application' },
    ios: { label: 'iPhone & iPad App', description: 'Create a native app for iPhone and iPad.', output: 'iOS application' },
    flutter: { label: 'Cross-platform App', description: 'Create one app project for Android, iPhone, and the web.', output: 'cross-platform application' },
    'react-native': { label: 'React Native App', description: 'Create one mobile app project for Android and iPhone.', output: 'mobile application' },
    nextjs: { label: 'Website / Web App', description: 'Create a modern website or browser-based application.', output: 'web application' },
    'fullstack-web': { label: 'Full-stack Web App', description: 'Create a complete web application with frontend and backend pieces.', output: 'full-stack web application' },
    fastapi: { label: 'Web API', description: 'Create a backend service that other apps and websites can connect to.', output: 'web API' },
    security: { label: 'Security Workspace', description: 'Create a workspace for security checks, evidence, and review automation.', output: 'security workspace' },
  };

  const commandCopy = {
    build: { label: 'Build', description: 'Create the runnable or installable output from this project.' },
    lint: { label: 'Check quality', description: 'Look for code problems before they become bugs.' },
    test: { label: 'Test', description: 'Run automated checks to make sure the project behaves as expected.' },
    dev: { label: 'Preview', description: 'Start the project so you can see and try it while you work.' },
    start: { label: 'Preview', description: 'Start the project so you can see and try it while you work.' },
    deploy: { label: 'Publish', description: 'Prepare or send the project to its configured destination.' },
    scan: { label: 'Security check', description: 'Check this project for security problems.' },
    review: { label: 'Review', description: 'Review the project and summarize anything that needs attention.' },
  };

  const serviceCopy = {
    'juice-shop': { label: 'Online Store Practice App', technical: 'OWASP Juice Shop', description: 'A safe, intentionally vulnerable website for practicing web security.' },
    dvwa: { label: 'Vulnerable Web App', technical: 'DVWA', description: 'A safe, intentionally vulnerable website for security testing and training.' },
    webgoat: { label: 'Security Training App', technical: 'OWASP WebGoat', description: 'A guided practice application for learning common web security problems.' },
  };

  const infrastructureCopy = {
    dashboard: { label: 'APOTHEON Interface', description: 'The web interface you are using right now.' },
    bridge: { label: 'Automation Bridge', description: 'Connects APOTHEON controls to the environment where work is executed.' },
    mcp: { label: 'Tool Connection Service', description: 'Lets approved tools and services communicate with APOTHEON.' },
  };

  const toolCopy = {
    nmap: 'Network discovery',
    nuclei: 'Web vulnerability checks',
    httpx: 'Website inspection',
    subfinder: 'Domain discovery',
    naabu: 'Port discovery',
    semgrep: 'Code security review',
    bandit: 'Python security review',
    'pip-audit': 'Python dependency check',
    trivy: 'Container and dependency check',
    gitleaks: 'Secret detection',
    ffuf: 'Web content discovery',
    yara: 'File pattern analysis',
    radare2: 'Binary inspection',
    shellcheck: 'Shell script quality check',
  };

  const actionCopy = {
    up: ['Start practice lab', 'Turn on the safe training applications.'],
    down: ['Stop practice lab', 'Turn off the training applications.'],
    scan: ['Security check', 'Choose a target, choose how thorough to be, then see what APOTHEON finds.'],
    defend: ['Check defenses', 'Run the defensive checks and summarize anything that needs attention.'],
    review: ['Review code', 'Inspect project code and explain the important results.'],
    report: ['Create report', 'Turn the latest evidence into a readable report.'],
  };

  let snapshotCache = null;
  let snapshotAt = 0;
  let scheduled = false;
  let runSyncing = false;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function humanize(value) {
    return String(value || '')
      .replace(/[-_]+/g, ' ')
      .replace(/\b\w/g, (char) => char.toUpperCase());
  }

  function profileInfo(name) {
    return profileCopy[String(name || '').toLowerCase()] || {
      label: humanize(name || 'Project'),
      description: 'A managed APOTHEON project with automated build, test, and review actions.',
      output: 'project',
    };
  }

  async function snapshot(force = false) {
    if (!force && snapshotCache && Date.now() - snapshotAt < 5000) return snapshotCache;
    try {
      const response = await fetch('/api/status', { cache: 'no-store' });
      if (!response.ok) return snapshotCache || {};
      snapshotCache = await response.json();
      snapshotAt = Date.now();
    } catch (_error) {
      snapshotCache = snapshotCache || {};
    }
    return snapshotCache;
  }

  function renameNavigation() {
    document.querySelectorAll('[data-page="systems"] .nav-label, .rail-button[data-page="systems"] span').forEach((node) => {
      node.textContent = 'Workspace';
    });

    const systems = document.getElementById('page-systems');
    if (systems) {
      const kicker = systems.querySelector('.brand-kicker');
      const title = systems.querySelector('.brand-title');
      const subtitle = systems.querySelector('.brand-sub');
      if (kicker) kicker.textContent = 'APOTHEON workspace';
      if (title) title.textContent = 'Your workspace';
      if (subtitle) subtitle.textContent = 'Apps, security targets, automation starters, and the services that keep them running.';

      const labels = {
        all: 'Everything',
        projects: 'Your projects',
        services: 'Practice apps',
        profiles: 'Start something',
        infrastructure: 'System services',
      };
      systems.querySelectorAll('[data-filter]').forEach((button) => {
        if (labels[button.dataset.filter]) button.textContent = labels[button.dataset.filter];
      });
      const resourceTitle = systems.querySelector('.section-head h2');
      if (resourceTitle) resourceTitle.textContent = 'What you have';
    }
  }

  function guideHome() {
    const labels = {
      'new-project-home': 'Create something',
      'start-home': 'Start practice lab',
      'scan-home': 'Security check',
      'activity-home': 'Recent work',
    };
    Object.entries(labels).forEach(([id, label]) => {
      const button = document.getElementById(id);
      const text = button?.querySelector('span');
      if (text) text.textContent = label;
    });

    const cardCopy = {
      'Cloud Lab': ['Practice Lab', 'Safe training apps for learning and testing.'],
      Development: ['Build & Create', 'Apps, websites, APIs, and automated projects.'],
      'Security Lab': ['Security', 'Check apps, code, and systems for problems.'],
      Infrastructure: ['System', 'The services that keep APOTHEON running.'],
    };
    document.querySelectorAll('#home-grid .hero-card').forEach((card) => {
      const title = card.querySelector('h3');
      if (!title || !cardCopy[title.textContent.trim()]) return;
      const [label, copy] = cardCopy[title.textContent.trim()];
      title.textContent = label;
      if (!card.querySelector('.guided-card-copy')) title.insertAdjacentElement('afterend', el('p', 'guided-card-copy', copy));
    });
  }

  function detailsBlock(title, rows) {
    const details = el('details', 'guided-advanced');
    details.appendChild(el('summary', '', title));
    const list = el('div', 'guided-tech-list');
    rows.filter((row) => row && row[1]).forEach(([key, value]) => {
      const item = el('div', 'guided-tech-row');
      item.appendChild(el('span', '', key));
      item.appendChild(el('b', '', value));
      list.appendChild(item);
    });
    details.appendChild(list);
    return details;
  }

  function transformProjectCard(card) {
    if (card.dataset.guided === 'project') return;
    const title = card.querySelector('.resource-title');
    const meta = card.querySelector('.resource-meta');
    const side = card.querySelector('.resource-side');
    const actions = card.querySelector('.project-actions');
    if (!title || !meta || !actions) return;

    const projectName = title.textContent.trim();
    const metaValues = [...meta.querySelectorAll('span')].map((node) => node.textContent.trim());
    const profileName = metaValues[0] || 'project';
    const info = profileInfo(profileName);
    const runner = metaValues[1] || '';
    const location = metaValues.slice(2).join(' · ');

    meta.replaceChildren(el('span', 'guided-kind', info.label));
    const description = el('p', 'guided-description', info.description);
    meta.insertAdjacentElement('afterend', description);

    const open = el('button', 'guided-primary-action', 'Open project');
    open.type = 'button';
    open.addEventListener('click', (event) => {
      event.stopPropagation();
      openProjectWorkspace(projectName);
    });
    actions.prepend(open);

    actions.querySelectorAll('[data-run-project]').forEach((button) => {
      const command = String(button.dataset.command || '').toLowerCase();
      const copy = commandCopy[command] || { label: humanize(command), description: `Run the ${humanize(command)} automation for this project.` };
      const mobileBuild = command === 'build' && ['android', 'ios', 'flutter', 'react-native'].includes(profileName);
      button.textContent = mobileBuild ? 'Build app' : copy.label;
      button.title = mobileBuild ? 'Create the runnable or installable app package.' : copy.description;
    });
    actions.querySelectorAll('[data-publish-project]').forEach((button) => {
      button.textContent = 'Save to GitHub';
      button.title = 'Create a private GitHub repository for this project.';
    });

    const advanced = detailsBlock('Technical details', [
      ['Project type', profileName],
      ['Execution system', runner],
      ['Repository', location],
    ]);
    actions.insertAdjacentElement('afterend', advanced);

    if (side) {
      side.replaceChildren(el('strong', '', info.label), el('small', '', 'project'));
    }
    card.dataset.guided = 'project';
  }

  function transformProfileCard(card) {
    if (card.dataset.guided === 'profile') return;
    const createButton = card.querySelector('[data-create-profile]');
    const title = card.querySelector('.resource-title');
    const meta = card.querySelector('.resource-meta');
    const side = card.querySelector('.resource-side');
    if (!createButton || !title || !meta) return;

    const name = createButton.dataset.createProfile || title.textContent.trim();
    const info = profileInfo(name);
    const technical = [...meta.querySelectorAll('span')].map((node) => node.textContent.trim()).filter(Boolean);
    title.textContent = info.label;
    meta.replaceChildren(el('span', 'guided-kind', 'Starter'));
    meta.insertAdjacentElement('afterend', el('p', 'guided-description', info.description));
    createButton.textContent = 'Start this';
    createButton.title = `Create a new ${info.output} from this starter.`;
    createButton.parentElement?.insertAdjacentElement('afterend', detailsBlock('Technical details', [
      ['Profile', name],
      ['Stack', technical.join(' · ')],
    ]));
    if (side) side.replaceChildren(el('strong', '', 'Starter'), el('small', '', 'template'));
    card.dataset.guided = 'profile';
  }

  function transformServiceCard(card) {
    if (card.dataset.guided === 'service') return;
    const key = card.dataset.detailName || '';
    const copy = serviceCopy[key] || { label: humanize(key), technical: key, description: 'A managed service available to APOTHEON.' };
    const title = card.querySelector('.resource-title');
    const meta = card.querySelector('.resource-meta');
    const side = card.querySelector('.resource-side');
    if (!title || !meta) return;
    const technical = [...meta.querySelectorAll('span')].map((node) => node.textContent.trim()).filter(Boolean);
    const status = technical[0] || 'Status unavailable';
    title.textContent = copy.label;
    meta.replaceChildren(el('span', status.toLowerCase().includes('online') ? 'ok' : 'bad', status));
    meta.insertAdjacentElement('afterend', el('p', 'guided-description', copy.description));
    meta.parentElement?.appendChild(detailsBlock('Technical details', [
      ['Technical name', copy.technical],
      ['Runtime', technical.slice(1).join(' · ')],
    ]));
    if (side) side.replaceChildren(el('strong', '', status.replace(/^●\s*/, '')), el('small', '', 'practice app'));
    card.dataset.guided = 'service';
  }

  function transformInfrastructureCard(card) {
    if (card.dataset.guided === 'infrastructure') return;
    const key = String(card.dataset.detailName || '').toLowerCase();
    const copy = infrastructureCopy[key] || { label: humanize(key), description: 'A background service APOTHEON uses to operate and automate work.' };
    const title = card.querySelector('.resource-title');
    const meta = card.querySelector('.resource-meta');
    const side = card.querySelector('.resource-side');
    if (!title || !meta) return;
    const technical = [...meta.querySelectorAll('span')].map((node) => node.textContent.trim()).filter(Boolean);
    const status = technical[0] || 'Status unavailable';
    title.textContent = copy.label;
    meta.replaceChildren(el('span', status.toLowerCase().includes('running') ? 'ok' : 'bad', status));
    meta.insertAdjacentElement('afterend', el('p', 'guided-description', copy.description));
    meta.parentElement?.appendChild(detailsBlock('Technical details', [
      ['Service name', key],
      ['Runtime', technical.slice(1).join(' · ')],
    ]));
    if (side) side.replaceChildren(el('strong', '', status.replace(/^●\s*/, '')), el('small', '', 'system service'));
    card.dataset.guided = 'infrastructure';
  }

  function guideResources() {
    document.querySelectorAll('.resource-card[data-kind="projects"]').forEach(transformProjectCard);
    document.querySelectorAll('.resource-card[data-kind="profiles"]').forEach(transformProfileCard);
    document.querySelectorAll('.resource-card[data-kind="services"]').forEach(transformServiceCard);
    document.querySelectorAll('.resource-card[data-kind="infrastructure"]').forEach(transformInfrastructureCard);
  }

  function guideProjectSheet() {
    const sheet = document.getElementById('project-sheet');
    if (!sheet) return;
    const title = sheet.querySelector('#project-sheet-title');
    const input = sheet.querySelector('#project-name');
    const select = sheet.querySelector('#project-profile');
    const create = sheet.querySelector('#create-project');
    if (title) title.textContent = 'What do you want to create?';
    if (input) input.placeholder = 'Name your project';
    if (create) create.textContent = 'Create';
    if (select) {
      [...select.options].forEach((option) => {
        const info = profileInfo(option.value);
        option.textContent = info.label;
      });
      if (!sheet.querySelector('.guided-sheet-help')) {
        const help = el('p', 'guided-sheet-help');
        const update = () => {
          const info = profileInfo(select.value);
          help.textContent = `${info.description} APOTHEON sets up the technical project structure and automation for you.`;
        };
        select.addEventListener('change', update);
        sheet.querySelector('.form-row')?.insertAdjacentElement('afterend', help);
        update();
      }
    }
  }

  function guideControls() {
    const detail = document.getElementById('page-detail');
    if (detail) {
      const controlsHead = [...detail.querySelectorAll('.panel-head h3')].find((node) => node.textContent.trim() === 'Controls');
      if (controlsHead) controlsHead.textContent = 'What you can do';
      const controlPlaneHead = [...detail.querySelectorAll('.panel-head h3')].find((node) => node.textContent.trim() === 'Control plane');
      if (controlPlaneHead) controlPlaneHead.textContent = 'System services';
      const quality = detail.querySelector('.health-card .health-label');
      if (quality?.textContent.trim() === 'Current quality') quality.textContent = 'System health';
    }

    document.querySelectorAll('#control-grid .control').forEach((button, index) => {
      const action = ['up', 'down', 'scan', 'defend', 'review', 'report'][index];
      const copy = actionCopy[action];
      if (!copy) return;
      const label = button.querySelector('span');
      if (label) label.textContent = copy[0];
      button.title = copy[1];
    });
  }

  function guideSettingsAndActivity() {
    const activity = document.getElementById('page-activity');
    if (activity) {
      const kicker = activity.querySelector('.brand-kicker');
      const subtitle = activity.querySelector('.brand-sub');
      if (kicker) kicker.textContent = 'History';
      if (subtitle) subtitle.textContent = 'See what APOTHEON ran, what happened, and anything that still needs attention.';
      activity.querySelectorAll('.panel-head h3').forEach((heading) => {
        if (heading.textContent.trim() === 'Run history') heading.textContent = 'Recent automation';
        if (heading.textContent.trim() === 'Activity log') heading.textContent = 'Technical log';
      });
    }

    const settings = document.getElementById('page-settings');
    if (settings) {
      const subtitle = settings.querySelector('.brand-sub');
      if (subtitle) subtitle.textContent = 'How APOTHEON runs work, connects tools, and presents information.';
      settings.querySelectorAll('.panel-head h3').forEach((heading) => {
        if (heading.textContent.trim() === 'Execution runners') heading.textContent = 'Where work runs';
        if (heading.textContent.trim() === 'Security tooling') heading.textContent = 'Security capabilities';
      });
      const source = [...settings.querySelectorAll('.setting b')].find((node) => node.textContent.trim() === 'Telemetry source');
      if (source) source.textContent = 'Live data source';
    }

    document.querySelectorAll('#tool-list .chip').forEach((chip) => {
      const technical = chip.dataset.technicalName || chip.textContent.trim();
      chip.dataset.technicalName = technical;
      const plain = toolCopy[technical.toLowerCase()];
      if (plain) {
        chip.textContent = plain;
        chip.title = `Technical tool: ${technical}`;
      }
    });

    document.querySelectorAll('#runner-summary .scan-row').forEach((row) => {
      const heading = row.querySelector('b');
      const small = row.querySelector('small');
      if (!heading || row.dataset.guidedRunner === 'true') return;
      const original = heading.textContent.trim();
      if (original === 'GitHub Actions') {
        heading.textContent = 'Cloud automation';
        if (small) small.textContent = 'Runs builds and checks in GitHub when a project needs cloud execution.';
      } else if (original === 'Local runners') {
        heading.textContent = 'Local automation';
        if (small) small.textContent = 'Runs work directly inside the APOTHEON environment.';
      } else if (original === 'External runners') {
        heading.textContent = 'Connected automation';
        if (small) small.textContent = 'Other approved environments APOTHEON can use for work.';
      }
      row.dataset.guidedRunner = 'true';
    });
  }

  function findProjectButton(name, command) {
    return [...document.querySelectorAll('[data-run-project]')].find((button) => button.dataset.runProject === name && button.dataset.command === command);
  }

  function findPublishButton(name) {
    return [...document.querySelectorAll('[data-publish-project]')].find((button) => button.dataset.publishProject === name);
  }

  function ensureWorkspaceOverlay() {
    let overlay = document.getElementById('guided-project-overlay');
    if (overlay) return overlay;
    overlay = el('div', 'guided-overlay');
    overlay.id = 'guided-project-overlay';
    const panel = el('section', 'guided-project-panel');
    panel.id = 'guided-project-panel';
    overlay.appendChild(panel);
    overlay.addEventListener('click', (event) => {
      if (event.target === overlay) closeProjectWorkspace();
    });
    document.body.appendChild(overlay);
    return overlay;
  }

  function closeProjectWorkspace() {
    const overlay = document.getElementById('guided-project-overlay');
    if (!overlay) return;
    overlay.classList.remove('open');
    document.body.style.overflow = '';
  }

  async function openProjectWorkspace(name) {
    const data = await snapshot(true);
    const project = (data?.platform?.projects || []).find((row) => row.name === name) || { name, profile: 'project', commands: [] };
    const profile = (data?.platform?.profiles || []).find((row) => row.name === project.profile);
    const info = profileInfo(project.profile);
    const overlay = ensureWorkspaceOverlay();
    const panel = document.getElementById('guided-project-panel');
    panel.replaceChildren();

    const head = el('div', 'guided-project-head');
    const heading = el('div');
    heading.appendChild(el('span', 'guided-eyebrow', info.label));
    heading.appendChild(el('h2', '', project.name));
    head.appendChild(heading);
    const close = el('button', 'guided-close', '×');
    close.type = 'button';
    close.setAttribute('aria-label', 'Close project');
    close.addEventListener('click', closeProjectWorkspace);
    head.appendChild(close);
    panel.appendChild(head);

    const intro = el('section', 'guided-workspace-intro');
    intro.appendChild(el('strong', '', 'What is this?'));
    intro.appendChild(el('p', '', profile?.description || info.description));
    panel.appendChild(intro);

    const output = el('section', 'guided-output-card');
    output.appendChild(el('span', 'guided-output-icon', ['android', 'ios', 'flutter', 'react-native'].includes(project.profile) ? '▯' : '◇'));
    const outputText = el('div');
    outputText.appendChild(el('strong', '', `Your ${info.output}`));
    outputText.appendChild(el('p', '', 'Use the actions below to keep working. APOTHEON handles the underlying commands and keeps technical output available only when you need it.'));
    output.appendChild(outputText);
    panel.appendChild(output);

    const section = el('section', 'guided-workspace-actions');
    section.appendChild(el('h3', '', 'What do you want to do?'));
    const grid = el('div', 'guided-action-grid');
    (project.commands || []).forEach((command) => {
      const commandName = String(command).toLowerCase();
      const base = commandCopy[commandName] || { label: humanize(commandName), description: `Run the ${humanize(commandName)} automation.` };
      const mobileBuild = commandName === 'build' && ['android', 'ios', 'flutter', 'react-native'].includes(project.profile);
      const label = mobileBuild ? 'Build app' : base.label;
      const description = mobileBuild ? 'Package the app so it can be run or installed.' : base.description;
      const button = el('button', 'guided-workspace-action');
      button.type = 'button';
      button.appendChild(el('strong', '', label));
      button.appendChild(el('span', '', description));
      button.addEventListener('click', () => {
        closeProjectWorkspace();
        findProjectButton(project.name, command)?.click();
      });
      grid.appendChild(button);
    });
    if (!project.repository) {
      const publish = el('button', 'guided-workspace-action');
      publish.type = 'button';
      publish.appendChild(el('strong', '', 'Save to GitHub'));
      publish.appendChild(el('span', '', 'Create a private repository so the project is backed up and ready for collaboration.'));
      publish.addEventListener('click', () => {
        closeProjectWorkspace();
        findPublishButton(project.name)?.click();
      });
      grid.appendChild(publish);
    }
    section.appendChild(grid);
    panel.appendChild(section);

    panel.appendChild(detailsBlock('Advanced technical details', [
      ['Project profile', project.profile],
      ['Execution system', project.runner || 'local'],
      ['Source location', project.path || 'Managed by APOTHEON'],
      ['Repository', project.repository || 'Local only'],
      ['Available commands', (project.commands || []).join(', ')],
    ]));

    overlay.classList.add('open');
    document.body.style.overflow = 'hidden';
  }

  function plainFailureReason(run) {
    const raw = (run?.technical_tail || []).join('\n').toLowerCase();
    if (raw.includes('command not found') || raw.includes('not installed')) return 'A required build or analysis tool is not available in the current environment.';
    if (raw.includes('no such file') || raw.includes('not found')) return 'A required project file or dependency could not be found.';
    if (raw.includes('permission denied') || raw.includes('unauthorized')) return 'The task was blocked by a permission or authorization problem.';
    if (raw.includes('timeout') || raw.includes('timed out')) return 'The task took too long and APOTHEON stopped waiting for it.';
    if (raw.includes('exit code') || raw.includes('failed')) return 'One of the automated steps returned an error before the task could finish.';
    return 'One of the required automation steps did not complete successfully.';
  }

  async function guideRun() {
    if (runSyncing) return;
    runSyncing = true;
    try {
      const response = await fetch('/api/run', { cache: 'no-store' });
      if (!response.ok) return;
      const payload = await response.json();
      const run = payload?.run;
      if (!run || run.action === 'scan') return;

      const peek = document.getElementById('apo-run-peek');
      if (peek && ['failed', 'succeeded'].includes(run.state)) {
        const strong = peek.querySelector('strong');
        const status = peek.querySelector('span');
        const right = peek.querySelector(':scope > b');
        if (run.state === 'failed') {
          if (strong) strong.textContent = 'Action needs attention';
          if (status) status.textContent = 'Tap to see what happened and what to do next.';
          if (right) right.textContent = 'Review';
          peek.classList.add('guided-failed');
        } else {
          if (strong) strong.textContent = 'Action complete';
          if (status) status.textContent = 'Completed. Tap to review.';
          if (right) right.textContent = 'Done';
          peek.classList.remove('guided-failed');
        }
      }

      const body = document.querySelector('#apo-run-panel .apo-panel-body');
      if (!body || !['failed', 'succeeded'].includes(run.state) || body.querySelector('[data-guided-run-result]')) return;
      const result = el('section', `guided-run-result ${run.state}`);
      result.dataset.guidedRunResult = run.id || 'latest';
      result.appendChild(el('span', 'guided-eyebrow', run.state === 'failed' ? 'Needs attention' : 'Completed'));
      result.appendChild(el('h3', '', run.state === 'failed' ? 'This task did not finish.' : 'This task finished successfully.'));
      result.appendChild(el('p', '', run.state === 'failed'
        ? plainFailureReason(run)
        : 'APOTHEON completed the requested work. The exact implementation details remain available below if you want them.'));
      const next = el('div', 'guided-next-step');
      next.appendChild(el('strong', '', 'What should I do next?'));
      next.appendChild(el('p', '', run.state === 'failed'
        ? 'Review the explanation above. Open Technical details only if you need the exact error, then correct the issue and try the action again.'
        : 'Continue working on the project, open Activity for the saved history, or start another action.'));
      result.appendChild(next);
      body.prepend(result);
    } catch (_error) {
      // The guided layer is additive. Core controls remain available if this request fails.
    } finally {
      runSyncing = false;
    }
  }

  function guideControlPlaneRows() {
    document.querySelectorAll('#control-plane-list .scan-row').forEach((row) => {
      const heading = row.querySelector('b');
      const small = row.querySelector('small');
      if (!heading || row.dataset.guidedControl === 'true') return;
      const key = heading.textContent.trim().toLowerCase();
      const copy = infrastructureCopy[key];
      if (copy) {
        heading.textContent = copy.label;
        if (small) small.textContent = copy.description;
      }
      row.dataset.guidedControl = 'true';
    });
  }

  function apply() {
    renameNavigation();
    guideHome();
    guideResources();
    guideProjectSheet();
    guideControls();
    guideSettingsAndActivity();
    guideControlPlaneRows();
    guideRun();
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(() => {
      scheduled = false;
      apply();
    });
  }

  function start() {
    apply();
    const observer = new MutationObserver(schedule);
    observer.observe(document.body, { childList: true, subtree: true });
    window.setInterval(() => {
      schedule();
      snapshot(true);
    }, 4000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
