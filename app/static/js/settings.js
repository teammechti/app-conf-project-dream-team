import {api, setLoading, showToast} from "./common.js?v=0.5.1";

const form = document.querySelector("#settings-form");
form.addEventListener("submit", async event => {
  event.preventDefault();
  const submit = event.submitter || document.querySelector('[form="settings-form"]');
  const payload = {
    organizer_name: form.organizer_name.value.trim(), timezone: form.timezone.value,
    notify_new_participant: form.notify_new_participant.checked,
    notify_queue_finished: form.notify_queue_finished.checked,
    notify_queue_changes: form.notify_queue_changes.checked,
    default_max_participants: Number(form.default_max_participants.value),
    default_show_participant_list: form.default_show_participant_list.checked,
    default_allow_join_after_start: form.default_allow_join_after_start.checked,
  };
  setLoading(submit, true);
  try { await api("/api/settings", {method:"PUT", body:JSON.stringify(payload)}); showToast("Настройки сохранены"); }
  catch (error) { showToast(error.message, "error"); }
  finally { setLoading(submit, false); }
});

const passwordForm = document.querySelector("#password-form");
document.querySelector("#change-password-button").addEventListener("click", async event => {
  const error = passwordForm.querySelector(".field-error");
  const button = event.currentTarget;
  error.textContent = "";
  if (!passwordForm.current_password.value || !passwordForm.new_password.value) {
    error.textContent = "Заполните текущий и новый пароль";
    return;
  }
  if (passwordForm.new_password.value !== passwordForm.new_password_confirm.value) {
    error.textContent = "Новые пароли не совпадают";
    return;
  }
  setLoading(button, true);
  try {
    await api("/api/auth/change-password", {method:"POST", body:JSON.stringify({current_password: passwordForm.current_password.value, new_password: passwordForm.new_password.value})});
    passwordForm.querySelectorAll("input").forEach(input => { input.value = ""; });
    showToast("Пароль изменён");
  } catch (errorValue) { error.textContent = errorValue.message; }
  finally { setLoading(button, false); }
});

document.querySelector("#logout-button").addEventListener("click", async event => {
  const button = event.currentTarget;
  setLoading(button, true);
  try {
    const result = await api("/api/auth/logout", {method:"POST"});
    location.assign(result.redirect_url);
  } catch (error) {
    showToast(error.message, "error");
    setLoading(button, false);
  }
});
