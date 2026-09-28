export async function api(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {"Content-Type": "application/json", ...(options.headers || {})},
  });
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("json") ? await response.json() : null;
  if (!response.ok) {
    const detail = body?.detail;
    const message = Array.isArray(detail) ? detail.map(item => item.msg).join(". ") : detail;
    throw new Error(message || "Не удалось выполнить действие");
  }
  return body;
}

export function showToast(message, type = "success") {
  const region = document.querySelector("#toast-region");
  if (!region) return;
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${type === "error" ? "!" : "✓"}</span><b></b>`;
  toast.querySelector("b").textContent = message;
  region.append(toast);
  window.setTimeout(() => {
    toast.classList.add("out");
    toast.addEventListener("animationend", () => toast.remove(), {once: true});
  }, 2600);
}

const eventLabels = {
  joined: "Новый участник", called: "Участник вызван", acknowledged: "Участник идёт",
  completed: "Обслужен", skipped: "Пропущен", restored: "Возвращён",
  cancelled: "Участник вышел", renamed: "Имя изменено", paused: "Пауза",
  resumed: "Очередь продолжена", finished: "Очередь завершена", created: "Очередь создана",
};
const eventIcons = {joined:"users",called:"radio",acknowledged:"arrow",completed:"check",skipped:"skip",restored:"arrow",cancelled:"x",renamed:"edit",paused:"pause",resumed:"arrow",finished:"stop",created:"plus"};
const escapeText = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));

export function showEventNotification(event) {
  const region = document.querySelector("#toast-region");
  if (!region || !event) return;
  const alert = document.createElement("article");
  alert.className = `organizer-alert kind-${event.kind}`;
  alert.innerHTML = `<span><svg class="icon" aria-hidden="true"><use href="#i-${eventIcons[event.kind] || "bell"}"/></svg></span><div><small>${escapeText(eventLabels[event.kind] || "Событие очереди")}</small><b>${escapeText(event.message)}</b></div>`;
  region.append(alert);
  window.setTimeout(() => { alert.classList.add("out"); alert.addEventListener("animationend", () => alert.remove(), {once:true}); }, 4500);
}

export async function refreshNotifications(markNew = false) {
  const center = document.querySelector("#notification-center");
  if (!center) return [];
  try {
    const data = await api("/api/notifications");
    const events = data.events || [];
    const items = document.querySelector("#notification-items");
    items.innerHTML = "";
    if (!events.length) {
      items.innerHTML = "<p>Событий пока нет</p>";
    } else {
      events.slice(0,12).forEach(event => {
        const row = document.createElement("div");
        row.className = `notification-item kind-${event.kind}`;
        const time = new Date(event.created_at).toLocaleTimeString("ru-RU", {hour:"2-digit", minute:"2-digit"});
        row.innerHTML = `<span><svg class="icon" aria-hidden="true"><use href="#i-${eventIcons[event.kind] || "bell"}"/></svg></span><div><b>${escapeText(event.message)}</b><small>${escapeText(event.queue_name || "Очередь")} · ${time}</small></div>`;
        items.append(row);
      });
    }
    const latest = events[0]?.id || "";
    const lastRead = localStorage.getItem("qm-notifications-read") || "";
    document.querySelector("#notification-dot").hidden = !latest || latest === lastRead || (!markNew && !lastRead);
    if (!lastRead && latest) localStorage.setItem("qm-notifications-read", latest);
    return events;
  } catch {
    document.querySelector("#notification-items").innerHTML = "<p>Не удалось загрузить события</p>";
    return [];
  }
}

export function setLoading(button, loading) {
  button.disabled = loading;
  button.classList.toggle("loading", loading);
}

export function connectQueueSocket(code, onEvent) {
  let socket;
  let retry = 800;
  let stopped = false;
  const status = document.querySelector("#connection-pill");
  const connect = () => {
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${protocol}://${location.host}/ws/queues/${code}`);
    socket.addEventListener("open", () => {
      const wasReconnecting = !status.hidden;
      status.hidden = true;
      retry = 800;
      socket.send("ready");
      if (wasReconnecting) {
        showToast("Соединение восстановлено");
        onEvent({event: "reconnected"});
      }
    });
    socket.addEventListener("message", event => {
      try { onEvent(JSON.parse(event.data)); } catch { onEvent({event: "updated"}); }
    });
    socket.addEventListener("close", () => {
      if (stopped) return;
      status.hidden = false;
      window.setTimeout(connect, retry);
      retry = Math.min(retry * 1.7, 8000);
    });
    socket.addEventListener("error", () => socket.close());
  };
  connect();
  return () => { stopped = true; socket?.close(); };
}

