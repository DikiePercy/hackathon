let currentUser = null;
const MAX_IMAGE_BYTES = 2 * 1024 * 1024;
const MAX_DOCUMENT_BYTES = 3 * 1024 * 1024;

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
    setStatus(tr("suggestions_desc_2", "Not authorized. Click \"Login\" in the header."));
    return;
  }

  setStatus(tf("auth_logged_in_as", "Logged in: {username} ({role})", {
    username: currentUser.username,
    role: currentUser.role,
  }));
}

async function sendSuggestion() {
  if (!currentUser) {
    setStatus(tr("chat_login_first", "Please sign in first"));
    return;
  }

  const suggestionKind = (readText("suggestionKind") || "create").toLowerCase();
  const targetPersonId = parseYear("targetPersonId");
  const documentText = readText("documentText");

  const fullName = readText("fullName");
  const birthYear = parseYear("birthYear");
  if (suggestionKind !== "document" && (!fullName || !birthYear)) {
    setStatus(tr("suggestions_required_name_year", "Full name and birth year are required"));
    return;
  }

  if ((suggestionKind === "update" || suggestionKind === "document") && !targetPersonId) {
    setStatus(tr("suggestions_need_target_id", "For update/document, provide existing entry ID"));
    return;
  }

  const photoInput = document.getElementById("photoFile");
  const photo = photoInput?.files?.[0] || null;
  if (photo && photo.size >= MAX_IMAGE_BYTES) {
    setStatus(tr("suggestions_image_limit", "Image size must be less than 2 MB"));
    return;
  }

  const documentInput = document.getElementById("documentFile");
  const documentFile = documentInput?.files?.[0] || null;
  if (documentFile && documentFile.size >= MAX_DOCUMENT_BYTES) {
    setStatus(tr("suggestions_doc_limit", "Document size must be less than 3 MB"));
    return;
  }

  if (documentFile) {
    const name = (documentFile.name || "").toLowerCase();
    if (!(name.endsWith(".txt") || name.endsWith(".md") || name.endsWith(".markdown"))) {
      setStatus(tr("suggestions_doc_format", "Document must be in .txt or .md format"));
      return;
    }
  }

  if (suggestionKind === "document" && !documentText && !documentFile) {
    setStatus(tr("suggestions_doc_required", "For document mode, add text or a .txt/.md file"));
    return;
  }

  const form = new FormData();
  form.set("suggestion_kind", suggestionKind);
  form.set("full_name", fullName || `Документ к записи #${targetPersonId || "?"}`);
  form.set("birth_year", String(birthYear || 1900));
  form.set("death_year", String(parseYear("deathYear") || ""));
  form.set("nationality", readText("nationality") || "");
  form.set("region", readText("region") || "");
  form.set("district", readText("district") || "");
  form.set("occupation", readText("occupation") || "");
  form.set("charge", readText("charge") || "");
  form.set("sentence", readText("sentence") || "");
  form.set("arrest_date", readText("arrestDate") || "");
  form.set("sentence_date", readText("sentenceDate") || "");
  form.set("rehabilitation_date", readText("rehabilitationDate") || "");
  form.set("biography", readText("biography") || "");
  form.set("document_text", documentText || "");
  form.set("source", readText("source") || "");
  form.set("status", readText("status") || "");
  if (targetPersonId) {
    form.set("target_person_id", String(targetPersonId));
  }
  if (photo) {
    form.set("photo", photo);
  }
  if (documentFile) {
    form.set("document_file", documentFile);
  }

  const response = await apiFetch("/suggestions/with-photo", {
    method: "POST",
    body: form
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    setStatus(`Ошибка отправки: ${body.detail || response.status}`);
    return;
  }

  const created = await response.json();
  setStatus(tf("suggestions_sent", "Suggestion sent: #{id} ({kind})", {
    id: created.id,
    kind: created.suggestion_kind,
  }));
  if (photoInput) {
    photoInput.value = "";
  }
  if (documentInput) {
    documentInput.value = "";
  }
  await loadMySuggestions();
}

async function findExistingPerson() {
  const query = readText("existingSearch");
  const resultEl = document.getElementById("existingSearchResult");
  if (!query) {
    resultEl.textContent = tr("suggestions_search_enter", "Enter text to search entries");
    return;
  }

  const response = await apiFetch(`/api/persons/search?q=${encodeURIComponent(query)}&limit=5`);
  if (!response.ok) {
    resultEl.textContent = tr("suggestions_search_failed", "Search failed");
    return;
  }

  const items = await response.json();
  if (!items.length) {
    resultEl.textContent = tr("suggestions_search_empty", "Nothing found");
    return;
  }

  const first = items[0];
  document.getElementById("targetPersonId").value = String(first.id);
  document.getElementById("fullName").value = first.full_name || "";
  document.getElementById("birthYear").value = String(first.birth_year || "");
  resultEl.textContent = tf("suggestions_search_found", "Found: {name} (#{id}). ID was applied.", {
    name: first.full_name,
    id: first.id,
  });
}

async function loadMySuggestions() {
  if (!currentUser) {
    document.getElementById("mySuggestionsList").innerHTML = tr("suggestions_login_to_view", "Sign in to view");
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
    container.innerHTML = tr("suggestions_no_items", "No suggestions yet");
    return;
  }

  container.innerHTML = "";
  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "admin-card-row";
    const photoLabel = item.photo_url ? ` | фото: есть` : " | фото: placeholder";
    const docLabel = item.document_filename ? ` | doc: ${item.document_filename}` : (item.document_text ? " | doc: text" : "");
    row.innerHTML = `<span><strong>${item.full_name}</strong> (${item.birth_year}) #${item.id}<br><small>mode: ${item.suggestion_kind}${item.target_person_id ? ` | target: #${item.target_person_id}` : ""} | state: ${item.state}${item.moderation_comment ? ` | ${item.moderation_comment}` : ""}${photoLabel}${docLabel}</small></span>`;
    container.appendChild(row);
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  document.getElementById("findExistingBtn").addEventListener("click", findExistingPerson);
  document.getElementById("sendSuggestionBtn").addEventListener("click", sendSuggestion);
  document.getElementById("loadMySuggestionsBtn").addEventListener("click", loadMySuggestions);

  window.addEventListener("site-auth-changed", async (event) => {
    currentUser = event.detail?.user || null;
    if (currentUser) {
      setStatus(tf("auth_logged_in_as", "Logged in: {username} ({role})", {
        username: currentUser.username,
        role: currentUser.role,
      }));
      await loadMySuggestions();
      return;
    }

    setStatus(tr("suggestions_desc_2", "Not authorized. Click \"Login\" in the header."));
    document.getElementById("mySuggestionsList").innerHTML = "";
  });

  window.addEventListener("site-language-changed", async () => {
    if (!currentUser) {
      setStatus(tr("suggestions_desc_2", "Not authorized. Click \"Login\" in the header."));
      return;
    }
    setStatus(tf("auth_logged_in_as", "Logged in: {username} ({role})", {
      username: currentUser.username,
      role: currentUser.role,
    }));
    await loadMySuggestions();
  });

  await checkSession();
  if (currentUser) {
    await loadMySuggestions();
  }
});
