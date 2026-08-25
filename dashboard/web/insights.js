(() => {
  const cache = new Map();
  let loadingRun = '';

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = String(text);
    return element;
  }

  function number(value) {
    const parsed = Number(value || 0);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function moveQuickActions() {
    const grid = document.getElementById('home-grid');
    const strip = document.querySelector('#page-home .quick-strip');
    const head = strip?.previousElementSibling;
    if (!grid || !strip || !head || head.dataset.apotheonPriority === 'true') return;

    head.dataset.apotheonPriority = 'true';
    head.classList.add('apo-quick-top');
    grid.parentNode?.insertBefore(head, grid);
    grid.parentNode?.insertBefore(strip, grid);

    const scanLabel = document.querySelector('#scan-home span');
    if (scanLabel) scanLabel.textContent = 'Security check';
  }

  function interpretation(run, status) {
    const findings = status?.findings || {};
    const critical = number(findings.critical);
    const high = number(findings.high);
    const medium = number(findings.medium);
    const low = number(findings.low);
    const info = number(findings.info);
    const highPriority = critical + high;
    const weakness = (run.stages || []).find((stage) => stage.id === 'weakness');
    const limited = run.profile === 'quick' || weakness?.state === 'skipped';
    const toolUnavailable = limited && String(weakness?.detail || '').toLowerCase().includes('not installed');

    if (run.state === 'failed') {
      return {
        tone: 'failed',
        label: 'Needs attention',
        headline: 'The security check did not finish.',
        summary: 'APOTHEON stopped before it could produce a complete result. Your target was not silently treated as safe.',
        meaning: 'A failed check means the evidence is incomplete. The last execution details can show whether the target, runtime, or one of the underlying tools needs attention.',
        next: 'Open Technical details, correct the failed step, then run the same check again.',
        metrics: [
          ['Completed', `${number(run.progress)}%`],
          ['Target', run.target_label || 'Selected target'],
          ['Check', run.profile_label || 'Security check'],
        ],
        technical: `Run state: failed\nProfile: ${run.profile || 'unknown'}\nTarget: ${run.target || 'unknown'}`,
      };
    }

    if (limited) {
      return {
        tone: 'limited',
        label: 'Initial check complete',
        headline: 'APOTHEON completed the initial inspection.',
        summary: toolUnavailable
          ? 'Service and web inspection completed, but known-pattern vulnerability checks were unavailable in this runtime.'
          : 'Service and web inspection completed. This check intentionally stopped before known-pattern vulnerability testing.',
        meaning: 'This result tells you what is exposed and reachable, but it does not make a broad statement about application security.',
        next: toolUnavailable
          ? 'Enable Web Vulnerability Checks, then run Standard Security Check for deeper coverage.'
          : 'Run Standard Security Check when you want APOTHEON to check for known vulnerability patterns.',
        metrics: [
          ['High priority', 'Not checked'],
          ['Coverage', 'Initial'],
          ['Target', run.target_label || 'Selected target'],
        ],
        technical: `Vulnerability templates: ${toolUnavailable ? 'unavailable' : 'not included'}\nProfile: ${run.profile_label || run.profile || 'Quick Check'}\nTarget: ${run.target_label || run.target || 'unknown'}`,
      };
    }

    if (highPriority > 0) {
      return {
        tone: 'attention',
        label: 'Review recommended',
        headline: 'Important security issues were detected.',
        summary: `APOTHEON found ${highPriority} high-priority ${highPriority === 1 ? 'finding' : 'findings'} during this check.`,
        meaning: 'These findings deserve attention before lower-priority results. A scanner can still produce false positives, so validation should come before making a change.',
        next: 'Validate the high-priority findings, review the evidence, then decide what needs remediation.',
        metrics: [
          ['High priority', highPriority],
          ['Needs review', medium],
          ['Lower priority', low],
        ],
        technical: `Critical: ${critical}\nHigh: ${high}\nMedium: ${medium}\nLow: ${low}\nInformational: ${info}`,
      };
    }

    if (medium > 0) {
      return {
        tone: 'review',
        label: 'Review recommended',
        headline: 'Security issues were detected.',
        summary: `APOTHEON found ${medium} medium-priority ${medium === 1 ? 'finding' : 'findings'} and no high-priority findings in this check.`,
        meaning: 'The result does not indicate an immediate high-priority issue, but the findings should still be reviewed and validated in context.',
        next: 'Review the medium-priority findings and validate anything that could affect the application or its data.',
        metrics: [
          ['High priority', 0],
          ['Needs review', medium],
          ['Lower priority', low],
        ],
        technical: `Critical: ${critical}\nHigh: ${high}\nMedium: ${medium}\nLow: ${low}\nInformational: ${info}`,
      };
    }

    if (low + info > 0) {
      return {
        tone: 'low',
        label: 'Lower-priority findings',
        headline: 'No high-priority issues were detected by this check.',
        summary: `APOTHEON recorded ${low + info} lower-priority or informational ${low + info === 1 ? 'result' : 'results'}.`,
        meaning: 'Nothing in this run was classified as critical, high, or medium. Lower-priority results can still be useful for hardening and cleanup.',
        next: 'Review the lower-priority results when appropriate, or run a deeper check if you need broader coverage.',
        metrics: [
          ['High priority', 0],
          ['Needs review', 0],
          ['Lower / info', low + info],
        ],
        technical: `Critical: ${critical}\nHigh: ${high}\nMedium: ${medium}\nLow: ${low}\nInformational: ${info}`,
      };
    }

    return {
      tone: 'clear',
      label: 'Check complete',
      headline: 'No known-pattern weaknesses were detected by this check.',
      summary: 'The selected checks completed without producing a vulnerability finding.',
      meaning: 'This is a clean result for the checks that ran. It is not proof that the application has no security problems.',
      next: run.profile === 'deep'
        ? 'Review the evidence if needed, then continue with another target or a different type of analysis.'
        : 'Run Deep Security Check if you need broader coverage before making a decision.',
      metrics: [
        ['High priority', 0],
        ['Needs review', 0],
        ['Findings', 0],
      ],
      technical: `Critical: ${critical}\nHigh: ${high}\nMedium: ${medium}\nLow: ${low}\nInformational: ${info}`,
    };
  }

  function addResultCard(run, result) {
    const body = document.querySelector('#apo-run-panel .apo-panel-body');
    if (!body || body.querySelector('[data-apotheon-insight]')) return;

    body.querySelectorAll('.apo-run-summary').forEach((summary) => {
      const heading = summary.querySelector('strong')?.textContent?.trim();
      if (heading === 'What next?' || heading === 'Run needs attention') summary.remove();
    });

    const card = node('section', `apo-insight apo-insight-${result.tone}`);
    card.dataset.apotheonInsight = run.id || 'latest';

    const top = node('div', 'apo-insight-top');
    top.appendChild(node('span', 'apo-insight-label', result.label));
    top.appendChild(node('span', 'apo-insight-check', run.profile_label || 'Security check'));
    card.appendChild(top);
    card.appendChild(node('h3', 'apo-insight-title', result.headline));
    card.appendChild(node('p', 'apo-insight-summary', result.summary));

    const metrics = node('div', 'apo-insight-metrics');
    result.metrics.forEach(([label, value]) => {
      const metric = node('div', 'apo-insight-metric');
      metric.appendChild(node('span', '', label));
      metric.appendChild(node('strong', '', value));
      metrics.appendChild(metric);
    });
    card.appendChild(metrics);

    const meaning = node('div', 'apo-insight-block');
    meaning.appendChild(node('b', '', 'What this means'));
    meaning.appendChild(node('p', '', result.meaning));
    card.appendChild(meaning);

    const next = node('div', 'apo-insight-block');
    next.appendChild(node('b', '', 'Recommended next step'));
    next.appendChild(node('p', '', result.next));
    card.appendChild(next);

    const actions = node('div', 'apo-insight-actions');
    const rerun = node('button', 'primary', 'Run another check');
    rerun.type = 'button';
    rerun.addEventListener('click', () => document.getElementById('scan-home')?.click());
    actions.appendChild(rerun);

    const activity = node('button', '', 'Open Activity');
    activity.type = 'button';
    activity.addEventListener('click', () => {
      document.querySelector('#apo-run-panel .apo-close')?.click();
      document.querySelector('.nav-button[data-page="activity"]')?.click();
    });
    actions.appendChild(activity);
    card.appendChild(actions);

    const details = node('details', 'apo-insight-technical');
    details.appendChild(node('summary', '', 'Technical result details'));
    details.appendChild(node('pre', '', result.technical));
    card.appendChild(details);

    const firstSummary = body.querySelector('.apo-run-summary');
    if (firstSummary?.nextSibling) body.insertBefore(card, firstSummary.nextSibling);
    else body.prepend(card);
  }

  async function syncResult() {
    moveQuickActions();
    const panel = document.getElementById('apo-run-panel');
    if (!panel || panel.querySelector('[data-apotheon-insight]')) return;

    let payload;
    try {
      const runResponse = await fetch('/api/run', { cache: 'no-store' });
      if (!runResponse.ok) return;
      payload = await runResponse.json();
    } catch (_error) {
      return;
    }

    const run = payload?.run;
    if (!run || run.action !== 'scan' || !['succeeded', 'failed'].includes(run.state)) return;

    if (cache.has(run.id)) {
      addResultCard(run, cache.get(run.id));
      return;
    }
    if (loadingRun === run.id) return;
    loadingRun = run.id;

    try {
      const statusResponse = await fetch('/api/status', { cache: 'no-store' });
      const status = statusResponse.ok ? await statusResponse.json() : {};
      const result = interpretation(run, status);
      cache.set(run.id, result);
      addResultCard(run, result);
    } catch (_error) {
      const result = interpretation(run, {});
      cache.set(run.id, result);
      addResultCard(run, result);
    } finally {
      loadingRun = '';
    }
  }

  function start() {
    moveQuickActions();
    const observer = new MutationObserver(() => window.requestAnimationFrame(syncResult));
    observer.observe(document.body, { childList: true, subtree: true });
    window.setInterval(syncResult, 1500);
    syncResult();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
