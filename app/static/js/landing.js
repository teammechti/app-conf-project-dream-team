import {api, setLoading} from "./common.js?v=0.5.1";

const organizerModal = document.querySelector("#organizer-modal");
const participantModal = document.querySelector("#participant-modal");
const organizerRole = document.querySelector("#organizer-role");

organizerRole.addEventListener("click", () => {
  if (document.body.classList.contains("authenticated")) { location.assign("/organizer"); return; }
  organizerModal.showModal();
  window.setTimeout(() => document.querySelector("#login-email").focus(), 40);
});
document.querySelector("#participant-role").addEventListener("click", () => {
  participantModal.showModal();
  window.setTimeout(() => document.querySelector("#queue-link").focus(), 40);
});

document.querySelectorAll("[data-auth-tab]").forEach(tab => tab.addEventListener("click", () => {
  const selected = tab.dataset.authTab;
  document.querySelectorAll("[data-auth-tab]").forEach(item => item.classList.toggle("active", item === tab));
  document.querySelectorAll("[data-auth-panel]").forEach(panel => { panel.hidden = panel.dataset.authPanel !== selected; });
  document.querySelector(`[data-auth-panel="${selected}"] input`)?.focus();
}));

async function submitAuth(form, endpoint, payload) {
  const error = form.querySelector(".field-error");
  const button = form.querySelector("button[type=submit]");
  error.textContent = "";
  setLoading(button, true);
  try {
    const result = await api(endpoint, {method:"POST", body:JSON.stringify(payload)});
    location.assign(result.dashboard_url);
  } catch (value) {
    error.textContent = value.message;
    setLoading(button, false);
  }
}

document.querySelector("#organizer-login-form").addEventListener("submit", event => {
  event.preventDefault();
  const form = event.currentTarget;
  submitAuth(form, "/api/auth/login", {email: form.email.value.trim(), password: form.password.value});
});

document.querySelector("#organizer-register-form").addEventListener("submit", event => {
  event.preventDefault();
  const form = event.currentTarget;
  const error = form.querySelector(".field-error");
  error.textContent = "";
  if (form.password.value !== form.password_confirm.value) { error.textContent = "Пароли не совпадают"; return; }
  submitAuth(form, "/api/auth/register", {
    name: form.name.value.trim(), email: form.email.value.trim(), password: form.password.value,
    accept_terms: form.accept_terms.checked,
  });
});

document.querySelector("#participant-entry-form").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const raw = form.elements.queue.value.trim();
  const error = form.querySelector(".field-error");
  error.textContent = "";
  let code = "";
  try {
    const parsed = new URL(raw, location.origin);
    const match = parsed.pathname.match(/^\/q\/([^/?#]+)\/?$/);
    if (match) code = decodeURIComponent(match[1]);
  } catch { /* A short code is handled below. */ }
  if (!code && /^[a-zA-Z0-9_-]{3,40}$/.test(raw)) code = raw;
  if (!code) { error.textContent = "Вставьте ссылку вида /q/… или код очереди"; return; }
  const button = form.querySelector("button[type=submit]");
  setLoading(button, true);
  try { await api(`/api/queues/${encodeURIComponent(code)}`); location.assign(`/q/${encodeURIComponent(code)}`); }
  catch { error.textContent = "Очередь по этой ссылке не найдена"; setLoading(button, false); }
});
