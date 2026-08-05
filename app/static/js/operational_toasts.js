(() => {
  const toastSelector = '[data-operational-toast]';
  const stackSelector = '#operational-toast-stack';
  const maximumVisibleToasts = 4;
  const state = new WeakMap();

  const dismiss = (toast) => {
    if (!(toast instanceof HTMLElement) || toast.dataset.toastDismissing === 'true') return;
    toast.dataset.toastDismissing = 'true';
    const timer = state.get(toast)?.timer;
    if (timer) window.clearTimeout(timer);
    toast.classList.add('opacity-0');
    window.setTimeout(() => toast.remove(), 200);
  };

  const schedule = (toast, duration) => {
    if (!(toast instanceof HTMLElement) || duration <= 0) return;
    const current = state.get(toast) || {};
    if (current.timer) window.clearTimeout(current.timer);
    const startedAt = performance.now();
    const timerBar = toast.querySelector('[data-operational-toast-timer]');
    if (timerBar instanceof HTMLElement) {
      timerBar.style.transition = 'none';
      timerBar.style.width = `${Math.max(0, Math.min(1, current.remaining / duration || 1)) * 100}%`;
      requestAnimationFrame(() => {
        timerBar.style.transition = `width ${current.remaining || duration}ms linear`;
        timerBar.style.width = '0%';
      });
    }
    const remaining = current.remaining || duration;
    current.startedAt = startedAt;
    current.remaining = remaining;
    current.timer = window.setTimeout(() => dismiss(toast), remaining);
    state.set(toast, current);
  };

  const pause = (toast) => {
    const current = state.get(toast);
    if (!current?.timer) return;
    window.clearTimeout(current.timer);
    current.timer = null;
    current.remaining = Math.max(0, current.remaining - (performance.now() - current.startedAt));
    const timerBar = toast.querySelector('[data-operational-toast-timer]');
    if (timerBar instanceof HTMLElement) {
      const width = getComputedStyle(timerBar).width;
      timerBar.style.transition = 'none';
      timerBar.style.width = width;
    }
  };

  const resume = (toast) => {
    const current = state.get(toast);
    if (current?.remaining > 0) schedule(toast, Number(toast.dataset.autoDismissMs || 0));
  };


  const notifyActivityCenter = (element) => {
    if (!(element instanceof HTMLElement) || element.dataset.notificationRefreshDispatched === 'true') return;
    element.dataset.notificationRefreshDispatched = 'true';
    document.body.dispatchEvent(new CustomEvent('kaori:notifications-changed', { bubbles: true }));
    if (!element.matches(toastSelector)) element.remove();
  };

  const enforceStackLimit = () => {
    const stack = document.querySelector(stackSelector);
    if (!stack) return;
    const toasts = Array.from(stack.querySelectorAll(toastSelector));
    toasts.slice(0, Math.max(0, toasts.length - maximumVisibleToasts)).forEach(dismiss);
  };

  const initialiseToast = (toast) => {
    if (!(toast instanceof HTMLElement) || toast.dataset.toastInitialised === 'true') return;
    toast.dataset.toastInitialised = 'true';

    const id = toast.dataset.toastId;
    if (id) {
      document.querySelectorAll(`${toastSelector}[data-toast-id="${CSS.escape(id)}"]`).forEach((candidate) => {
        if (candidate !== toast) candidate.remove();
      });
    }

    toast.addEventListener('mouseenter', () => pause(toast));
    toast.addEventListener('mouseleave', () => resume(toast));
    toast.addEventListener('focusin', () => pause(toast));
    toast.addEventListener('focusout', () => resume(toast));

    requestAnimationFrame(() => {
      toast.classList.remove('opacity-0');
    });

    const duration = Number(toast.dataset.autoDismissMs || 0);
    if (duration > 0) {
      state.set(toast, { remaining: duration, timer: null, startedAt: 0 });
      schedule(toast, duration);
    }
    if (toast.matches('[data-operational-notification-refresh]')) notifyActivityCenter(toast);
    enforceStackLimit();
    window.renderKaoriIcons?.();
  };

  const initialise = (root = document) => {
    if (root.matches?.(toastSelector)) initialiseToast(root);
    root.querySelectorAll?.(toastSelector).forEach(initialiseToast);
    if (root.matches?.('[data-operational-notification-refresh]:not([data-operational-toast])')) {
      notifyActivityCenter(root);
    }
    root.querySelectorAll?.('[data-operational-notification-refresh]:not([data-operational-toast])').forEach(
      notifyActivityCenter,
    );
  };

  document.addEventListener('click', (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const close = target?.closest('[data-operational-toast-close]');
    if (!close) return;
    event.preventDefault();
    dismiss(close.closest(toastSelector));
  });

  document.addEventListener('htmx:load', (event) => initialise(event.detail?.elt || document));
  document.addEventListener('htmx:oobAfterSwap', (event) => initialise(event.detail?.target || document));

  window.dismissOperationalToast = (element) => dismiss(element?.closest?.(toastSelector) || element);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initialise());
  } else {
    initialise();
  }
})();
