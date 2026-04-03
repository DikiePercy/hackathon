let currentUser = null;

function resolveApiBase() {
  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get("api");
  if (fromQuery) {
    return fromQuery.replace(/\/$/, "");
  }
  return "";
}

const API_BASE = resolveApiBase();

function apiUrl(path) {
  return API_BASE ? `${API_BASE}${path}` : path;
}

function setStatus(text) {
  document.getElementById("suggestAuthStatus").textContent = text;
}

async function apiFetch(path, options = {}) {
  return fetch(apiUrl(path), {
    credentials: "include",
    ...options
  });
}

function parseYear(id) {
  const raw = (document.getElementById(id).value || "").trim();
  if (!raw) return null;
  const val = Number(raw);
  return Number.isInteger(val) ? val : null;
}

function readText(id) {
  const v = (document.getElementById(id).value || "").trim();
  return v || null;
}

async function checkSession() {
  const response = await apiFetch("/me");
  if (!response.ok) {
    currentUser = null;
    setStatus("Не авторизован");
    return;
  }

  currentUser = await response.json();
  setStatus(`Вход выполнен: ${currentUser.username} (${currentUser.role})`);
}

async function registerUser() {
  const username = readText("userLogin");
  const password = readText("userPassword");
  if (!username || !password) {
    setStatus("Введите логин и пароль");
    return;
  }

  const response = await apiFetch("/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password })
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    setStatus(`Ошибка регистрации: ${body.detail || response.status}`);
    return;
  }

  setStatus("Регистрация успешна. Выполните вход.");
}

async function loginUser() {
  const username = readText("userLogin");
  const password = readText("userPassword");
  if (!username || !password) {
    setStatus("Введите логин и пароль");
    return;
  }

  const body = new URLSearchParams();
  body.set("username", username);
  body.set("password", password);

  const response = await apiFetch("/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString()
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    setStatus(`Ошибка входа: ${payload.detail || response.status}`);
    return;
  }

  await checkSession();
  await loadMySuggestions();
}

async function logoutUser() {
  await apiFetch("/logout", { method: "POST" });
  currentUser = null;
  setStatus("Вы вышли");
  document.getElementById("mySuggestionsList").innerHTML = "";
}

async function sendSuggestion() {
  if (!currentUser) {
    setStatus("Сначала войдите в аккаунт");
    return;
  }

  const fullName = readText("fullName");
  const birthYear = parseYear("birthYear");
  if (!fullName || !birthYear) {
    setStatus("ФИО и год рождения обязательны");
    return;
  }

  const payload = {
    full_name: fullName,
    birth_year: birthYear,
    death_year: parseYear("deathYear"),
    nationality: readText("nationality"),
    region: readText("region"),
    district: readText("district"),
    occupation: readText("occupation"),
    charge: readText("charge"),
    sentence: readText("sentence"),
    arrest_date: readText("arrestDate"),
    sentence_date: readText("sentenceDate"),
    rehabilitation_date: readText("rehabilitationDate"),
    biography: readText("biography") || "",
    source: readText("source"),
    status: readText("status")
  };

  const response = await apiFetch("/suggestions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    setStatus(`Ошибка отправки: ${body.detail || response.status}`);
    return;
  }

  const created = await response.json();
  setStatus(`Предложение отправлено: #${created.id}`);
  await loadMySuggestions();
}

async function loadMySuggestions() {
  if (!currentUser) {
    document.getElementById("mySuggestionsList").innerHTML = "Войдите для просмотра";
    return;
  }

  const response = await apiFetch("/suggestions/my");
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    document.getElementById("mySuggestionsList").innerHTML = `Ошибка: ${body.detail || response.status}`;
    return;
  }

  const items = await response.json();
  const container = document.getElementById("mySuggestionsList");
  if (!items.length) {
    container.innerHTML = "Пока нет предложений";
    return;
  }

  container.innerHTML = "";
  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "admin-card-row";
    row.innerHTML = `<span><strong>${item.full_name}</strong> (${item.birth_year}) #${item.id}<br><small>state: ${item.state}${item.moderation_comment ? ` | ${item.moderation_comment}` : ""}</small></span>`;
    container.appendChild(row);
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  document.getElementById("registerBtn").addEventListener("click", registerUser);
  document.getElementById("loginBtn").addEventListener("click", loginUser);
  document.getElementById("logoutBtn").addEventListener("click", logoutUser);
  document.getElementById("sendSuggestionBtn").addEventListener("click", sendSuggestion);
  document.getElementById("loadMySuggestionsBtn").addEventListener("click", loadMySuggestions);

  await checkSession();
  if (currentUser) {
    await loadMySuggestions();
  }
});
