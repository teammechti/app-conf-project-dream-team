import {api, showToast} from "./common.js?v=0.5.1";

const cards = [...document.querySelectorAll(".template-card")];
const search = document.querySelector("#template-search");
search?.addEventListener("input", () => {
  const query = search.value.trim().toLowerCase();
  let visible = 0;
  cards.forEach(card => {
    card.hidden = Boolean(query) && !card.dataset.name.includes(query);
    if (!card.hidden) visible += 1;
  });
  const empty = document.querySelector("#template-no-results");
  if (empty) empty.hidden = visible !== 0;
});

document.addEventListener("click", async event => {
  const duplicate = event.target.closest("[data-template-duplicate]");
  if (duplicate) {
    duplicate.disabled = true;
    try {
      await api(`/api/templates/${duplicate.dataset.templateDuplicate}/duplicate`, {method:"POST"});
      showToast("Шаблон продублирован");
      location.reload();
    } catch (error) { showToast(error.message, "error"); duplicate.disabled = false; }
  }
  const remove = event.target.closest("[data-template-delete]");
  if (remove) {
    const modal = document.querySelector("#delete-template-modal");
    modal.dataset.id = remove.dataset.templateDelete;
    modal.showModal();
  }
});

document.querySelector("#confirm-template-delete")?.addEventListener("click", async event => {
  const modal = document.querySelector("#delete-template-modal");
  event.currentTarget.disabled = true;
  try {
    await api(`/api/templates/${modal.dataset.id}`, {method:"DELETE"});
    modal.close();
    document.querySelector(`.template-card[data-id="${CSS.escape(modal.dataset.id)}"]`)?.remove();
    showToast("Шаблон удалён");
  } catch (error) { showToast(error.message, "error"); }
  finally { event.currentTarget.disabled = false; }
});
