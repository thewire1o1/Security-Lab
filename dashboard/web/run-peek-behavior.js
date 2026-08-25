(() => {
  const dismissedKey = 'apotheon.dismissedRunId';
  let reviewingRunId = '';
  let swipeConsumed = false;
  let syncTimer = 0;

  const style = document.createElement('style');
  style.textContent = `
    .apo-run-peek{touch-action:pan-y;transition:transform .18s ease,opacity .18s ease}
    .apo-run-peek.apo-peek-dismissed{opacity:0;transform:translate(-50%,18px);pointer-events:none}
  `;
  document.head.appendChild(style);

  function storedDismissedRun() {
    try {
      return sessionStorage.getItem(dismissedKey) || '';
    } catch (_error) {
      return '';
    }
  }

  function storeDismissedRun(runId) {
    if (!runId) return;
    try {
      sessionStorage.setItem(dismissedKey, runId);
    } catch (_error) {
      return;
    }
  }

  async function currentRun() {
    try {
      const response = await fetch('/api/run', { cache: 'no-store' });
      if (!response.ok) return null;
      const payload = await response.json();
      return payload.run || null;
    } catch (_error) {
      return null;
    }
  }

  function isTerminal(run) {
    return Boolean(run && (run.state === 'succeeded' || run.state === 'failed'));
  }

  function hidePeek(peek) {
    if (!peek) return;
    peek.classList.add('apo-peek-dismissed');
    window.setTimeout(() => {
      if (peek.classList.contains('apo-peek-dismissed')) peek.classList.remove('visible');
    }, 190);
  }

  async function dismissPeek(peek) {
    const run = await currentRun();
    const runId = run?.id || peek?.dataset.runId || '';
    if (isTerminal(run) || peek?.dataset.terminal === 'true') {
      storeDismissedRun(runId);
      hidePeek(peek);
    }
  }

  async function syncPeek(peek) {
    if (!peek) return;
    const run = await currentRun();
    if (!run) return;
    peek.dataset.runId = run.id || '';
    peek.dataset.terminal = isTerminal(run) ? 'true' : 'false';

    if (!isTerminal(run)) {
      peek.classList.remove('apo-peek-dismissed');
      return;
    }

    if (storedDismissedRun() === run.id) hidePeek(peek);
  }

  function attachPeek(peek) {
    if (!peek || peek.dataset.dismissBehavior === 'true') return;
    peek.dataset.dismissBehavior = 'true';
    let startX = 0;
    let startY = 0;

    peek.addEventListener('click', (event) => {
      if (swipeConsumed) {
        swipeConsumed = false;
        event.preventDefault();
        event.stopImmediatePropagation();
        return;
      }
      if (peek.dataset.terminal !== 'true') return;
      reviewingRunId = peek.dataset.runId || '';
      if (!reviewingRunId) {
        currentRun().then((run) => {
          if (isTerminal(run)) reviewingRunId = run.id || '';
        });
      }
    }, true);

    peek.addEventListener('pointerdown', (event) => {
      startX = event.clientX;
      startY = event.clientY;
    }, { passive: true });

    peek.addEventListener('pointerup', (event) => {
      if (peek.dataset.terminal !== 'true') return;
      const dx = event.clientX - startX;
      const dy = event.clientY - startY;
      if (Math.abs(dx) < 54 || Math.abs(dx) <= Math.abs(dy)) return;
      swipeConsumed = true;
      dismissPeek(peek);
    }, { passive: true });

    syncPeek(peek);
  }

  function attachOverlay(overlay) {
    if (!overlay || overlay.dataset.dismissBehavior === 'true') return;
    overlay.dataset.dismissBehavior = 'true';
    let wasOpen = overlay.classList.contains('open');
    const observer = new MutationObserver(() => {
      const isOpen = overlay.classList.contains('open');
      if (wasOpen && !isOpen && reviewingRunId) {
        const peek = document.getElementById('apo-run-peek');
        const reviewed = reviewingRunId;
        reviewingRunId = '';
        currentRun().then((run) => {
          if (run?.id === reviewed && isTerminal(run)) dismissPeek(peek);
        });
      }
      wasOpen = isOpen;
    });
    observer.observe(overlay, { attributes: true, attributeFilter: ['class'] });
  }

  function scan() {
    const peek = document.getElementById('apo-run-peek');
    const overlay = document.getElementById('apo-run-overlay');
    if (peek) attachPeek(peek);
    if (overlay) attachOverlay(overlay);
    if (peek) {
      window.clearTimeout(syncTimer);
      syncTimer = window.setTimeout(() => syncPeek(peek), 80);
    }
  }

  const observer = new MutationObserver(scan);
  observer.observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
  scan();
})();