function setupDialog(dialog) {
  if (!dialog) return;
  dialog.querySelectorAll('[value="cancel"], .modal-close').forEach(button => {
    button.addEventListener("click", () => dialog.close());
  });
  dialog.addEventListener("click", event => {
    if (event.target === dialog) dialog.close();
  });
  dialog.addEventListener("keydown", event => {
    if (event.key !== "Tab") return;
    const focusable = [...dialog.querySelectorAll("button:not(:disabled),input:not(:disabled),a[href]")];
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
}

document.querySelectorAll("dialog").forEach(setupDialog);
document.querySelectorAll("[data-toast]").forEach(button => button.addEventListener("click", () => showToast(button.dataset.toast)));
document.addEventListener("click", async event => {
  const button = event.target.closest("[data-copy]");
  if (!button) return;
  try {
    await navigator.clipboard.writeText(button.dataset.copy);
    showToast("Ссылка скопирована");
  } catch { showToast("Не удалось скопировать ссылку", "error"); }
});

const sidebar = document.querySelector("#sidebar");
const sidebarToggle = document.querySelector("#sidebar-toggle");
const backdrop = document.querySelector("#sidebar-backdrop");
function toggleSidebar(force) {
  if (!sidebar) return;
  const open = force ?? !sidebar.classList.contains("open");
  sidebar.classList.toggle("open", open);
  backdrop?.classList.toggle("open", open);
  sidebarToggle?.setAttribute("aria-expanded", String(open));
}
sidebarToggle?.addEventListener("click", () => toggleSidebar());
backdrop?.addEventListener("click", () => toggleSidebar(false));
document.addEventListener("keydown", event => { if (event.key === "Escape") toggleSidebar(false); });

const qrButton = document.querySelector("[data-show-qr]");
qrButton?.addEventListener("click", () => document.querySelector("#qr-modal")?.showModal());

const notificationCenter = document.querySelector("#notification-center");
notificationCenter?.addEventListener("toggle", async () => {
  if (!notificationCenter.open) return;
  const events = await refreshNotifications();
  if (events[0]) localStorage.setItem("qm-notifications-read", events[0].id);
  document.querySelector("#notification-dot").hidden = true;
});
document.querySelector("#notification-read-all")?.addEventListener("click", async () => {
  const events = await refreshNotifications();
  if (events[0]) localStorage.setItem("qm-notifications-read", events[0].id);
  document.querySelector("#notification-dot").hidden = true;
});
if (notificationCenter) refreshNotifications();

const mobileTap = window.matchMedia("(max-width: 760px) and (hover: none)");
document.addEventListener("click", event => {
  if (!mobileTap.matches || event.defaultPrevented || event.button !== 0) return;
  const control = event.target.closest("button, a.button, a.icon-button, a.nav-item, summary.icon-button, .filter, .role-card");
  if (!control || control.disabled) return;
  control.classList.remove("tap-animate");
  void control.offsetWidth;
  control.classList.add("tap-animate");
  control.addEventListener("animationend", () => control.classList.remove("tap-animate"), {once:true});

  if (control instanceof HTMLAnchorElement && control.href && !control.target && !control.hasAttribute("download") && !event.ctrlKey && !event.metaKey && !event.shiftKey) {
    const target = new URL(control.href, location.href);
    if (target.origin === location.origin && target.hash === "") {
      event.preventDefault();
      window.setTimeout(() => location.assign(target.href), 145);
    }
  }
});
