// Mock data fallback
const MOCK_DATA = {
  id: 18,
  full_name: "Гольдберг Максим Ефимович",
  birth_year: 1900,
  death_year: 1937,
  nationality: "еврей",
  occupation: "Начальник строительства БМК",
  arrest_date: "1937-03-12",
  sentence: "ВМН (расстрел)",
  sentence_date: "1937-10-30",
  rehabilitation_date: "1957-06-06",
  biography: "Максим Ефимович родился в 1900 году в Варшаве в семье врача. Окончил гимназию. В 1928 году ЦК Профсоюзов направил Максима Ефимовича из Москвы в Иваново-Вознесенск. В феврале 1932 года был командирован в Барнаул, где возглавил строительство меланжевого комбината... Гольдберг был исключен из партии, а 12 марта 1937 года арестован. Приговор приведен в исполнение.",
  photo_url: "https://via.placeholder.com/250x350.png?text=Portrait",
  documents: [
    "https://via.placeholder.com/100x140.png?text=Doc+1",
    "https://via.placeholder.com/100x140.png?text=Doc+2",
    "https://via.placeholder.com/100x140.png?text=Doc+3",
    "https://via.placeholder.com/100x140.png?text=Doc+4"
  ]
};

// Metadata field labels (Russian)
const META_LABELS = {
  nationality: "Национальность",
  occupation: "Профессия / должность",
  arrest_date: "Дата ареста",
  sentence: "Приговор",
  sentence_date: "Дата приговора",
  rehabilitation_date: "Дата реабилитации"
};

function resolveApiBase() {
  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get("api");
  if (fromQuery) {
    return fromQuery.replace(/\/$/, "");
  }
  return "";
}

const API_BASE = resolveApiBase();
const TOKEN_KEY = "archive_auth_token";
let authToken = localStorage.getItem(TOKEN_KEY) || "";

function apiUrl(path) {
  return API_BASE ? `${API_BASE}${path}` : path;
}

function updateAuthStatus(text) {
  const statusEl = document.getElementById("authStatus");
  if (statusEl) {
    statusEl.textContent = text;
  }
}

