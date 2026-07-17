"use strict";

export function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function smoothScrollTo(target) {
  const el = typeof target === "string" ? document.querySelector(target) : target;
  if (!el) {
    return;
  }
  el.scrollIntoView({
    behavior: prefersReducedMotion() ? "auto" : "smooth",
    block: "start",
  });
}
