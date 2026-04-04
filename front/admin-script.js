function resolveApiBase() {
  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get("api");
  if (fromQuery) {
    return fromQuery.replace(/\/$/, "");
  }
  return "";
}

const ADMIN_API_BASE = resolveApiBase();
let currentAdmin = null;

function apiUrl(path) {
  return ADMIN_API_BASE ? `${ADMIN_API_BASE}${path}` : path;
}

function setAdminStatus(text) {
  document.getElementById("adminStatus").textContent = text;
}

function setAdminProtectedVisible(visible) {
  document.querySelectorAll(".admin-protected").forEach((panel) => {
    panel.hidden = !visible;
  });
}

function parseIntOrNull(value) {
  if (!value || value.trim() === "") return null;
  const n = Number(value);
  return Number.isInteger(n) ? n : null;
}

function parseDateOrNull(value) {
  const v = (value || "").trim();
  return v ? v : null;
}

async function apiFetch(path, options = {}) {
  const response = await fetch(apiUrl(path), {
    credentials: "include",
    ...options
  });
  return response;
}

async function checkSession() {
  let me = null;
  if (window.SiteAuth?.refreshSession) {
    await window.SiteAuth.refreshSession();
    me = window.SiteAuth.getCurrentUser();
  } else {
    const response = await apiFetch("/me");
    if (response.ok) {
      me = await response.json();
    }
  }

  if (!me) {
    currentAdmin = null;
    setAdminProtectedVisible(false);
    setAdminStatus("Сессия не активна. Нажмите \"Зайти как админ\".");
    return null;
  }

  if (me.role !== "admin") {
    currentAdmin = me;
    setAdminProtectedVisible(false);
    setAdminStatus(`Вход как ${me.username}, но роль не admin`);
    return me;
  }

  currentAdmin = me;
  setAdminProtectedVisible(true);
  setAdminStatus(`Авторизован как admin: ${me.username}`);
  return me;
}

async function createCard() {
  if (!currentAdmin || currentAdmin.role !== "admin") {
    setAdminStatus("Нужна авторизация администратора");
    return;
  }

  const name = document.getElementById("createName").value.trim();
  if (!name) {
    setAdminStatus("Введите ФИО для создания карточки");
    return;
  }

  const payload = {
    name,
    region: document.getElementById("createRegion").value.trim() || undefined,
    district: document.getElementById("createDistrict").value.trim() || undefined,
    birth_year: parseIntOrNull(document.getElementById("createBirthYear").value),
    death_year: parseIntOrNull(document.getElementById("createDeathYear").value),
    nationality: document.getElementById("createNationality").value.trim() || undefined,
    category: document.getElementById("createOccupation").value.trim() || undefined,
    charge: document.getElementById("createCharge").value.trim() || undefined,
    sentence: document.getElementById("createSentence").value.trim() || undefined,
    arrest_date: parseDateOrNull(document.getElementById("createArrestDate").value),
    sentence_date: parseDateOrNull(document.getElementById("createSentenceDate").value),
    rehabilitation_date: parseDateOrNull(document.getElementById("createRehabilitationDate").value),
    source: document.getElementById("createSource").value.trim() || undefined,
    status: document.getElementById("createStatus").value.trim() || undefined,
    description: document.getElementById("createBiography").value.trim() || undefined
  };

  const response = await apiFetch("/cards", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    setAdminStatus(`Ошибка создания: ${body.detail || response.status}`);
    return;
  }

  const created = await response.json();
  setAdminStatus(`Карточка создана: #${created.id}`);
  document.getElementById("createName").value = "";
  document.getElementById("createRegion").value = "";
  document.getElementById("createDistrict").value = "";
  document.getElementById("createBirthYear").value = "";
  document.getElementById("createDeathYear").value = "";
  document.getElementById("createNationality").value = "";
  document.getElementById("createOccupation").value = "";
  document.getElementById("createCharge").value = "";
  document.getElementById("createSentence").value = "";
  document.getElementById("createArrestDate").value = "";
  document.getElementById("createSentenceDate").value = "";
  document.getElementById("createRehabilitationDate").value = "";
  document.getElementById("createSource").value = "";
  document.getElementById("createStatus").value = "";
  document.getElementById("createBiography").value = "";
  await loadCards();
}

async function importSeedFile() {
  const fileInput = document.getElementById("seedFile");
  const file = fileInput.files[0];
  if (!file) {
    setAdminStatus("Выберите JSON файл");
    return;
  }

  try {
    const text = await file.text();
    const payload = JSON.parse(text);

    const response = await apiFetch("/cards/import/seed", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || response.status);
    }

    const body = await response.json();
    setAdminStatus(`Импорт завершен: создано ${body.created}, пропущено ${body.skipped_duplicates}`);
    await loadCards();
  } catch (err) {
    setAdminStatus(`Ошибка импорта: ${err.message}`);
  }
}