function appendRagMessage(role, text) {
  const box = document.getElementById("ragMessages");
  if (!box) return;
  const div = document.createElement("div");
  div.className = `rag-message ${role}`;
  div.textContent = text;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

async function registerUser() {
  const username = document.getElementById("authUsername").value.trim();
  const password = document.getElementById("authPassword").value.trim();
  if (!username || !password) {
    updateAuthStatus("Введите логин и пароль");
    return;
  }

  try {
    const response = await fetch(apiUrl("/register"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    updateAuthStatus("Регистрация выполнена. Теперь войдите.");
  } catch (err) {
    updateAuthStatus(`Ошибка регистрации: ${err.message}`);
  }
}

async function loginUser() {
  const username = document.getElementById("authUsername").value.trim();
  const password = document.getElementById("authPassword").value.trim();
  if (!username || !password) {
    updateAuthStatus("Введите логин и пароль");
    return;
  }

  try {
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
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }

    const payload = await response.json();
    authToken = payload.access_token || "";
    localStorage.setItem(TOKEN_KEY, authToken);
    updateAuthStatus(`Вход выполнен: ${username}`);
  } catch (err) {
    updateAuthStatus(`Ошибка входа: ${err.message}`);
  }
}

function logoutUser() {
  authToken = "";
  localStorage.removeItem(TOKEN_KEY);
  updateAuthStatus("Вы вышли из аккаунта");
}

async function sendRagQuery() {
  const input = document.getElementById("ragQuery");
  const query = input.value.trim();
  if (!query) return;
  if (!authToken) {
    updateAuthStatus("Сначала войдите, чтобы использовать RAG чат");
    return;
  }

  appendRagMessage("user", `Вы: ${query}`);
  input.value = "";

  try {
    const response = await fetch(apiUrl("/chat"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ query })
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    const payload = await response.json();
    appendRagMessage("assistant", `RAG: ${payload.answer || "Пустой ответ"}`);
  } catch (err) {
    appendRagMessage("assistant", `Ошибка: ${err.message}`);
  }
}

function formatDate(dateStr) {
  if (!dateStr) return "—";
  const parts = dateStr.split("-");
  if (parts.length === 3) {
    return `${parts[2]}.${parts[1]}.${parts[0]}`;
  }
  return dateStr;
}

function renderPerson(data) {
  // Name & years
  document.getElementById("personName").textContent = data.full_name;
  const years = [data.birth_year, data.death_year].filter(Boolean).join(" — ");
  document.getElementById("personYears").textContent = years ? `(${years})` : "";

  // Photo
  const photoEl = document.getElementById("personPhoto");
  photoEl.src = data.photo_url || "";
  photoEl.alt = "Портрет: " + data.full_name;

  // Metadata table
  const tbody = document.querySelector("#metaTable tbody");
  tbody.innerHTML = "";

  // Add birth/death years first
  const addRow = (label, value) => {
    const tr = document.createElement("tr");
    const td1 = document.createElement("td");
    td1.textContent = label;
    const td2 = document.createElement("td");
    td2.textContent = value || "—";
    tr.appendChild(td1);
    tr.appendChild(td2);
    tbody.appendChild(tr);
  };

  addRow("Год рождения", data.birth_year);
  addRow("Год смерти", data.death_year);

  for (const [key, label] of Object.entries(META_LABELS)) {
    let value = data[key];
    if (key.includes("date")) {
      value = formatDate(value);
    }
    addRow(label, value);
  }

  // Documents grid
  const grid = document.getElementById("documentsGrid");
  grid.innerHTML = "";
  if (data.documents && data.documents.length > 0) {
    data.documents.forEach((url, i) => {
      const div = document.createElement("div");
      div.className = "doc-thumb";
      const img = document.createElement("img");
      img.src = url;
      img.alt = `Документ ${i + 1}`;
      div.appendChild(img);
      grid.appendChild(div);
    });
  }

  // Biography
  const bioDiv = document.getElementById("biographyText");
  bioDiv.innerHTML = "";
  if (data.biography) {
    // Split by sentences ending with period for paragraphs, or just wrap
    const paragraphs = data.biography.split(/\.{3}|(?<=\.)\s+(?=[А-ЯA-Z])/);
    paragraphs.forEach(text => {
      text = text.trim();
      if (!text) return;
      if (!text.endsWith(".")) text += ".";
      const p = document.createElement("p");
      p.textContent = text;
      bioDiv.appendChild(p);
    });
  }
}

async function loadPerson() {
  const params = new URLSearchParams(window.location.search);
  const personId = Number(params.get("id")) || 1;
  const personApiUrl = apiUrl(`/api/person/${personId}`);
  let data;

  try {
    const response = await fetch(personApiUrl);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    data = await response.json();
    console.log("Loaded data from API");
  } catch (err) {
    console.warn("API unavailable, using mock data:", err.message);
    data = MOCK_DATA;
  }

  renderPerson(data);
}

async function searchPerson() {
  const input = document.getElementById("searchInput");
  const query = (input.value || "").trim();
  if (!query) {
    await loadPerson();
    return;
  }

  try {
    const response = await fetch(apiUrl(`/api/persons/search?q=${encodeURIComponent(query)}&limit=1`));
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const results = await response.json();
    if (!results.length) {
      alert("Ничего не найдено");
      return;
    }
    const person = results[0];
    const url = new URL(window.location.href);
    url.searchParams.set("id", String(person.id));
    history.replaceState(null, "", url.toString());
    await loadPerson();
  } catch (err) {
    console.warn("Search failed:", err.message);
    alert("Ошибка поиска: backend недоступен");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("searchBtn");
  const input = document.getElementById("searchInput");
  const registerBtn = document.getElementById("registerBtn");
  const loginBtn = document.getElementById("loginBtn");
  const logoutBtn = document.getElementById("logoutBtn");
  const ragSendBtn = document.getElementById("sendRagBtn");
  const ragInput = document.getElementById("ragQuery");

  btn.addEventListener("click", searchPerson);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      searchPerson();
    }
  });

  registerBtn.addEventListener("click", registerUser);
  loginBtn.addEventListener("click", loginUser);
  logoutBtn.addEventListener("click", logoutUser);
  ragSendBtn.addEventListener("click", sendRagQuery);
  ragInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendRagQuery();
    }
  });

  updateAuthStatus(authToken ? "Авторизован (токен сохранен)" : "Не авторизован");

  loadPerson();
});
