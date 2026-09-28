import {api, setLoading, showToast} from "./common.js?v=0.5.1";

const form = document.querySelector("#template-form");
form.addEventListener("submit", async event => {
  event.preventDefault();
  const start = form.default_start_time.value;
  const end = form.default_end_time.value;
  const error = document.querySelector("#time-error");
  error.textContent = "";
  if (Boolean(start) !== Boolean(end)) { error.textContent = "Укажите и начало, и окончание"; return; }
  if (start && start >= end) { error.textContent = "Окончание должно быть позже начала"; return; }
  if (!form.name.value.trim()) { form.name.focus(); return; }
  const payload = {
    name: form.name.value.trim(), description: form.description.value.trim(), location: form.location.value.trim(),
    default_start_time: start || null, default_end_time: end || null,
    max_participants: Number(form.max_participants.value),
    allow_join_after_start: form.allow_join_after_start.checked,
    show_participant_list: form.show_participant_list.checked,
    participant_instruction: form.participant_instruction.value.trim(),
  };
  const button = event.submitter;
  setLoading(button, true);
  try {
    const id = form.dataset.id;
    await api(id ? `/api/templates/${id}` : "/api/templates", {method: id ? "PUT" : "POST", body:JSON.stringify(payload)});
    showToast(id ? "Шаблон сохранён" : "Шаблон создан");
    location.assign("/templates");
  } catch (value) { showToast(value.message, "error"); setLoading(button, false); }
});
