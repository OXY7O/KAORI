(() => {
  const syncFormSelector = '[data-tls-sync-form]';

  const showSyncProgress = () => {
    const target = document.getElementById('operational-action-feedback');
    if (!target) return;

    target.innerHTML = `
      <div data-quick-action-toast role="status" aria-live="polite" class="quick-action-toast pointer-events-auto w-full">
        <article class="relative isolate overflow-hidden rounded-xl border border-outline-default bg-surface-elevated shadow-xl shadow-black/10">
          <div class="flex items-start gap-3 p-4">
            <span class="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-kaori-soft text-kaori-primary">
              <svg class="h-5 w-5 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle class="opacity-25" cx="12" cy="12" r="9" stroke="currentColor" stroke-width="3"></circle><path class="opacity-90" fill="currentColor" d="M21 12a9 9 0 0 0-9-9v3a6 6 0 0 1 6 6h3Z"></path></svg>
            </span>
            <div class="min-w-0 flex-1 pr-7">
              <p class="text-sm font-semibold text-content-primary">TLS Secret sync request</p>
              <p class="mt-1 text-xs leading-5 text-content-muted">KAORI is queuing TLS certificate collection in the inventory worker.</p>
            </div>
            <button type="button" data-tls-sync-toast-close class="absolute right-3 top-3 z-20 rounded-lg p-1 text-content-muted transition hover:bg-kaori-soft hover:text-kaori-primary" aria-label="Close progress notification">
              <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12" /></svg>
            </button>
          </div>
          <div class="mx-4 mb-4 h-1.5 overflow-hidden rounded-full bg-kaori-soft/70" aria-hidden="true">
            <div class="notification-progress-indeterminate h-full rounded-full bg-kaori-primary"></div>
          </div>
        </article>
      </div>`;
  };

  document.addEventListener('htmx:beforeRequest', (event) => {
    if (event.detail?.elt?.matches?.(syncFormSelector)) showSyncProgress();
  });

  document.addEventListener('click', (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const closeButton = target?.closest('[data-tls-sync-toast-close]');
    if (!closeButton) return;
    closeButton.closest('[data-quick-action-toast]')?.remove();
  });
})();
