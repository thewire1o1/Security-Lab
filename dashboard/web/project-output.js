(() => {
  let busy = false;
  let lastKey = '';

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = String(text);
    return element;
  }

  function artifactLabel(profile, name) {
    if (name === 'android-apk') return 'Download APK';
    if (name === 'react-native-android-apk') return 'Download Android app';
    if (name === 'flutter-android-apk') return 'Download Android app';
    if (name === 'flutter-web') return 'Download web build';
    if (name === 'ios-simulator-app') return 'Download iOS simulator build';
    if (profile === 'android' && name.toLowerCase().includes('apk')) return 'Download APK';
    return `Download ${name.replace(/[-_]+/g, ' ')}`;
  }

  function latestBuild(jobs, projectName) {
    return (jobs || []).find((job) => job?.project === projectName && job?.command === 'build') || null;
  }

  function resultCard(project, job) {
    const card = node('section', 'guided-project-result');
    card.dataset.projectOutput = project.name;
    card.appendChild(node('span', 'guided-eyebrow', 'Build output'));

    if (!job) {
      card.appendChild(node('h3', '', 'No finished build yet'));
      card.appendChild(node('p', '', 'Choose Build app below when you want APOTHEON to create a runnable or installable version.'));
      return card;
    }

    const state = String(job.state || 'unknown').toLowerCase();
    if (['queued', 'running', 'submitted'].includes(state)) {
      card.classList.add('running');
      card.appendChild(node('h3', '', 'Building your app…'));
      card.appendChild(node('p', '', 'APOTHEON is running the build and will make the finished output available here when it is ready.'));
      return card;
    }

    if (state === 'failed') {
      card.classList.add('failed');
      card.appendChild(node('h3', '', 'The latest build needs attention'));
      card.appendChild(node('p', '', 'The app package was not created. Review the completed action for the explanation, then try Build app again.'));
      return card;
    }

    if (state !== 'succeeded') {
      card.appendChild(node('h3', '', 'Build status unavailable'));
      card.appendChild(node('p', '', 'APOTHEON has build history for this project, but the latest result is not in a final state yet.'));
      return card;
    }

    const artifacts = Array.isArray(job.artifacts) ? job.artifacts : [];
    if (!artifacts.length) {
      card.appendChild(node('h3', '', 'Build completed'));
      card.appendChild(node('p', '', 'The build finished successfully. No downloadable package was reported for this project type.'));
      return card;
    }

    card.classList.add('ready');
    card.appendChild(node('h3', '', 'Your build is ready'));
    card.appendChild(node('p', '', 'Choose the output you want. APOTHEON keeps the build details and history separately.'));
    const actions = node('div', 'guided-project-downloads');
    artifacts.forEach((artifact) => {
      if (!artifact?.name) return;
      const link = node('a', 'guided-download', artifactLabel(project.profile, artifact.name));
      link.href = `/api/job-artifact?job=${encodeURIComponent(job.id)}&artifact=${encodeURIComponent(artifact.name)}`;
      link.setAttribute('download', '');
      actions.appendChild(link);
    });
    card.appendChild(actions);
    return card;
  }

  async function sync() {
    if (busy) return;
    const overlay = document.getElementById('guided-project-overlay');
    const panel = document.getElementById('guided-project-panel');
    if (!overlay?.classList.contains('open') || !panel) return;
    const projectName = panel.querySelector('.guided-project-head h2')?.textContent?.trim();
    if (!projectName) return;

    busy = true;
    try {
      const response = await fetch('/api/status', { cache: 'no-store' });
      if (!response.ok) return;
      const data = await response.json();
      const project = (data?.platform?.projects || []).find((row) => row.name === projectName);
      if (!project) return;
      const job = latestBuild(data?.platform?.jobs || [], projectName);
      const key = `${projectName}:${job?.id || 'none'}:${job?.state || 'none'}:${(job?.artifacts || []).map((row) => row.name).join(',')}`;
      if (key === lastKey && panel.querySelector('[data-project-output]')) return;
      lastKey = key;
      panel.querySelector('[data-project-output]')?.remove();
      const output = resultCard(project, job);
      const intro = panel.querySelector('.guided-output-card');
      if (intro?.nextSibling) panel.insertBefore(output, intro.nextSibling);
      else if (intro) intro.insertAdjacentElement('afterend', output);
      else panel.prepend(output);
    } catch (_error) {
      // Project output is supplemental. Core project controls remain available.
    } finally {
      busy = false;
    }
  }

  function start() {
    const observer = new MutationObserver(() => window.requestAnimationFrame(sync));
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
    window.setInterval(sync, 2500);
    sync();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
