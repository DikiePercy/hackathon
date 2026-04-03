const ADMIN_TOKEN_KEY = "archive_admin_token";
let adminToken = localStorage.getItem(ADMIN_TOKEN_KEY) || "";

function resolveApiBase() {
  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get("api");
  if (fromQuery) {
    return fromQuery.replace(/\/$/, "");
  }
  return "";
}

const ADMIN_API_BASE = resolveApiBase();

function apiUrl(path) {
  return ADMIN_API_BASE ? `${ADMIN_API_BASE}${path}` : path;
}

function setAdminStatus(text) {
  document.getElementById("adminStatus").textContent = text;
}

function authHeaders() {
  return adminToken ? { Authorization: `Bearer ${adminToken}` } : {};
}

async function registerAdmin() {
  const username = document.getElementById("adminUser").value.trim();
  const password = document.getElementById("adminPass").value.trim();
  if (!username || !password) {
    setAdminStatus("Введите логин и пароль");
    return;
  }

  const response = await fetch(apiUrl("/register"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password })
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    setAdminStatus(`Ошибка регистрации: ${payload.detail || response.status}`);
    return;
  }

  setAdminStatus("Регистрация успешна. Войдите.");
}

async function loginAdmin() {
  const username = document.getElementById("adminUser").value.trim();
  const password = document.getElementById("adminPass").value.trim();
  if (!username || !password) {
    setAdminStatus("Введите логин и пароль");
    return;
  }

  const body = new URLSearchParams();
  body.set("username", username);
  body.set("password", password);

  const response = await fetch(apiUrl("/login"), {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString()
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    setAdminStatus(`Ошибка входа: ${payload.detail || response.status}`);
    return;
  }

  const payload = await response.json();
  adminToken = payload.access_token || "";
  localStorage.setItem(ADMIN_TOKEN_KEY, adminToken);
  setAdminStatus(`Вход выполнен: ${username}`);
  await loadCards();
}

function logoutAdmin() {
  adminToken = "";
  localStorage.removeItem(ADMIN_TOKEN_KEY);
  setAdminStatus("Вы вышли");
  document.getElementById("adminCardsList").innerHTML = "";
}

async function importSeedFile() {
  const fileInput = document.getElementById("seedFile");
  const file = fileInput.files[0];
  if (!file) {
    setAdminStatus("Выберите JSON файл");
    return;
  }
  if (!adminToken) {
    setAdminStatus("Сначала войдите");
    return;
  }

  try {
    const text = await file.text();
    const payload = JSON.parse(text);

    const response = await fetch(apiUrl("/cards/import/seed"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders()
      },
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
  if (!adminToken) {
    setAdminStatus("Сначала войдите");
    return;
  }

  const response = await fetch(apiUrl(`/cards/${cardId}`), {
    method: "DELETE",
    headers: authHeaders()
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
  if (!adminToken) {
    container.innerHTML = "Войдите для просмотра карточек";
    return;
  }

  container.innerHTML = "Загрузка...";
  const response = await fetch(apiUrl("/cards"), {
    headers: authHeaders()
  });

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

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("adminRegisterBtn").addEventListener("click", registerAdmin);
  document.getElementById("adminLoginBtn").addEventListener("click", loginAdmin);
  document.getElementById("adminLogoutBtn").addEventListener("click", logoutAdmin);
  document.getElementById("seedImportBtn").addEventListener("click", importSeedFile);
  document.getElementById("refreshCardsBtn").addEventListener("click", loadCards);

  setAdminStatus(adminToken ? "Токен найден" : "Не авторизован");
  loadCards();
});
