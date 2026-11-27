"use strict";

const API_BASE = "";
const REFRESH_MS = 30_000;
const STATUS_EVENT = "live-status:update";

const LABELS = {
  ok: "Сервис работает",
  degraded: "Частичная деградация",
  offline: "Недоступен",
};

function statusClass(status) {
  if (status === "ok") {
    return "ok";
  }
  if (status === "error") {
    return "error";
  }
  return "warn";
}

function updateFooterBadge(overallStatus) {
  const badge = document.getElementById("footer-health-badge");
  if (!badge) {
    return;
  }

  if (overallStatus === "offline") {
    badge.hidden = false;
    badge.textContent = "offline";
    badge.className = "site-footer__badge site-footer__badge--error";
    return;
  }

  badge.hidden = false;
  badge.textContent = overallStatus;
  badge.className = `site-footer__badge site-footer__badge--${statusClass(overallStatus)}`;
}

function dispatchStatus(status) {
  window.dispatchEvent(
    new CustomEvent(STATUS_EVENT, { detail: { status } })
  );
}

function setDot(dotEl, status) {
  dotEl.className = `live-status__dot live-status__dot--${statusClass(status)}`;
}

function initLiveStatusVisibility(rootEl) {
  const contactSection = document.getElementById("contact");
  if (!contactSection) {
    return;
  }

  const observer = new IntersectionObserver(
    ([entry]) => {
      const hidden = entry.isIntersecting;
      rootEl.classList.toggle("live-status-panel--hidden", hidden);
      rootEl.setAttribute("aria-hidden", hidden ? "true" : "false");
    },
    { threshold: 0, rootMargin: "0px 0px -15% 0px" }
  );

  observer.observe(contactSection);

  window.addEventListener(
    "pagehide",
    () => observer.disconnect(),
    { once: true }
  );
}

const MOBILE_MQ = window.matchMedia("(max-width: 47.9875rem)");

function initLiveStatusMobileToggle(rootEl, toggleBtn) {
  function applyMode() {
    const mobile = MOBILE_MQ.matches;
    if (mobile) {
      rootEl.classList.add("live-status-panel--collapsed");
      rootEl.classList.remove("live-status-panel--expanded");
      toggleBtn.setAttribute("aria-expanded", "false");
    } else {
      rootEl.classList.remove("live-status-panel--collapsed", "live-status-panel--expanded");
      toggleBtn.setAttribute("aria-expanded", "true");
    }
  }

  function toggleExpanded() {
    if (!MOBILE_MQ.matches) {
      return;
    }
    const expanded = rootEl.classList.toggle("live-status-panel--expanded");
    rootEl.classList.toggle("live-status-panel--collapsed", !expanded);
    toggleBtn.setAttribute("aria-expanded", String(expanded));
  }

  toggleBtn.addEventListener("click", () => {
    toggleExpanded();
    toggleBtn.blur();
  });
  MOBILE_MQ.addEventListener("change", applyMode);
  applyMode();

  window.addEventListener(
    "pagehide",
    () => MOBILE_MQ.removeEventListener("change", applyMode),
    { once: true }
  );
}

export function initLiveStatus() {
  const rootEl = document.getElementById("live-status");
  const toggleBtn = document.getElementById("live-status-toggle");
  const dotEl = document.getElementById("live-status-dot");
  const labelEl = document.getElementById("live-status-label");

  if (!rootEl || !toggleBtn || !dotEl || !labelEl) {
    return;
  }

  initLiveStatusVisibility(rootEl);
  initLiveStatusMobileToggle(rootEl, toggleBtn);

  async function refresh() {
    let overall = "offline";

    try {
      const healthRes = await fetch(`${API_BASE}/api/health`);
      if (healthRes.ok) {
        const health = await healthRes.json();
        overall = health.status || "degraded";
        labelEl.textContent = LABELS[overall] || overall;
        setDot(dotEl, overall);
      } else {
        labelEl.textContent = LABELS.offline;
        setDot(dotEl, "error");
        overall = "offline";
      }
    } catch {
      labelEl.textContent = LABELS.offline;
      setDot(dotEl, "error");
      overall = "offline";
    }

    updateFooterBadge(overall);
    dispatchStatus(overall);
  }

  refresh();
  const intervalId = setInterval(refresh, REFRESH_MS);

  window.addEventListener("pagehide", () => clearInterval(intervalId), {
    once: true,
  });
}
