const STORAGE_KEY = "multiDbSelect.servers";
const DATABASE_STORAGE_KEY = "multiDbSelect.databases";
const QUERY_STORAGE_KEY = "multiDbSelect.query";

const checkboxes = [...document.querySelectorAll('input[name="servers"]')];
const summary = document.getElementById("selection-summary");
const credentialsForm = document.getElementById("credentials-form");
const prodUsernameInput = document.getElementById("prod-username");
const prodPasswordInput = document.getElementById("prod-password");
const stageUsernameInput = document.getElementById("stage-username");
const stagePasswordInput = document.getElementById("stage-password");
const loadButton = document.getElementById("load-databases");
const loadError = document.getElementById("load-error");
const databaseList = document.getElementById("database-list");
const databaseSummary = document.getElementById("database-summary");
const selectAllDatabasesButton = document.getElementById("select-all-databases");
const clearAllDatabasesButton = document.getElementById("clear-all-databases");
const queryInput = document.getElementById("sql-query");
const runButton = document.getElementById("run-query");
const queryError = document.getElementById("query-error");
const resultsList = document.getElementById("results-list");
const resultsCopy = document.getElementById("results-copy");

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

function credentialPayload() {
  const credentials = {};
  if (prodUsernameInput.value || prodPasswordInput.value) {
    credentials.prod = {
      username: prodUsernameInput.value,
      password: prodPasswordInput.value,
    };
  }
  if (stageUsernameInput.value || stagePasswordInput.value) {
    credentials.stage = {
      username: stageUsernameInput.value,
      password: stagePasswordInput.value,
    };
  }
  return credentials;
}

function envCheckboxes(env) {
  return checkboxes.filter((box) => box.dataset.environment === env);
}

function envCount(env) {
  const boxes = envCheckboxes(env);
  return {
    selected: boxes.filter((box) => box.checked).length,
    total: boxes.length,
  };
}

function updateSummary() {
  const prod = envCount("prod");
  const stage = envCount("stage");
  const count = prod.selected + stage.selected;
  const parts = [];
  if (prod.selected) {
    parts.push(`${prod.selected} of ${prod.total} production`);
  }
  if (stage.selected) {
    parts.push(`${stage.selected} of ${stage.total} staging`);
  }

  summary.textContent = parts.length
    ? `${parts.join(", ")} selected`
    : "No servers selected";

  loadButton.disabled = count === 0 || loadButton.dataset.loading === "true";
  updateRunState();
}

function updateDatabaseSummary() {
  const boxes = databaseCheckboxes();
  const count = boxes.filter((box) => box.checked).length;
  if (!boxes.length) {
    databaseSummary.textContent = "";
  } else if (count === 1) {
    databaseSummary.textContent = `1 of ${boxes.length} databases selected`;
  } else {
    databaseSummary.textContent = `${count} of ${boxes.length} databases selected`;
  }
  updateRunState();
}

function updateRunState() {
  runButton.disabled =
    selectedDatabases().length === 0 ||
    !queryInput.value.trim() ||
    runButton.dataset.loading === "true";
}

function persistSelection() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(selectedIds()));
}

function persistDatabaseSelection() {
  localStorage.setItem(DATABASE_STORAGE_KEY, JSON.stringify(selectedDatabases()));
}

