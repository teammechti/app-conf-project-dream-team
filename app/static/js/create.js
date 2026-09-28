import {api, setLoading, showToast} from "./common.js?v=0.5.1";

const form = document.querySelector("#create-form");
const preview = document.querySelector("#preview-card");
const mobileSlot = document.querySelector("#mobile-preview-slot");
const aiModal = document.querySelector("#ai-modal");
let applyingAI = false;
let aiDraft = null;

if (mobileSlot && preview) {
  const clone = preview.cloneNode(true);
  clone.removeAttribute("id");
  mobileSlot.append(clone);
}

const today = new Date();
const isoToday = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,"0")}-${String(today.getDate()).padStart(2,"0")}`;
form.date.min = isoToday;

function fieldValue(name) { return form.elements[name]?.value.trim() || ""; }
function formatDate(value) {
  if (!value) return "Не указано";
  const [year, month, day] = value.split("-");
  return `${day}.${month}.${year}`;
}
function updatePreview() {
  const values = {
    name: fieldValue("name") || "Название вашей очереди",
    description: fieldValue("description") || "Описание появится здесь.",
    location: fieldValue("location") || "Не указано",
    date: formatDate(fieldValue("date")),
    start_time: fieldValue("start_time") || "—",
    end_time: fieldValue("end_time") || "—",
  };
  for (const [key, value] of Object.entries(values)) {
    document.querySelectorAll(`[data-preview="${key}"]`).forEach(node => node.textContent = value);
  }
  document.querySelectorAll(".counter").forEach(counter => {
    const input = counter.parentElement.querySelector("input,textarea");
    counter.querySelector("b").textContent = input?.value.length || 0;
  });
}
form.addEventListener("input", event => {
  if (!applyingAI && event.target.matches("input,textarea")) event.target.dataset.userTouched = "true";
  updatePreview();
});
updatePreview();

const aiFields = {
  name: "Название", description: "Описание", location: "Место", date: "Дата",
  start_time: "Начало", end_time: "Окончание", max_participants: "Максимум участников",
  participant_instruction: "Инструкция",
};
const dateLabel = value => value ? new Intl.DateTimeFormat("ru-RU", {day:"numeric",month:"long",year:"numeric"}).format(new Date(`${value}T12:00:00`)) : "";

async function checkAIStatus() {
  try {
    const status = await api("/api/ai/status");
    const message = document.querySelector("#ai-availability");
    message.hidden = status.available;
    document.querySelector("#ai-open-button").title = status.available ? "Qwen заполнит черновик формы" : "Для AI укажите LLM_API_KEY и QWEN_BASE_URL";
  } catch { /* Main form remains available even when status check fails. */ }
}

document.querySelector("#ai-open-button").addEventListener("click", () => {
  document.querySelector("#ai-input-step").hidden = false;
  document.querySelector("#ai-review-step").hidden = true;
  document.querySelector("#ai-error").textContent = "";
  aiModal.showModal();
  checkAIStatus();
  window.setTimeout(() => document.querySelector("#ai-description").focus(), 30);
});

document.querySelector("#ai-description-form").addEventListener("submit", async event => {
  event.preventDefault();
  const text = document.querySelector("#ai-description").value.trim();
  const error = document.querySelector("#ai-error");
  const button = document.querySelector("#ai-analyze-button");
  if (text.length < 3) { error.textContent = "Опишите очередь хотя бы несколькими словами"; return; }
  error.textContent = "";
  const original = button.innerHTML;
  button.disabled = true; button.innerHTML = '<i class="inline-spinner"></i> Анализирую описание…';
  try {
    aiDraft = await api("/api/ai/parse-queue-description", {method:"POST", body:JSON.stringify({text})});
    const entries = Object.entries(aiDraft).filter(([,value]) => value !== null && value !== "");
    const review = document.querySelector("#ai-review-list");
    review.innerHTML = entries.map(([key,value]) => {
      const control = form.elements[key];
      const conflict = control?.dataset.userTouched === "true" && control.value && String(control.value) !== String(value);
      let shown = key === "date" ? dateLabel(value) : key === "start_time" || key === "end_time" ? String(value).slice(0,5) : value;
      return `<div><dt>${aiFields[key]}</dt><dd>${String(shown).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}${conflict ? '<small>Сохранится ваше значение</small>' : ''}</dd></div>`;
    }).join("") || "<div><dd>Qwen не нашёл параметров — уточните описание.</dd></div>";
    document.querySelector("#ai-input-step").hidden = true;
    document.querySelector("#ai-review-step").hidden = false;
  } catch (value) { error.textContent = value.message || "Не удалось обработать описание. Заполните поля вручную или попробуйте ещё раз."; }
  finally { button.disabled = false; button.innerHTML = original; }
});

document.querySelector("#ai-back-button").addEventListener("click", () => {
  document.querySelector("#ai-review-step").hidden = true;
  document.querySelector("#ai-input-step").hidden = false;
});
document.querySelector("#ai-apply-button").addEventListener("click", () => {
  applyingAI = true;
  for (const [key,value] of Object.entries(aiDraft || {})) {
    if (value === null || value === "") continue;
    const control = form.elements[key];
    if (!control || (control.dataset.userTouched === "true" && control.value)) continue;
    control.value = key === "start_time" || key === "end_time" ? String(value).slice(0,5) : value;
    control.classList.remove("ai-filled"); void control.offsetWidth; control.classList.add("ai-filled");
    control.dispatchEvent(new Event("input", {bubbles:true}));
  }
  applyingAI = false;
  updatePreview(); aiModal.close(); showToast("Поля формы заполнены с помощью AI");
});

function setError(control, message = "") {
  control.classList.toggle("invalid", Boolean(message));
  const container = control.closest(".field-control") || control.parentElement;
  const error = container.querySelector(".field-error");
  if (error) error.textContent = message;
}

function validate() {
  form.querySelectorAll("input,textarea").forEach(input => setError(input));
  let valid = true;
  [[form.name,"Укажите название очереди"]].forEach(([control,message]) => {
    if (!control.value) { setError(control,message); valid = false; }
  });
  if (form.name.value && form.name.value.trim().length < 2) { setError(form.name,"Минимум 2 символа"); valid = false; }
  if (form.location.value && form.location.value.trim().length < 2) { setError(form.location,"Минимум 2 символа"); valid = false; }
  if (form.start_time.value && form.end_time.value && form.start_time.value >= form.end_time.value) { setError(form.end_time,"Окончание должно быть позже начала"); valid = false; }
  if (Number(form.max_participants.value) <= 0) { setError(form.max_participants,"Введите число больше нуля"); valid = false; }
  return valid;
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  const submit = event.submitter || form.querySelector(".create-submit");
  if (!validate()) { form.querySelector(".invalid")?.focus(); return; }
  const payload = {
    name: fieldValue("name"), description: fieldValue("description"), location: fieldValue("location") || null,
    date: fieldValue("date") || null, start_time: fieldValue("start_time") || null, end_time: fieldValue("end_time") || null,
    max_participants: Number(form.max_participants.value),
    allow_join_after_start: form.allow_join_after_start.checked,
    show_participant_list: form.show_participant_list.checked,
    participant_instruction: fieldValue("participant_instruction"),
  };
  setLoading(submit, true);
  try {
    const templateId = form.dataset.templateId;
    const endpoint = templateId ? `/api/queues?template_id=${encodeURIComponent(templateId)}` : "/api/queues";
    const created = await api(endpoint, {method: "POST", body: JSON.stringify(payload)});
    showToast("Очередь создана");
    location.assign(created.created_url);
  } catch (error) {
    showToast(error.message, "error");
    setLoading(submit, false);
  }
});
