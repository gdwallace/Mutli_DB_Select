const STORAGE_KEY = "multiDbSelect.servers";
const DATABASE_STORAGE_KEY = "multiDbSelect.databases";

const checkboxes = [...document.querySelectorAll('input[name="servers"]')];
const summary = document.getElementById("selection-summary");
const selectAllButton = document.getElementById("select-all");
const clearAllButton = document.getElementById("clear-all");
const credentialsForm = document.getElementById("credentials-form");
const usernameInput = document.getElementById("sql-username");
const passwordInput = document.getElementById("sql-password");
const windowsAuthInput = document.getElementById("windows-auth");
const loadButton = document.getElementById("load-databases");
const loadError = document.getElementById("load-error");
const databasePanel = document.getElementById("database-panel");
const databaseList = document.getElementById("database-list");
const databaseSummary = document.getElementById("database-summary");
const selectAllDatabasesButton = document.getElementById("select-all-databases");
const clearAllDatabasesButton = document.getElementById("clear-all-databases");

function selectedIds() {
  return checkboxes.filter((box) => box.checked).map((box) => box.value);
}

function databaseCheckboxes() {
  return [...document.querySelectorAll('input[name="databases"]')];
}

function selectedDatabases() {
  return databaseCheckboxes()
    .filter((box) => box.checked)
    .map((box) => ({ serverId: box.dataset.serverId, name: box.value }));
}

function updateSummary() {
  const count = selectedIds().length;
  const total = checkboxes.length;

  if (count === 0) {
    summary.textContent = "No servers selected";
  } else if (count === 1) {
    summary.textContent = `1 of ${total} servers selected`;
  } else {
    summary.textContent = `${count} of ${total} servers selected`;
  }

  loadButton.disabled = count === 0 || loadButton.dataset.loading === "true";
}

function updateDatabaseSummary() {
  const boxes = databaseCheckboxes();
  const count = boxes.filter((box) => box.checked).length;
  if (!boxes.length) {
    databaseSummary.textContent = "";
    return;
  }
  databaseSummary.textContent =
    count === 1
      ? `1 of ${boxes.length} databases selected`
      : `${count} of ${boxes.length} databases selected`;
}

function persistSelection() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(selectedIds()));
}

function persistDatabaseSelection() {
  localStorage.setItem(DATABASE_STORAGE_KEY, JSON.stringify(selectedDatabases()));
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

function restoreDatabaseSelection() {
  try {
    const saved = JSON.parse(localStorage.getItem(DATABASE_STORAGE_KEY) || "[]");
    if (!Array.isArray(saved)) {
      return;
    }
    const selected = new Set(
      saved.map((item) => `${item.serverId}\0${item.name}`)
    );
    databaseCheckboxes().forEach((box) => {
      box.checked = selected.has(`${box.dataset.serverId}\0${box.value}`);
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

function setAllDatabases(checked) {
  databaseCheckboxes().forEach((box) => {
    box.checked = checked;
  });
  persistDatabaseSelection();
  updateDatabaseSummary();
}

function setCurrentStep(step) {
  document.querySelectorAll(".steps li").forEach((item) => {
    item.classList.toggle("is-current", item.dataset.step === step);
  });
}

function setLoadError(message) {
  if (!message) {
    loadError.hidden = true;
    loadError.textContent = "";
    return;
  }
  loadError.hidden = false;
  loadError.textContent = message;
}

function setWindowsAuthState() {
  const enabled = windowsAuthInput.checked;
  usernameInput.disabled = enabled;
  passwordInput.disabled = enabled;
}

function renderDatabaseResults(results) {
  databaseList.replaceChildren();
  databasePanel.hidden = false;
  setCurrentStep("databases");

  for (const result of results) {
    const group = document.createElement("li");
    group.className = "db-group";

    const heading = document.createElement("div");
    heading.className = "db-group-head";
    const title = document.createElement("h3");
    title.textContent = result.name;
    heading.append(title);
    if (result.ip) {
      const ip = document.createElement("span");
      ip.className = "server-ip";
      ip.textContent = result.ip;
      heading.append(ip);
    }
    group.append(heading);

    if (!result.ok) {
      const error = document.createElement("p");
      error.className = "db-error";
      error.textContent = result.error || "Could not load databases.";
      group.append(error);
      databaseList.append(group);
      continue;
    }

    const dbs = document.createElement("ul");
    dbs.className = "db-rows";
    for (const database of result.databases) {
      const item = document.createElement("li");
      const label = document.createElement("label");
      label.className = "server-row db-row";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.name = "databases";
      input.value = database.name;
      input.dataset.serverId = result.id;
      input.addEventListener("change", () => {
        persistDatabaseSelection();
        updateDatabaseSummary();
      });
      const copy = document.createElement("span");
      copy.className = "server-copy";
      const name = document.createElement("span");
      name.className = "server-name";
      name.textContent = database.name;
      copy.append(name);
      if (database.system) {
        const tag = document.createElement("span");
        tag.className = "system-tag";
        tag.textContent = "system";
        copy.append(tag);
      }
      label.append(input, copy);
      item.append(label);
      dbs.append(item);
    }
    group.append(dbs);
    databaseList.append(group);
  }

  restoreDatabaseSelection();
  updateDatabaseSummary();
}

async function loadDatabases(event) {
  event.preventDefault();
  if (!selectedIds().length) {
    return;
  }

  loadButton.dataset.loading = "true";
  loadButton.disabled = true;
  loadButton.textContent = "Loading databases…";
  setLoadError("");

  const body = {
    servers: selectedIds(),
    windows_auth: windowsAuthInput.checked,
  };
  if (usernameInput.value) {
    body.username = usernameInput.value;
  }
  if (passwordInput.value) {
    body.password = passwordInput.value;
  }

  try {
    const response = await fetch("/api/databases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok) {
      setLoadError(payload.error || "Could not load databases.");
      return;
    }
    renderDatabaseResults(payload.results || []);
  } catch {
    setLoadError("Could not reach the Multi-DB Select app.");
  } finally {
    loadButton.dataset.loading = "false";
    loadButton.textContent = "Load databases";
    updateSummary();
  }
}

checkboxes.forEach((box) => {
  box.addEventListener("change", () => {
    persistSelection();
    updateSummary();
  });
});

selectAllButton.addEventListener("click", () => setAll(true));
clearAllButton.addEventListener("click", () => setAll(false));
selectAllDatabasesButton.addEventListener("click", () => setAllDatabases(true));
clearAllDatabasesButton.addEventListener("click", () => setAllDatabases(false));
windowsAuthInput.addEventListener("change", setWindowsAuthState);
credentialsForm.addEventListener("submit", loadDatabases);

restoreSelection();
setWindowsAuthState();
updateSummary();
