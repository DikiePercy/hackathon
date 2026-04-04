let historyOffset = 0;
let currentUser = null;

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

async function apiFetch(path, options = {}) {
  return fetch(apiUrl(path), {
    credentials: "include",
    ...options
  });
}

async function loadStats() {
  const personsEl = document.getElementById("statsPersons");
  const docsEl = document.getElementById("statsDocuments");
  if (!personsEl || !docsEl) return;

  try {
    const response = await apiFetch("/api/stats");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const stats = await response.json();
    personsEl.textContent = String(stats.persons ?? "-");
    docsEl.textContent = String(stats.documents ?? "-");
  } catch (_err) {
    personsEl.textContent = "-";
    docsEl.textContent = "-";
  }
}

function setStatus(text) {
  const statusEl = document.getElementById("chatStatus");
  if (statusEl) {
    statusEl.textContent = text;
  }
}

function addMessage(role, text) {
  const box = document.getElementById("chatMessages");
  const div = document.createElement("div");
  const cssRole = role === "user" ? "user" : "ai";
  div.className = `message ${cssRole}`;

  const cleanText = text
    .replace(/^Вы:\s*/i, "")
    .replace(/^AI:\s*/i, "")
    .replace(/^Ассистент:\s*/i, "");
  div.textContent = cleanText;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function addSources(citations, sourceIds) {
  const box = document.getElementById("chatMessages");
  const wrap = document.createElement("div");
  wrap.className = "message ai";

  const idsText = Array.isArray(sourceIds) && sourceIds.length
    ? `Источники person_id: ${sourceIds.join(", ")}`
    : "Источники не найдены";

  let html = `<div><strong>${idsText}</strong></div>`;
  if (Array.isArray(citations) && citations.length) {
    html += "<ul class=\"chat-citations\">";
    citations.slice(0, 3).forEach((c) => {
      const docName = c.document_name || "unknown";
      const chunkIdx = c.chunk_index ?? "?";
      const score = typeof c.score === "number" ? c.score.toFixed(3) : "n/a";
      const quote = (c.quote || "").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      html += `<li><div><strong>${docName}</strong> (chunk ${chunkIdx}, score ${score})</div><div>${quote}</div></li>`;
    });
    html += "</ul>";
  }

  wrap.innerHTML = html;
  box.appendChild(wrap);
  box.scrollTop = box.scrollHeight;
}

function renderHistoryItems(items, append = false) {
  const box = document.getElementById("chatHistory");
  if (!append) {
    box.innerHTML = "";
  }

  if (!Array.isArray(items) || !items.length) {
    if (!append) {
      box.innerHTML = "История пуста";
    }
    return;
  }

  items.forEach((entry) => {
    const item = document.createElement("div");
    item.className = "chat-history-item";
    const ts = entry.timestamp ? new Date(entry.timestamp).toLocaleString() : "";
    const src = Array.isArray(entry.sources) && entry.sources.length
      ? entry.sources.join(", ")
      : "-";
    item.innerHTML = `
      <div class="chat-history-time">${ts}</div>
      <div><strong>Вы:</strong> ${entry.user_message || ""}</div>
      <div><strong>AI:</strong> ${entry.bot_response || ""}</div>
      <div class="chat-history-sources">sources: ${src}</div>
    `;
    box.appendChild(item);
  });
}

function getHistoryLimit() {
  const select = document.getElementById("historyLimit");
  const v = Number(select?.value || 20);
  if (!Number.isInteger(v) || v < 1) return 20;
  return Math.min(v, 100);
}

async function checkSession() {
  if (window.SiteAuth?.refreshSession) {
    await window.SiteAuth.refreshSession();
    currentUser = window.SiteAuth.getCurrentUser();
  } else {
    const response = await apiFetch("/me");
    if (!response.ok) {
      currentUser = null;
    } else {
      currentUser = await response.json();
    }
  }

  if (!currentUser) {
    setStatus("Не авторизован. Нажмите \"Зайти\" в шапке.");
    return null;
  }

  setStatus(`Вход выполнен: ${currentUser.username} (${currentUser.role})`);
  return currentUser;
}

async function loadHistory(reset = true) {
  if (!currentUser) {
    document.getElementById("chatHistory").innerHTML = "Войдите, чтобы увидеть историю";
    document.getElementById("chatHistoryMeta").textContent = "";
    return;
  }

  const limit = getHistoryLimit();
  if (reset) {
    historyOffset = 0;
  }

  const url = `/chat/history?limit=${limit}&offset=${historyOffset}`;
  const response = await apiFetch(url);

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    document.getElementById("chatHistory").innerHTML = `Ошибка истории: ${payload.detail || response.status}`;
    return;
  }

  const payload = await response.json();
  const items = payload.items || [];
  renderHistoryItems(items, !reset);

  historyOffset += items.length;
  const backend = payload.storage_backend || "unknown";
  const hasMore = Boolean(payload.has_more);
  document.getElementById("chatHistoryMeta").textContent =
    `history: ${historyOffset}/${payload.total || 0}, backend: ${backend}`;

  const loadMoreBtn = document.getElementById("loadMoreHistoryBtn");
  loadMoreBtn.disabled = !hasMore;
}

async function sendMessage() {
  const input = document.getElementById("chatInput");
  const query = input.value.trim();
  if (!query) return;

  if (!currentUser) {
    setStatus("Сначала войдите в аккаунт");
    return;
  }

  addMessage("user", `Вы: ${query}`);
  input.value = "";

  const response = await apiFetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query })
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    addMessage("assistant", `Ошибка: ${payload.detail || response.status}`);
    return;
  }

  const payload = await response.json();
  addMessage("assistant", payload.answer || "Пустой ответ");
  addSources(payload.citations || [], payload.sources || []);
  await loadHistory(true);
}

document.addEventListener("DOMContentLoaded", async () => {
  document.getElementById("sendChatBtn").addEventListener("click", sendMessage);
  document.getElementById("loadHistoryBtn").addEventListener("click", () => loadHistory(true));
  document.getElementById("loadMoreHistoryBtn").addEventListener("click", () => loadHistory(false));
  document.getElementById("historyLimit").addEventListener("change", () => loadHistory(true));
  document.getElementById("chatInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  });

  window.addEventListener("site-auth-changed", async (event) => {
    currentUser = event.detail?.user || null;
    historyOffset = 0;

    if (currentUser) {
      setStatus(`Вход выполнен: ${currentUser.username} (${currentUser.role})`);
      await loadHistory(true);
      return;
    }

    setStatus("Не авторизован. Нажмите \"Зайти\" в шапке.");
    document.getElementById("chatHistory").innerHTML = "";
    document.getElementById("chatHistoryMeta").textContent = "";
  });

  await checkSession();
  if (currentUser) {
    await loadHistory(true);
  }
  await loadStats();
});
