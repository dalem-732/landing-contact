"use strict";

import { prefersReducedMotion } from "./utils.js";

const STEP_ACTIVE_CLASS = "contact__step--active";
const STEP_INTERVAL_MS = 600;

let motionAnimate = null;

async function loadMotion() {
  if (prefersReducedMotion()) {
    return null;
  }
  try {
    const motion = await import(
      "https://cdn.jsdelivr.net/npm/motion@11.11.17/+esm"
    );
    return motion.animate;
  } catch {
    return null;
  }
}

function getDelay(el) {
  const raw = el.getAttribute("data-reveal-delay");
  return raw ? parseInt(raw, 10) : 0;
}

function revealElement(el, animateFn) {
  if (el.classList.contains("is-visible")) {
    return;
  }

  const delay = getDelay(el) * 0.1;

  if (animateFn) {
    animateFn(
      el,
      { opacity: [0, 1], transform: ["translateY(16px)", "translateY(0)"] },
      { duration: 0.5, delay, easing: "ease-out" }
    );
  }

  el.classList.add("is-visible");
  el.style.setProperty("--reveal-delay", String(getDelay(el)));
}

function animateContactSteps(aside) {
  const steps = aside.querySelectorAll(".contact__step");
  if (!steps.length || prefersReducedMotion()) {
    steps.forEach((step) => step.classList.add(STEP_ACTIVE_CLASS));
    return;
  }

  steps.forEach((step, index) => {
    setTimeout(() => {
      step.classList.add(STEP_ACTIVE_CLASS);
    }, index * STEP_INTERVAL_MS);
  });
}

export async function initReveal() {
  motionAnimate = await loadMotion();

  const elements = document.querySelectorAll("[data-reveal]");
  if (!elements.length) {
    return;
  }

  if (prefersReducedMotion()) {
    elements.forEach((el) => {
      el.classList.add("is-visible");
    });
    const aside = document.getElementById("contact-aside");
    if (aside) {
      animateContactSteps(aside);
    }
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) {
          return;
        }
        revealElement(entry.target, motionAnimate);
        observer.unobserve(entry.target);

        if (entry.target.id === "contact-aside") {
          animateContactSteps(entry.target);
        }
      });
    },
    { threshold: 0.15, rootMargin: "0px 0px -40px 0px" }
  );

  elements.forEach((el) => observer.observe(el));
}

export async function animateFeedback(el) {
  if (!el || prefersReducedMotion()) {
    return;
  }
  if (!motionAnimate) {
    motionAnimate = await loadMotion();
  }
  if (motionAnimate) {
    motionAnimate(
      el,
      { opacity: [0, 1], transform: ["translateY(8px)", "translateY(0)"] },
      { duration: 0.35, easing: "ease-out" }
    );
  }
}