async function deleteCard(cardId) {
  const response = await apiFetch(`/cards/${cardId}`, {
    method: "DELETE"
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    setAdminStatus(`Ошибка удаления: ${body.detail || response.status}`);
    return;
  }

  setAdminStatus(`Карточка ${cardId} удалена`);
  await loadCards();
}

async function loadCards() {
  const container = document.getElementById("adminCardsList");
  if (!currentAdmin || currentAdmin.role !== "admin") {
    container.innerHTML = "Войдите как admin для просмотра карточек";
    return;
  }

  container.innerHTML = "Загрузка...";
  const response = await apiFetch("/cards");

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    container.innerHTML = `Ошибка: ${body.detail || response.status}`;
    return;
  }

  const cards = await response.json();
  if (!cards.length) {
    container.innerHTML = "Нет карточек";
    return;
  }

  container.innerHTML = "";
  cards.forEach((card) => {
    const row = document.createElement("div");
    row.className = "admin-card-row";
    row.innerHTML = `<span><strong>${card.name}</strong> (${card.birth_year || "?"}) #${card.id}</span>`;

    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "Удалить";
    btn.addEventListener("click", () => deleteCard(card.id));

    row.appendChild(btn);
    container.appendChild(row);
  });
}

async function moderationAction(id, action) {
  const comment = window.prompt("Комментарий модератора (необязательно):", "") || "";
  const response = await apiFetch(`/admin/suggestions/${id}/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ comment })
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    setAdminStatus(`Ошибка модерации: ${body.detail || response.status}`);
    return;
  }

  const body = await response.json();
  setAdminStatus(body.message || "Модерация выполнена");
  await loadSuggestions();
  await loadCards();
}

async function deleteSuggestion(id) {
  const response = await apiFetch(`/admin/suggestions/${id}`, { method: "DELETE" });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    setAdminStatus(`Ошибка удаления предложки: ${body.detail || response.status}`);
    return;
  }
  setAdminStatus(`Предложение #${id} удалено`);
  await loadSuggestions();
}

async function loadSuggestions() {
  const container = document.getElementById("adminSuggestionsList");
  const state = document.getElementById("suggestionsStateFilter").value;
  if (!currentAdmin || currentAdmin.role !== "admin") {
    container.innerHTML = "Войдите как admin для модерации";
    return;
  }

  const query = state ? `?state=${encodeURIComponent(state)}` : "";
  const response = await apiFetch(`/admin/suggestions${query}`);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    container.innerHTML = `Ошибка: ${body.detail || response.status}`;
    return;
  }

  const items = await response.json();
  if (!items.length) {
    container.innerHTML = "Предложений нет";
    return;
  }

  container.innerHTML = "";
  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "admin-card-row";

    const info = document.createElement("div");
    const photoState = item.photo_url ? "photo: yes" : "photo: placeholder";
    const docState = item.document_filename
      ? `doc: ${item.document_filename}`
      : (item.document_text ? "doc: text" : "doc: -");
    info.innerHTML = `<strong>${item.full_name}</strong> (${item.birth_year || "?"}) #${item.id}<br><small>mode: ${item.suggestion_kind}${item.target_person_id ? ` | target: #${item.target_person_id}` : ""} | state: ${item.state} | source: ${item.source || "-"} | ${photoState} | ${docState}</small>`;
    row.appendChild(info);

    const actions = document.createElement("div");

    if (item.state === "pending") {
      const approveBtn = document.createElement("button");
      approveBtn.type = "button";
      approveBtn.textContent = "Одобрить";
      approveBtn.addEventListener("click", () => moderationAction(item.id, "approve"));
      actions.appendChild(approveBtn);

      const rejectBtn = document.createElement("button");
      rejectBtn.type = "button";
      rejectBtn.textContent = "Отклонить";
      rejectBtn.addEventListener("click", () => moderationAction(item.id, "reject"));
      actions.appendChild(rejectBtn);
    }

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.textContent = "Удалить";
    deleteBtn.addEventListener("click", () => deleteSuggestion(item.id));
    actions.appendChild(deleteBtn);

    row.appendChild(actions);
    container.appendChild(row);
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  document.getElementById("openAdminLoginModalBtn")?.addEventListener("click", () => {
    window.SiteAuth?.openModal?.();
  });

  document.getElementById("seedImportBtn").addEventListener("click", importSeedFile);
  document.getElementById("createCardBtn").addEventListener("click", createCard);
  document.getElementById("refreshCardsBtn").addEventListener("click", loadCards);
  document.getElementById("loadSuggestionsBtn").addEventListener("click", loadSuggestions);

  window.addEventListener("site-auth-changed", async () => {
    const me = await checkSession();
    if (me?.role === "admin") {
      await loadCards();
      await loadSuggestions();
      return;
    }

    document.getElementById("adminCardsList").innerHTML = "";
    document.getElementById("adminSuggestionsList").innerHTML = "";
  });

  const me = await checkSession();
  if (me?.role === "admin") {
    await loadCards();
    await loadSuggestions();
  }
});
