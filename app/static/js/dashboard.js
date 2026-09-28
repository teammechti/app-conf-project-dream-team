import {api, setLoading, showToast} from "./common.js?v=0.5.1";

const cards = [...document.querySelectorAll(".queue-card")];
const filters = [...document.querySelectorAll("[data-filter]")];
const search = document.querySelector("#queue-search");
let activeFilter = "all";

function update() {
  const query = search?.value.trim().toLowerCase() || "";
  let visible = 0;
  cards.forEach(card => {
    if (!card.isConnected) return;
    const matchesFilter = activeFilter === "all" || card.dataset.status === activeFilter;
    const matchesSearch = !query || card.dataset.name.includes(query);
    card.hidden = !(matchesFilter && matchesSearch);
    if (!card.hidden) visible += 1;
  });
  const empty = document.querySelector("#no-results");
  if (empty) empty.hidden = visible !== 0;
}

filters.forEach(button => button.addEventListener("click", () => {
  filters.forEach(item => item.classList.toggle("active", item === button));
  activeFilter = button.dataset.filter;
  update();
}));
search?.addEventListener("input", update);

const deleteModal = document.querySelector("#delete-queue-modal");
const confirmDelete = document.querySelector("#confirm-queue-delete");
let pendingQueueId = null;

document.addEventListener("click", event => {
  const button = event.target.closest("[data-delete-queue]");
  if (!button) return;
  pendingQueueId = button.dataset.deleteQueue;
  document.querySelector("#delete-queue-name").textContent = `«${button.dataset.queueName}»`;
  button.closest("details")?.removeAttribute("open");
  deleteModal.showModal();
});

confirmDelete.addEventListener("click", async () => {
  if (!pendingQueueId) return;
  setLoading(confirmDelete, true);
  try {
    await api(`/api/queues/${encodeURIComponent(pendingQueueId)}`, {method:"DELETE"});
    showToast("Очередь удалена");
    window.setTimeout(() => location.reload(), 180);
  } catch (error) {
    showToast(error.message, "error");
    setLoading(confirmDelete, false);
  }
});
