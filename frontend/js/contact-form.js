"use strict";

import { animateFeedback } from "./reveal.js";

const API_BASE = "";
const COMMENT_MAX = 2000;
const TRACKED_FIELDS = ["name", "email", "phone", "comment"];

export function initContactForm() {
  const form = document.getElementById("contact-form");
  const feedbackEl = document.getElementById("feedback");
  const submitBtn = document.getElementById("submit-btn");
  const submitIcon = document.getElementById("submit-icon");
  const submitText = document.getElementById("submit-text");
  const progressBar = document.getElementById("form-progress-bar");
  const progressEl = document.getElementById("form-progress");
  const commentCounter = document.getElementById("comment-counter");
  const commentField = document.getElementById("comment");

  if (!form || !feedbackEl || !submitBtn) {
    return;
  }

  let turnstileSiteKey = null;
  let captchaToken = null;

  function loadPublicConfig() {
    fetch(`${API_BASE}/api/config/public`)
      .then((res) => res.json())
      .then((cfg) => {
        if (!cfg.turnstile_enabled || !cfg.turnstile_site_key) {
          return;
        }
        turnstileSiteKey = cfg.turnstile_site_key;
        const script = document.createElement("script");
        script.src =
          "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
        script.onload = () => {
          if (typeof turnstile !== "undefined") {
            turnstile.render("#turnstile-container", {
              sitekey: turnstileSiteKey,
              callback: (token) => {
                captchaToken = token;
              },
            });
          }
        };
        document.head.appendChild(script);
      })
      .catch(() => {});
  }

  function updateGroupState(group) {
    const input = group.querySelector(".contact-form__input");
    if (!input) {
      return;
    }
    const filled = input.value.trim().length > 0;
    group.classList.toggle("contact-form__group--filled", filled);
  }

  function updateProgress() {
    const filled = TRACKED_FIELDS.filter((name) => {
      const field = form.elements[name];
      return field && field.value.trim().length > 0;
    }).length;
    const percent = Math.round((filled / TRACKED_FIELDS.length) * 100);

    if (progressBar) {
      progressBar.style.width = `${percent}%`;
    }
    if (progressEl) {
      progressEl.setAttribute("aria-valuenow", String(percent));
    }
  }

  function updateCommentCounter() {
    if (!commentField || !commentCounter) {
      return;
    }
    const len = commentField.value.length;
    commentCounter.textContent = `${len} / ${COMMENT_MAX}`;
    commentCounter.classList.toggle(
      "contact-form__counter--warn",
      len >= COMMENT_MAX * 0.95
    );
  }

  function bindFieldInteractions() {
    form.querySelectorAll(".contact-form__group").forEach((group) => {
      const input = group.querySelector(".contact-form__input");
      if (!input) {
        return;
      }
      const handler = () => {
        updateGroupState(group);
        updateProgress();
        if (input === commentField) {
          updateCommentCounter();
        }
      };
      input.addEventListener("input", handler);
      input.addEventListener("blur", handler);
      handler();
    });
  }

  function clearErrors() {
    form.querySelectorAll(".contact-form__error").forEach((el) => {
      el.textContent = "";
    });
    form.querySelectorAll(".contact-form__input").forEach((input) => {
      input.classList.remove("contact-form__input--error");
      input.removeAttribute("aria-invalid");
    });
    hideFeedback();
  }

  function hideFeedback() {
    feedbackEl.hidden = true;
    feedbackEl.className = "feedback";
    feedbackEl.innerHTML = "";
  }

  async function showFeedback(type, title, detail) {
    feedbackEl.hidden = false;
    feedbackEl.className = `feedback feedback--${type}`;

    let html = `<strong class="feedback__title">${title}</strong>`;
    if (detail) {
      html += `<pre class="feedback__detail">${detail}</pre>`;
    }
    feedbackEl.innerHTML = html;
    await animateFeedback(feedbackEl);
  }

  function showFieldErrors(details) {
    if (!Array.isArray(details)) {
      return;
    }
    details.forEach((item) => {
      const errorEl = form.querySelector(
        `.contact-form__error[data-for="${item.field}"]`
      );
      const inputEl = form.querySelector(`[name="${item.field}"]`);
      if (errorEl) {
        errorEl.textContent = item.message;
      }
      if (inputEl) {
        inputEl.classList.add("contact-form__input--error");
        inputEl.setAttribute("aria-invalid", "true");
      }
    });
  }

  function setLoading(isLoading) {
    submitBtn.disabled = isLoading;
    submitBtn.classList.toggle("contact-form__submit--loading", isLoading);
    if (submitIcon) {
      submitIcon.classList.toggle(
        "contact-form__submit-icon--spin",
        isLoading
      );
    }
    if (submitText) {
      submitText.textContent = isLoading
        ? "Отправка..."
        : "Отправить обращение";
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearErrors();
    setLoading(true);

    const payload = {
      name: form.name.value.trim(),
      email: form.email.value.trim(),
      phone: form.phone.value.trim(),
      comment: form.comment.value.trim(),
      website: form.website.value.trim() || null,
      captcha_token: captchaToken,
    };

    try {
      const res = await fetch(`${API_BASE}/api/contact`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (res.ok) {
        const analysis = data.analysis;
        let detail = "";
        if (analysis) {
          detail = `Тональность: ${analysis.sentiment}\nКатегория: ${analysis.category}\nОтвет: ${analysis.auto_reply}`;
        }
        if (data.email_queued) {
          detail += detail
            ? "\n\nEmail поставлен в очередь."
            : "Email поставлен в очередь.";
        }
        await showFeedback("success", data.message, detail || null);
        form.reset();
        captchaToken = null;
        form.querySelectorAll(".contact-form__group").forEach((group) => {
          group.classList.remove("contact-form__group--filled");
        });
        updateProgress();
        updateCommentCounter();
      } else if (res.status === 422) {
        await showFeedback("error", "Проверьте правильность полей.", null);
        showFieldErrors(data.detail);
      } else if (res.status === 429) {
        await showFeedback("error", data.message, null);
      } else {
        await showFeedback(
          "error",
          data.message || "Неизвестная ошибка",
          data.request_id ? `ID: ${data.request_id}` : null
        );
      }
    } catch {
      await showFeedback("error", "Не удалось связаться с сервером.", null);
    } finally {
      setLoading(false);
    }
  });

  bindFieldInteractions();
  loadPublicConfig();
}
