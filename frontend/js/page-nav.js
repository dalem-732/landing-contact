"use strict";

import { smoothScrollTo } from "./utils.js";

const NAV_ID = "page-nav";
const HERO_THRESHOLD = 120;

export function initPageNav() {
  const nav = document.getElementById(NAV_ID);
  if (!nav) {
    return;
  }

  const anchorLinks = document.querySelectorAll('a[href^="#"]');

  anchorLinks.forEach((link) => {
    link.addEventListener("click", (event) => {
      const href = link.getAttribute("href");
      if (!href || href === "#") {
        return;
      }
      const target = document.querySelector(href);
      if (!target) {
        return;
      }
      event.preventDefault();
      smoothScrollTo(target);
    });
  });

  function onScroll() {
    const navVisible = window.scrollY > HERO_THRESHOLD;
    if (navVisible) {
      nav.classList.add("page-nav--visible");
    } else {
      nav.classList.remove("page-nav--visible");
    }
    document.documentElement.classList.toggle("page-nav-is-visible", navVisible);
  }

  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
}