function persistQuery() {
  localStorage.setItem(QUERY_STORAGE_KEY, queryInput.value);
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

function restoreQuery() {
  const saved = localStorage.getItem(QUERY_STORAGE_KEY);
  if (typeof saved === "string") {
    queryInput.value = saved;
  }
}

function setEnvAll(env, checked) {
  envCheckboxes(env).forEach((box) => {
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

function setFormError(element, message) {
  if (!message) {
    element.hidden = true;
    element.textContent = "";
    return;
  }
  element.hidden = false;
  element.textContent = message;
}

function environmentLabel(environment) {
  return environment === "stage" ? "Stage" : "Prod";
}

function renderDatabaseResults(results) {
  databaseList.replaceChildren();
  setCurrentStep("databases");

  const grouped = { prod: [], stage: [] };
  for (const result of results) {
    const env = result.environment === "stage" ? "stage" : "prod";
    grouped[env].push(result);
  }

  for (const env of ["prod", "stage"]) {
    if (!grouped[env].length) {
      continue;
    }
    const label = document.createElement("li");
    label.className = `env-label is-${env}`;
    label.textContent = env === "stage" ? "Staging" : "Production";
    databaseList.append(label);

    for (const result of grouped[env]) {
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
        const rowLabel = document.createElement("label");
        rowLabel.className = "server-row db-row";
        const input = document.createElement("input");
        input.type = "checkbox";
        input.name = "databases";
        input.value = database.name;
        input.dataset.serverId = result.id;
        input.dataset.environment = env;
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
        rowLabel.append(input, copy);
        item.append(rowLabel);
        dbs.append(item);
      }
      group.append(dbs);
      databaseList.append(group);
    }
  }

  restoreDatabaseSelection();
  updateDatabaseSummary();
}

function isMissingTargetError(error) {
  return /invalid (object|column) name|cannot find the object|could not find|could not be bound|does not exist|unknown object|invalid object/i.test(
    error || ""
  );
}

function visibleQueryResults(results) {
  return results.filter((result) => {
    if (result.ok) {
      return result.rowCount > 0;
    }
    return Boolean(result.error) && !isMissingTargetError(result.error);
  });
}

function renderQueryResults(results) {
  const visible = visibleQueryResults(results);
  resultsList.replaceChildren();
  setCurrentStep("results");

  if (!visible.length) {
    resultsCopy.textContent = "No databases returned matching rows.";
    const empty = document.createElement("p");
    empty.className = "result-note";
    empty.textContent =
      "Databases where the table or column was not found were omitted.";
    resultsList.append(empty);
    return;
  }

  resultsCopy.textContent =
    visible.length === 1
      ? "Found matching rows in 1 database."
      : `Found matching rows in ${visible.length} databases.`;

  for (const result of visible) {
    const block = document.createElement("article");
    block.className = "result-block";

    const heading = document.createElement("div");
    heading.className = "db-group-head";
    const copy = document.createElement("div");
    copy.className = "server-copy";
    const title = document.createElement("h3");
    title.textContent = result.database;
    const server = document.createElement("span");
    server.className = "server-host";
    server.textContent = result.serverName;
    copy.append(title, server);
    const meta = document.createElement("span");
    meta.className = "server-meta";
    const env = document.createElement("span");
    env.className = `env-pill is-${result.environment || "prod"}`;
    env.textContent = environmentLabel(result.environment);
    meta.append(env);
    heading.append(copy, meta);
    block.append(heading);

    if (!result.ok) {
      const error = document.createElement("p");
      error.className = "db-error";
      error.textContent = result.error || "Query failed.";
      block.append(error);
      resultsList.append(block);
      continue;
    }

    const note = document.createElement("p");
    note.className = "result-note";
    note.textContent = result.truncated
      ? `${result.rowCount} rows shown; additional rows were truncated.`
      : `${result.rowCount} row${result.rowCount === 1 ? "" : "s"}`;
    block.append(note);

    if (!result.columns.length) {
      resultsList.append(block);
      continue;
    }

    const scroller = document.createElement("div");
    scroller.className = "table-wrap";
    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    for (const column of result.columns) {
      const th = document.createElement("th");
      th.textContent = column;
      headRow.append(th);
    }
    thead.append(headRow);
    const tbody = document.createElement("tbody");
    for (const row of result.rows) {
      const tr = document.createElement("tr");
      for (const value of row) {
        const td = document.createElement("td");
        td.textContent = value == null ? "" : String(value);
        tr.append(td);
      }
      tbody.append(tr);
    }
    table.append(thead, tbody);
    scroller.append(table);
    block.append(scroller);
    resultsList.append(block);
  }
}

async function loadDatabases(event) {
  event.preventDefault();
  if (!selectedIds().length) {
    return;
  }

  loadButton.dataset.loading = "true";
  loadButton.disabled = true;
  loadButton.textContent = "Loading databases…";
  setFormError(loadError, "");

  try {
    const response = await fetch("/api/databases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        servers: selectedIds(),
        credentials: credentialPayload(),
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      setFormError(loadError, payload.error || "Could not load databases.");
      return;
    }
    renderDatabaseResults(payload.results || []);
  } catch {
    setFormError(loadError, "Could not reach the Multi-DB Select app.");
  } finally {
    loadButton.dataset.loading = "false";
    loadButton.textContent = "Load databases";
    updateSummary();
  }
}

async function runQuery() {
  const databases = selectedDatabases();
  const query = queryInput.value.trim();
  if (!databases.length || !query) {
    return;
  }

  runButton.dataset.loading = "true";
  runButton.disabled = true;
  runButton.textContent = "Running query…";
  setFormError(queryError, "");

  try {
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        databases,
        credentials: credentialPayload(),
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      setFormError(queryError, payload.error || "Could not run the query.");
      return;
    }
    renderQueryResults(payload.results || []);
  } catch {
    setFormError(queryError, "Could not reach the Multi-DB Select app.");
  } finally {
    runButton.dataset.loading = "false";
    runButton.textContent = "Run query";
    updateRunState();
  }
}

checkboxes.forEach((box) => {
  box.addEventListener("change", () => {
    persistSelection();
    updateSummary();
  });
});

selectAllDatabasesButton.addEventListener("click", () => setAllDatabases(true));
clearAllDatabasesButton.addEventListener("click", () => setAllDatabases(false));
document.querySelectorAll("[data-select-env]").forEach((button) => {
  button.addEventListener("click", () => {
    setEnvAll(button.dataset.selectEnv, button.dataset.checked !== "false");
  });
});
credentialsForm.addEventListener("submit", loadDatabases);
queryInput.addEventListener("input", () => {
  persistQuery();
  updateRunState();
});
runButton.addEventListener("click", runQuery);

restoreSelection();
restoreQuery();
updateSummary();
