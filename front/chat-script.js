const CHAT_TOKEN_KEY = "archive_chat_token";
let chatToken = localStorage.getItem(CHAT_TOKEN_KEY) || "";

function resolveApiBase() {
  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get("api");
  if (fromQuery) {
    return fromQuery.replace(/\/$/, "");
  }
  return "";
}

const CHAT_API_BASE = resolveApiBase();

function apiUrl(path) {
  return CHAT_API_BASE ? `${CHAT_API_BASE}${path}` : path;
}

function setStatus(text) {
  document.getElementById("chatAuthStatus").textContent = text;
}

function addMessage(role, text) {
  const box = document.getElementById("chatMessages");
  const div = document.createElement("div");
  div.className = `chat-line ${role}`;
  div.textContent = text;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

async function registerUser() {
  const username = document.getElementById("loginUser").value.trim();
  const password = document.getElementById("loginPass").value.trim();
  if (!username || !password) {
    setStatus("Введите логин и пароль");
    return;
  }

  const response = await fetch(apiUrl("/register"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password })
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    setStatus(`Ошибка регистрации: ${payload.detail || response.status}`);
    return;
  }

  setStatus("Регистрация успешна. Теперь войдите.");
}

async function loginUser() {
  const username = document.getElementById("loginUser").value.trim();
  const password = document.getElementById("loginPass").value.trim();
  if (!username || !password) {
    setStatus("Введите логин и пароль");
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
    setStatus(`Ошибка входа: ${payload.detail || response.status}`);
    return;
  }

  const payload = await response.json();
  chatToken = payload.access_token || "";
  localStorage.setItem(CHAT_TOKEN_KEY, chatToken);
  setStatus(`Вход выполнен: ${username}`);
}

function logoutUser() {
  chatToken = "";
  localStorage.removeItem(CHAT_TOKEN_KEY);
  setStatus("Вы вышли");
}

async function sendMessage() {
  const input = document.getElementById("chatInput");
  const query = input.value.trim();
  if (!query) return;

  if (!chatToken) {
    setStatus("Сначала войдите в аккаунт");
    return;
  }

  addMessage("user", `Вы: ${query}`);
  input.value = "";

  const response = await fetch(apiUrl("/chat"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${chatToken}`
    },
    body: JSON.stringify({ query })
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    addMessage("assistant", `Ошибка: ${payload.detail || response.status}`);
    return;
  }

  const payload = await response.json();
  addMessage("assistant", payload.answer || "Пустой ответ");
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("registerBtn").addEventListener("click", registerUser);
  document.getElementById("loginBtn").addEventListener("click", loginUser);
  document.getElementById("logoutBtn").addEventListener("click", logoutUser);
  document.getElementById("sendChatBtn").addEventListener("click", sendMessage);
  document.getElementById("chatInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  });

  setStatus(chatToken ? "Токен найден, можно писать в чат" : "Не авторизован");
});
