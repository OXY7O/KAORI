(() => {
  const selector = '[data-secret-reveal-value]';

  const initialiseCard = (card) => {
    if (!(card instanceof HTMLElement) || card.dataset.countdownStarted === 'true') return;
    card.dataset.countdownStarted = 'true';

    let remaining = Number.parseInt(card.dataset.secretRevealExpires || '0', 10);
    const counter = card.querySelector('[data-secret-countdown]');
    if (!Number.isFinite(remaining) || remaining <= 0) return;

    const interval = window.setInterval(() => {
      remaining -= 1;
      if (counter) counter.textContent = String(Math.max(remaining, 0));
      if (remaining > 0) return;

      window.clearInterval(interval);
      card.innerHTML = '<div class="flex items-center gap-3 p-5 text-sm text-content-secondary"><i data-lucide="eye-off" class="h-5 w-5"></i><span>The one-time Secret value has been removed from the page.</span></div>';
      window.renderKaoriIcons?.();
      if (!window.renderKaoriIcons && window.lucide) window.lucide.createIcons();
    }, 1000);
  };

  const initialise = (root = document) => {
    if (root.matches?.(selector)) initialiseCard(root);
    root.querySelectorAll?.(selector).forEach(initialiseCard);
  };

  document.addEventListener('htmx:load', (event) => initialise(event.detail?.elt || document));
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initialise());
  } else {
    initialise();
  }
})();
