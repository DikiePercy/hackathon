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
  return "http://localhost:8000";
}

const API_BASE = resolveApiBase();

function setPortraitVisible(visible) {
  const photoWrap = document.querySelector(".profile-photo");
  const photoEl = document.getElementById("personPhoto");
  if (photoWrap) {
    photoWrap.style.display = visible ? "block" : "none";
  }
  if (!visible && photoEl) {
    photoEl.removeAttribute("src");
  }
}

function formatDate(dateStr) {
  if (!dateStr) return "-";
  const parts = String(dateStr).split("-");
  if (parts.length === 3) {
    return `${parts[2]}.${parts[1]}.${parts[0]}`;
  }
  return dateStr;
}

function renderPerson(data) {
  document.getElementById("personName").textContent = data.full_name;
  const years = [data.birth_year, data.death_year].filter(Boolean).join(" - ");
  document.getElementById("personYears").textContent = years ? `(${years})` : "";

  const photoEl = document.getElementById("personPhoto");
  if (data.photo_url) {
    setPortraitVisible(true);
    photoEl.src = data.photo_url;
    photoEl.onerror = () => {
      photoEl.onerror = null;
      setPortraitVisible(false);
    };
    photoEl.alt = "Портрет: " + data.full_name;
  } else {
    setPortraitVisible(false);
  }

  const tbody = document.querySelector("#metaTable tbody");
  tbody.innerHTML = "";

  const addRow = (label, value) => {
    const tr = document.createElement("tr");
    const td1 = document.createElement("td");
    td1.textContent = label;
    const td2 = document.createElement("td");
    td2.textContent = value || "-";
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

  const grid = document.getElementById("documentsGrid");
  grid.innerHTML = "";
  if (Array.isArray(data.documents) && data.documents.length > 0) {
    data.documents.forEach((url, i) => {
      const div = document.createElement("div");
      div.className = "doc-thumb";
      const img = document.createElement("img");
      img.src = url;
      img.alt = `Документ ${i + 1}`;
      div.appendChild(img);
      grid.appendChild(div);
    });
  } else {
    grid.textContent = "Документы пока не добавлены";
  }

  const bioDiv = document.getElementById("biographyText");
  bioDiv.innerHTML = "";
  if (data.biography) {
    const paragraphs = String(data.biography).split(/\n{2,}|(?<=\.)\s+(?=[А-ЯA-Z])/);
    paragraphs.forEach((text) => {
      text = text.trim();
      if (!text) return;
      const p = document.createElement("p");
      p.textContent = text;
      bioDiv.appendChild(p);
    });
  } else {
    bioDiv.textContent = "Биография пока не добавлена";
  }
}

function showNoDataState() {
  document.getElementById("personName").textContent = "Пока нет данных";
  document.getElementById("personYears").textContent = "";

  setPortraitVisible(false);

  const tbody = document.querySelector("#metaTable tbody");
  tbody.innerHTML = "";

  const grid = document.getElementById("documentsGrid");
  grid.innerHTML = "";
  grid.textContent = "Документы пока не добавлены";

  const bioDiv = document.getElementById("biographyText");
  bioDiv.innerHTML = "";
  bioDiv.textContent = "В базе пока нет данных.";
}

async function loadStats() {
  const personsEl = document.getElementById("statsPersons");
  const docsEl = document.getElementById("statsDocuments");

  try {
    const response = await fetch(`${API_BASE}/api/stats`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const stats = await response.json();
    personsEl.textContent = String(stats.persons ?? 0);
    docsEl.textContent = String(stats.documents ?? 0);
  } catch (_err) {
    personsEl.textContent = "-";
    docsEl.textContent = "-";
  }
}

async function resolveInitialPersonId() {
  const params = new URLSearchParams(window.location.search);
  const fromQuery = Number(params.get("id"));
  if (Number.isInteger(fromQuery) && fromQuery > 0) {
    return fromQuery;
  }

  try {
    const response = await fetch(`${API_BASE}/api/persons?limit=1&offset=0`);
    if (!response.ok) {
      return null;
    }
    const people = await response.json();
    if (!Array.isArray(people) || people.length === 0) {
      return null;
    }
    return Number(people[0].id) || null;
  } catch (_err) {
    return null;
  }
}

async function loadPerson(personId) {
  if (!personId) {
    showNoDataState();
    return;
  }

  const response = await fetch(`${API_BASE}/api/person/${personId}`);
  if (response.status === 404) {
    showNoDataState();
    return;
  }
  if (!response.ok) {
    showNoDataState();
    return;
  }
  const data = await response.json();
  renderPerson(data);
}

async function searchPerson() {
  const input = document.getElementById("searchInput");
  const query = (input.value || "").trim();
  if (!query) {
    const personId = await resolveInitialPersonId();
    await loadPerson(personId);
    return;
  }

  const response = await fetch(`${API_BASE}/api/persons/search?q=${encodeURIComponent(query)}&limit=5`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const results = await response.json();
  if (!results.length) {
    showNoDataState();
    return;
  }

  const person = results[0];
  const url = new URL(window.location.href);
  url.searchParams.set("id", String(person.id));
  history.replaceState(null, "", url.toString());
  await loadPerson(Number(person.id));
}

function bindCardAction(element, action) {
  if (!element) return;
  element.addEventListener("click", action);
  element.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      action();
    }
  });
}

function setupHeroCards() {
  const searchInput = document.getElementById("searchInput");

  bindCardAction(document.getElementById("heroFindCard"), () => {
    searchInput.focus();
    searchInput.scrollIntoView({ behavior: "smooth", block: "center" });
  });

  bindCardAction(document.getElementById("heroSuggestCard"), () => {
    window.location.href = "suggestions.html";
  });

  bindCardAction(document.getElementById("heroHelpCard"), () => {
    window.location.href = "contacts.html";
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("searchBtn");
  const input = document.getElementById("searchInput");

  btn.addEventListener("click", async () => {
    await searchPerson();
  });

  input.addEventListener("keydown", async (event) => {
    if (event.key === "Enter") {
      await searchPerson();
    }
  });

  setupHeroCards();
  loadStats();
  resolveInitialPersonId().then((personId) => loadPerson(personId));
});
