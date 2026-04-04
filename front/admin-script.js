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

function tr(key, fallback) {
  return window.AppI18n?.t?.(key) || fallback;
}

function tf(key, fallback, vars = {}) {
  let text = tr(key, fallback);
  Object.entries(vars).forEach(([name, value]) => {
    text = text.replaceAll(`{${name}}`, String(value ?? ""));
  });
  return text;
}

function apiUrl(path) {
  return ADMIN_API_BASE ? `${ADMIN_API_BASE}${path}` : path;
}

function applyAiConfigToInputs(cfg = {}) {
  document.getElementById("llmProvider").value = cfg.rag_llm_provider || "gemini";
  document.getElementById("embeddingProvider").value = cfg.rag_embedding_provider || "gemini";
  document.getElementById("geminiModel").value = cfg.rag_gemini_model || "";
  document.getElementById("openaiModel").value = cfg.rag_openai_model || "gpt-4o-mini";
  document.getElementById("claudeModel").value = cfg.rag_claude_model || "";
  document.getElementById("groqModel").value = cfg.rag_groq_model || "groq/compound";
  document.getElementById("geminiEmbeddingModel").value = cfg.rag_gemini_embedding_model || "";
  document.getElementById("openaiEmbeddingModel").value = cfg.rag_openai_embedding_model || "";

  // Backend returns masked secrets; keep them visible in masked form to show persistence.
  document.getElementById("geminiApiKey").value = cfg.gemini_api_key || "";
  document.getElementById("openaiApiKey").value = cfg.openai_api_key || "";
  document.getElementById("anthropicApiKey").value = cfg.anthropic_api_key || "";
  document.getElementById("groqApiKey").value = cfg.groq_api_key || "";
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

async function checkSession({ refresh = false } = {}) {
  let me = null;
  if (window.SiteAuth?.getCurrentUser) {
    if (refresh && window.SiteAuth?.refreshSession) {
      await window.SiteAuth.refreshSession();
    }
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
    setAdminStatus(tr("admin_session_inactive", "Session inactive. Click \"Login as admin\"."));
    return null;
  }

  if (me.role !== "admin") {
    currentAdmin = me;
    setAdminProtectedVisible(false);
    setAdminStatus(tf("admin_login_not_admin", "Signed in as {username}, but role is not admin", { username: me.username }));
    return me;
  }

  currentAdmin = me;
  setAdminProtectedVisible(true);
  setAdminStatus(tf("admin_logged_admin", "Signed in as admin: {username}", { username: me.username }));
  return me;
}

async function createCard() {
  if (!currentAdmin || currentAdmin.role !== "admin") {
    setAdminStatus(tr("admin_need_auth", "Admin authorization is required"));
    return;
  }

  const name = document.getElementById("createName").value.trim();
  if (!name) {
    setAdminStatus(tr("admin_need_name", "Enter full name to create a card"));
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
    setAdminStatus(tr("admin_select_json", "Select a JSON file"));
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
    setAdminStatus(tf("admin_import_done", "Import complete: created {created}, skipped {skipped}", {
      created: body.created,
      skipped: body.skipped_duplicates,
    }));
    await loadCards();
  } catch (err) {
    setAdminStatus(`Ошибка импорта: ${err.message}`);
  }
}

async function importBundledSeeds() {
  if (!currentAdmin || currentAdmin.role !== "admin") {
    setAdminStatus(tr("admin_need_auth", "Admin authorization is required"));
    return;
  }

  const response = await apiFetch("/cards/import/seed/examples", {
    method: "POST"
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    setAdminStatus(`Ошибка импорта встроенных seed: ${body.detail || response.status}`);
    return;
  }

  const body = await response.json();
  setAdminStatus(tf("admin_bundled_import_done", "Bundled import: created {created}, skipped {skipped}, files: {files}", {
    created: body.created,
    skipped: body.skipped_duplicates,
    files: (body.files || []).join(", "),
  }));
  await loadCards();
}

async function importDocumentsBatch() {
  if (!currentAdmin || currentAdmin.role !== "admin") {
    setAdminStatus(tr("admin_need_auth", "Admin authorization is required"));
    return;
  }

  const input = document.getElementById("batchDocuments");
  const personIdRaw = document.getElementById("batchPersonId").value.trim();
  const files = Array.from(input.files || []);

  if (!files.length) {
    setAdminStatus("Выберите хотя бы один файл (.txt/.md)");
    return;
  }

  if (files.length > 20) {
    setAdminStatus("Можно загрузить максимум 20 файлов за один раз");
    return;
  }

  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  if (personIdRaw) {
    formData.append("person_id", personIdRaw);
  }

  const response = await apiFetch("/api/documents/upload-batch", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    setAdminStatus(`Ошибка пакетного импорта: ${body.detail || response.status}`);
    return;
  }

  const body = await response.json();
  const imported = Number(body.imported || 0);
  const failed = Number(body.failed || 0);
  const vectorFailed = Number(body.vector_failed || 0);
  setAdminStatus(`Пакетный импорт завершен: загружено ${imported}, ошибок ${failed}, без векторов ${vectorFailed}`);

  input.value = "";
  await loadCards();
}

async function loadAiRuntimeConfig() {
  if (!currentAdmin || currentAdmin.role !== "admin") {
    setAdminStatus(tr("admin_need_auth", "Admin authorization is required"));
    return;
  }

  const response = await apiFetch("/admin/ai/runtime-config");
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    setAdminStatus(`Ошибка чтения AI настроек: ${body.detail || response.status}`);
    return;
  }

  const payload = await response.json();
  applyAiConfigToInputs(payload.config || {});

  setAdminStatus(tr("admin_ai_loaded", "AI settings loaded"));
}

async function saveAiRuntimeConfig() {
  if (!currentAdmin || currentAdmin.role !== "admin") {
    setAdminStatus(tr("admin_need_auth", "Admin authorization is required"));
    return;
  }

  const payload = {
    rag_llm_provider: document.getElementById("llmProvider").value,
    rag_embedding_provider: document.getElementById("embeddingProvider").value,
    rag_gemini_model: document.getElementById("geminiModel").value.trim(),
    rag_openai_model: document.getElementById("openaiModel").value.trim(),
    rag_claude_model: document.getElementById("claudeModel").value.trim(),
    rag_groq_model: document.getElementById("groqModel").value.trim(),
    rag_gemini_embedding_model: document.getElementById("geminiEmbeddingModel").value.trim(),
    rag_openai_embedding_model: document.getElementById("openaiEmbeddingModel").value.trim(),
  };

  const geminiKey = document.getElementById("geminiApiKey").value.trim();
  const openaiKey = document.getElementById("openaiApiKey").value.trim();
  const anthropicKey = document.getElementById("anthropicApiKey").value.trim();
  const groqKey = document.getElementById("groqApiKey").value.trim();
  if (geminiKey) payload.gemini_api_key = geminiKey;
  if (openaiKey) payload.openai_api_key = openaiKey;
  if (anthropicKey) payload.anthropic_api_key = anthropicKey;
  if (groqKey) payload.groq_api_key = groqKey;

  const response = await apiFetch("/admin/ai/runtime-config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    setAdminStatus(`Ошибка сохранения AI настроек: ${body.detail || response.status}`);
    return;
  }

  const body = await response.json().catch(() => ({}));
  if (body?.config) {
    applyAiConfigToInputs(body.config);
  }
  setAdminStatus(tr("admin_ai_saved", "AI settings saved"));
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
    container.innerHTML = tr("admin_cards_login_needed", "Login as admin to view cards");
    return;
  }

  container.innerHTML = tr("common_loading", "Loading...");
  const response = await apiFetch("/cards");

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    container.innerHTML = `Ошибка: ${body.detail || response.status}`;
    return;
  }

  const cards = await response.json();
  if (!cards.length) {
    container.innerHTML = tr("admin_no_cards", "No cards");
    return;
  }

  container.innerHTML = "";
  cards.forEach((card) => {
    const row = document.createElement("div");
    row.className = "admin-card-row";
    row.innerHTML = `<span><strong>${card.name}</strong> (${card.birth_year || "?"}) #${card.id}</span>`;

    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = tr("common_delete", "Delete");
    btn.addEventListener("click", () => deleteCard(card.id));

    row.appendChild(btn);
    container.appendChild(row);
  });
}

