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

function apiUrl(path) {
  return API_BASE ? `${API_BASE}${path}` : path;
}

function formatDate(dateStr) {
  if (!dateStr) return "-";
  const parts = dateStr.split("-");
  if (parts.length === 3) {
    return `${parts[2]}.${parts[1]}.${parts[0]}`;
  }
  return dateStr;
}

function addRow(tbody, label, value) {
  const tr = document.createElement("tr");
  const td1 = document.createElement("td");
  td1.textContent = label;
  const td2 = document.createElement("td");
  td2.textContent = value || "-";
  tr.appendChild(td1);
  tr.appendChild(td2);
  tbody.appendChild(tr);
}

function renderPerson(data) {
  document.getElementById("personName").textContent = data.full_name || "Без имени";
  const years = [data.birth_year, data.death_year].filter(Boolean).join(" - ");
  document.getElementById("personYears").textContent = years ? `(${years})` : "";

  const photoEl = document.getElementById("personPhoto");
  photoEl.src = data.photo_url || "";
  photoEl.alt = "Портрет";

  const tbody = document.querySelector("#metaTable tbody");
  tbody.innerHTML = "";
  addRow(tbody, "Год рождения", data.birth_year);
  addRow(tbody, "Год смерти", data.death_year);

  Object.entries(META_LABELS).forEach(([key, label]) => {
    const value = key.includes("date") ? formatDate(data[key]) : data[key];
    addRow(tbody, label, value);
  });

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
    const p = document.createElement("p");
    p.textContent = "Документы пока не загружены";
    grid.appendChild(p);
  }

  const bioDiv = document.getElementById("biographyText");
  bioDiv.innerHTML = "";
  if (!data.biography) {
    bioDiv.textContent = "Биография отсутствует";
    return;
  }

  data.biography
    .split(/\n+/)
    .map((text) => text.trim())
    .filter(Boolean)
    .forEach((text) => {
      const p = document.createElement("p");
      p.textContent = text;
      bioDiv.appendChild(p);
    });
}

function renderError(message) {
  document.getElementById("personName").textContent = "Ошибка загрузки";
  document.getElementById("personYears").textContent = "";
  document.getElementById("biographyText").textContent = message;
}

async function loadPerson() {
  const params = new URLSearchParams(window.location.search);
  const personId = Number(params.get("id")) || 1;

  try {
    const response = await fetch(apiUrl(`/api/person/${personId}`));
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    renderPerson(data);
  } catch (err) {
    renderError(`Не удалось получить данные: ${err.message}`);
  }
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
    renderError(`Ошибка поиска: ${err.message}`);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("searchBtn");
  const input = document.getElementById("searchInput");

  btn.addEventListener("click", searchPerson);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") searchPerson();
  });

  loadPerson();
});
