const STORAGE_KEY = "multiDbSelect.servers";

const checkboxes = [...document.querySelectorAll('input[name="servers"]')];
const summary = document.getElementById("selection-summary");
const selectAllButton = document.getElementById("select-all");
const clearAllButton = document.getElementById("clear-all");

function selectedIds() {
  return checkboxes.filter((box) => box.checked).map((box) => box.value);
}

function updateSummary() {
  const count = selectedIds().length;
  const total = checkboxes.length;

  if (count === 0) {
    summary.textContent = "No servers selected";
    return;
  }

  summary.textContent =
    count === 1
      ? `1 of ${total} servers selected`
      : `${count} of ${total} servers selected`;
}

function persistSelection() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(selectedIds()));
}

function restoreSelection() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    if (!Array.isArray(saved)) {
      return;
    }
    checkboxes.forEach((box) => {
      box.checked = saved.includes(box.value);
    });
  } catch {
    // Ignore unreadable localStorage and start with an empty selection.
  }
}

function setAll(checked) {
  checkboxes.forEach((box) => {
    box.checked = checked;
  });
  persistSelection();
  updateSummary();
}

checkboxes.forEach((box) => {
  box.addEventListener("change", () => {
    persistSelection();
    updateSummary();
  });
});

selectAllButton.addEventListener("click", () => setAll(true));
clearAllButton.addEventListener("click", () => setAll(false));

restoreSelection();
updateSummary();