async function moderationAction(id, action) {
  const comment = window.prompt(tr("admin_prompt_comment", "Moderator comment (optional):"), "") || "";
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
  setAdminStatus(body.message || tr("admin_moderation_done", "Moderation complete"));
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
    container.innerHTML = tr("admin_suggestions_login_needed", "Login as admin for moderation");
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
    container.innerHTML = tr("admin_no_suggestions", "No suggestions");
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
      approveBtn.textContent = tr("common_approve", "Approve");
      approveBtn.addEventListener("click", () => moderationAction(item.id, "approve"));
      actions.appendChild(approveBtn);

      const rejectBtn = document.createElement("button");
      rejectBtn.type = "button";
      rejectBtn.textContent = tr("common_reject", "Reject");
      rejectBtn.addEventListener("click", () => moderationAction(item.id, "reject"));
      actions.appendChild(rejectBtn);
    }

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.textContent = tr("common_delete", "Delete");
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
  document.getElementById("seedExamplesImportBtn").addEventListener("click", importBundledSeeds);
  document.getElementById("batchImportDocsBtn").addEventListener("click", importDocumentsBatch);
  document.getElementById("createCardBtn").addEventListener("click", createCard);
  document.getElementById("refreshCardsBtn").addEventListener("click", loadCards);
  document.getElementById("loadSuggestionsBtn").addEventListener("click", loadSuggestions);
  document.getElementById("loadAiConfigBtn").addEventListener("click", loadAiRuntimeConfig);
  document.getElementById("saveAiConfigBtn").addEventListener("click", saveAiRuntimeConfig);

  window.addEventListener("site-auth-changed", async () => {
    const me = await checkSession({ refresh: false });
    if (me?.role === "admin") {
      await loadCards();
      await loadSuggestions();
      await loadAiRuntimeConfig();
      return;
    }

    document.getElementById("adminCardsList").innerHTML = "";
    document.getElementById("adminSuggestionsList").innerHTML = "";
  });

  const me = await checkSession({ refresh: true });
  if (me?.role === "admin") {
    await loadCards();
    await loadSuggestions();
    await loadAiRuntimeConfig();
  }

  window.addEventListener("site-language-changed", async () => {
    const me2 = await checkSession({ refresh: false });
    if (me2?.role === "admin") {
      await loadCards();
      await loadSuggestions();
    }
  });
});
