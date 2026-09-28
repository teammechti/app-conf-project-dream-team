import {api, connectQueueSocket, refreshNotifications, setLoading, showEventNotification, showToast} from "./common.js?v=0.5.1";

const root = document.querySelector(".manage-main");
const token = root.dataset.token;
const code = root.dataset.code;
let state = JSON.parse(document.querySelector("#initial-state").textContent);
const list = document.querySelector("#participant-list");
const nextButton = document.querySelector("#next-button");
const skipButton = document.querySelector("#skip-button");
const pauseButton = document.querySelector("#pause-button");
const seenEventIds = new Set((state.recent_events || []).map(event => event.id));
let notificationPreferences = {notify_new_participant:true, notify_queue_finished:true, notify_queue_changes:false};
api("/api/settings").then(value => { notificationPreferences = value; }).catch(() => {});

const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
function icon(name) { return `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`; }

function render() {
  document.querySelector("#called-number").textContent = state.called?.number || "—";
  document.querySelector("#called-name").textContent = state.called?.name || "Никто не вызван";
  document.querySelector("#called-note").textContent = state.called?.acknowledged_at ? "Участник подтвердил, что идёт" : state.called ? "Ожидаем подтверждения участника" : "Вызовите первого участника";
  skipButton.disabled = !state.called || state.status !== "active";
  nextButton.disabled = state.status !== "active" || (!state.called && !state.participants.some(p => p.status === "waiting"));
  pauseButton.querySelector("span").textContent = state.status === "paused" ? "Продолжить" : "Пауза";
  const status = document.querySelector("#manage-status");
  status.className = `status-badge ${state.status}`;
  status.querySelector("b").textContent = state.status === "paused" ? "Очередь на паузе" : "Очередь активна";
  document.querySelector("#aside-status").textContent = state.status === "paused" ? "Пауза" : "Активна";
  document.querySelector("#waiting-count").textContent = state.counts.waiting;
  document.querySelector("#stat-waiting").textContent = state.counts.waiting;
  document.querySelector("#stat-completed").textContent = state.counts.completed;
  document.querySelector("#stat-average").textContent = state.average_wait_seconds ? Math.round(state.average_wait_seconds/60) : "—";
  const rows = state.participants.filter(p => ["waiting","skipped"].includes(p.status));
  list.innerHTML = rows.map(p => `<div class="participant-row ${p.status}" data-id="${p.id}"><b>${esc(p.number)}</b><span class="participant-name"><b>${esc(p.name)}</b><small>Участник очереди</small></span><span class="row-status">${p.status === "skipped" ? "Пропущен" : "Ожидает"}</span><time>${new Date(p.joined_at).toLocaleTimeString("ru",{hour:"2-digit",minute:"2-digit"})}</time><span class="row-actions"><button class="icon-button call-row" type="button" title="Вызвать">${icon("arrow")}</button><details class="row-menu"><summary class="icon-button">${icon("dots")}</summary><div><button type="button" data-row-action="${p.status === "skipped" ? "restore" : "skip"}">${p.status === "skipped" ? "Вернуть в очередь" : "Пропустить"}</button><button type="button" data-row-action="call">Вызвать сейчас</button></div></details></span></div>`).join("");
  document.querySelector("#participant-empty").hidden = rows.length !== 0;
  const events = document.querySelector("#event-list");
  events.innerHTML = (state.recent_events || []).slice(0,8).map(event => `<article class="event-row kind-${event.kind}"><span>${icon(event.kind === "joined" ? "users" : event.kind === "called" ? "radio" : event.kind === "acknowledged" ? "arrow" : event.kind === "completed" ? "check" : event.kind === "skipped" ? "skip" : event.kind === "paused" ? "pause" : event.kind === "finished" ? "stop" : "info")}</span><div><b>${esc(event.message)}</b><time>${new Date(event.created_at).toLocaleTimeString("ru-RU",{hour:"2-digit",minute:"2-digit"})}</time></div></article>`).join("") || '<p class="empty-inline">Событий пока нет</p>';
}

function consumeEvents(nextState, notify = true) {
  const fresh = (nextState.recent_events || []).filter(event => !seenEventIds.has(event.id));
  (nextState.recent_events || []).forEach(event => seenEventIds.add(event.id));
  const enabled = event => event.kind === "joined" ? notificationPreferences.notify_new_participant : event.kind === "finished" ? notificationPreferences.notify_queue_finished : ["paused","resumed"].includes(event.kind) ? notificationPreferences.notify_queue_changes : true;
  const visible = fresh.filter(enabled);
  if (notify) visible.slice().reverse().forEach(showEventNotification);
  if (fresh.length) refreshNotifications(true);
  return visible.length;
}

async function act(path, message, button) {
  if (button) setLoading(button, true);
  try {
    const nextState = await api(`/api/manage/${token}/${path}`, {method: "POST"});
    const shown = consumeEvents(nextState); state = nextState;
    render(); if (!shown) showToast(message);
  } catch (error) { showToast(error.message,"error"); }
  finally { if (button) setLoading(button, false); }
}

nextButton.addEventListener("click", () => act("next","Вызван следующий участник",nextButton));
skipButton.addEventListener("click", () => act("skip","Участник пропущен",skipButton));
pauseButton.addEventListener("click", () => act(state.status === "paused" ? "resume" : "pause", state.status === "paused" ? "Очередь продолжена" : "Очередь приостановлена", pauseButton));
list.addEventListener("click", event => {
  const row = event.target.closest(".participant-row");
  if (!row) return;
  if (event.target.closest(".call-row")) act(`call/${row.dataset.id}`,"Участник вызван",event.target.closest("button"));
  const action = event.target.closest("[data-row-action]")?.dataset.rowAction;
  if (action) act(`${action}/${row.dataset.id}`, action === "restore" ? "Участник возвращён в очередь" : action === "skip" ? "Участник пропущен" : "Участник вызван");
});

const finishModal = document.querySelector("#finish-modal");
document.querySelector("#finish-button").addEventListener("click", () => finishModal.showModal());
document.querySelector("#confirm-finish").addEventListener("click", async event => {
  event.preventDefault(); setLoading(event.currentTarget,true);
  try { await api(`/api/manage/${token}/finish`,{method:"POST"}); showToast("Очередь завершена"); location.reload(); }
  catch(error) { showToast(error.message,"error"); setLoading(event.currentTarget,false); }
});

connectQueueSocket(code, async () => {
  try { const nextState = await api(`/api/manage/${token}`); consumeEvents(nextState); state = nextState; render(); }
  catch (error) { showToast(error.message,"error"); }
});
render();
