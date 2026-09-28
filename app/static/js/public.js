import {api, connectQueueSocket, setLoading, showToast} from "./common.js?v=0.5.1";

const root = document.querySelector(".public-main");
const code = root.dataset.code;
const storageKey = `qm-participant:${code}`;
let token = localStorage.getItem(storageKey);
let queueState = JSON.parse(document.querySelector("#initial-state").textContent);
let participantState = null;
const joinView = document.querySelector("#join-view");
const waitingView = document.querySelector("#waiting-view");
const joinForm = document.querySelector("#join-form");
const overlay = document.querySelector("#call-overlay");
const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));

function pluralPeople(count) {
  const mod10 = count % 10, mod100 = count % 100;
  const word = mod10 === 1 && mod100 !== 11 ? "человек" : "человека";
  return `${count} ${word}`;
}
function formatWait(seconds) { return seconds ? `~ ${Math.max(1,Math.round(seconds/60))} мин` : "меньше минуты"; }

function renderPublicQueue(state) {
  queueState = state;
  document.querySelector("#join-count").textContent = `${state.counts.waiting + state.counts.called} участников`;
  document.querySelector("#public-called-number").textContent = state.called?.number || "—";
  document.querySelector("#public-called-name").textContent = state.called?.name || "Ожидаем первого участника";
  document.querySelector("#public-preview-list").innerHTML = state.participants.slice(0,3).map(p => `<div><b>${esc(p.number)}</b><span>${esc(p.name)}</span><em class="status-badge ${p.status}">${p.status === "called" ? "Вызывается" : "Ожидает"}</em></div>`).join("");
}

function renderParticipant(data) {
  participantState = data;
  queueState = data.queue;
  const p = data.participant;
  if (["cancelled","completed"].includes(p.status)) {
    localStorage.removeItem(storageKey); token = null; participantState = null;
    waitingView.hidden = true; joinView.hidden = false;
    showToast(p.status === "completed" ? "Спасибо! Вы обслужены" : "Вы вышли из очереди");
    return;
  }
  joinView.hidden = true; waitingView.hidden = false;
  document.querySelector("#ticket-number").textContent = p.number;
  document.querySelector("#ticket-name").textContent = p.name;
  document.querySelector("#people-ahead").textContent = pluralPeople(data.people_ahead);
  document.querySelector("#waiting-called").textContent = data.queue.called ? `${data.queue.called.number} — ${data.queue.called.name}` : "Пока никто";
  document.querySelector("#estimate").textContent = formatWait(data.estimated_wait_seconds);
  document.querySelector("#nearby-count").textContent = Math.min(data.queue.participants.length,3);
  const nearby = data.queue.participants.filter(item => ["waiting","called"].includes(item.status)).slice(0,5);
  document.querySelector("#nearby-list").innerHTML = nearby.map(item => `<div class="${item.id === p.id ? "me" : ""}"><b>${esc(item.number)}</b><span>${esc(item.name)}</span><small>${item.id === p.id ? "Вы" : item.status === "called" ? "Вызывается" : "Ожидает"}</small></div>`).join("");
  const ordered = data.queue.participants.filter(item => ["waiting","called"].includes(item.status));
  let index = ordered.findIndex(item => item.id === p.id);
  const start = Math.max(0,index-3); const items = ordered.slice(start,start+6);
  document.querySelector("#progress-line").innerHTML = items.map(item => `<span class="progress-item ${item.id === p.id ? "me" : item.queue_order < p.queue_order ? "done" : ""}"><b>${esc(item.number)}</b><small>${item.id === p.id ? "Вы" : item.status === "called" ? "Вызывается" : "Ожидает"}</small></span>`).join("") + `<span class="progress-item"><b>…</b><small>Далее</small></span>`;
  if (p.status === "called" && !p.acknowledged_at && sessionStorage.getItem(`qm-ack:${p.id}`) !== "yes") {
    document.querySelector("#call-number").textContent = p.number;
    document.querySelector("#call-name").textContent = p.name;
    overlay.hidden = false;
  } else overlay.hidden = true;
  if (data.queue.status === "paused") showToast("Очередь временно приостановлена", "error");
}

async function refresh() {
  const queue = await api(`/api/queues/${code}`);
  renderPublicQueue(queue);
  if (token) {
    try { renderParticipant(await api(`/api/participants/${token}`)); }
    catch { localStorage.removeItem(storageKey); token = null; joinView.hidden = false; waitingView.hidden = true; }
  }
}

joinForm?.addEventListener("submit", async event => {
  event.preventDefault();
  const input = joinForm.elements.name;
  const error = document.querySelector("#join-error");
  error.textContent = "";
  if (input.value.trim().length < 2) { error.textContent = "Введите имя — минимум 2 символа"; input.focus(); return; }
  const button = joinForm.querySelector("button"); setLoading(button,true);
  try {
    const created = await api(`/api/queues/${code}/join`,{method:"POST",body:JSON.stringify({name:input.value.trim()})});
    token = created.token; localStorage.setItem(storageKey,token); showToast("Вы в очереди"); await refresh();
  } catch(errorValue) { error.textContent = errorValue.message; setLoading(button,false); }
});

const renameModal = document.querySelector("#rename-modal");
document.querySelector("#rename-button").addEventListener("click", () => { renameModal.querySelector("input").value = participantState.participant.name; renameModal.showModal(); });
renameModal.querySelector("form").addEventListener("submit", async event => {
  event.preventDefault(); const input = event.currentTarget.elements.name; const button = event.currentTarget.querySelector("button[type=submit]");
  if (input.value.trim().length < 2) { event.currentTarget.querySelector(".field-error").textContent = "Минимум 2 символа"; return; }
  setLoading(button,true);
  try { renderParticipant(await api(`/api/participants/${token}`,{method:"PATCH",body:JSON.stringify({name:input.value.trim()})})); renameModal.close(); showToast("Имя изменено"); }
  catch(error) { showToast(error.message,"error"); } finally { setLoading(button,false); }
});

const leaveModal = document.querySelector("#leave-modal");
document.querySelector("#leave-button").addEventListener("click", () => leaveModal.showModal());
document.querySelector("#called-leave-button").addEventListener("click", () => { overlay.hidden = true; leaveModal.showModal(); });
document.querySelector("#confirm-leave").addEventListener("click", async event => {
  setLoading(event.currentTarget,true);
  try { await api(`/api/participants/${token}`,{method:"DELETE"}); localStorage.removeItem(storageKey); location.reload(); }
  catch(error) { showToast(error.message,"error"); setLoading(event.currentTarget,false); }
});
document.querySelector("#going-button").addEventListener("click", async event => {
  const button = event.currentTarget;
  setLoading(button, true);
  try {
    const nextState = await api(`/api/participants/${token}/acknowledge`, {method:"POST"});
    sessionStorage.setItem(`qm-ack:${participantState.participant.id}`,"yes");
    renderParticipant(nextState);
    overlay.hidden = true;
    showToast("Организатор получил подтверждение");
  } catch (error) { showToast(error.message, "error"); }
  finally { setLoading(button, false); }
});

connectQueueSocket(code, async () => { if (document.querySelector("#auto-update")?.checked !== false) await refresh(); });
renderPublicQueue(queueState);
if (token) refresh();
