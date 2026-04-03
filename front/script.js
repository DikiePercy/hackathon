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
  photoEl.src = data.photo_url || "https://via.placeholder.com/250x350.png?text=Archive";
  photoEl.alt = "Портрет: " + data.full_name;

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
  }
}

function showLoadError(message) {
  document.getElementById("personName").textContent = "Ошибка загрузки";
  document.getElementById("personYears").textContent = message;
  document.getElementById("biographyText").textContent = "Проверьте доступность backend API.";
}

async function loadPerson() {
  const params = new URLSearchParams(window.location.search);
  const personId = Number(params.get("id")) || 1;
  const response = await fetch(`${API_BASE}/api/person/${personId}`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const data = await response.json();
  renderPerson(data);
}

async function searchPerson() {
  const input = document.getElementById("searchInput");
  const query = (input.value || "").trim();
  if (!query) {
    await loadPerson();
    return;
  }

  const response = await fetch(`${API_BASE}/api/persons/search?q=${encodeURIComponent(query)}&limit=5`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

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
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("searchBtn");
  const input = document.getElementById("searchInput");

  btn.addEventListener("click", async () => {
    try {
      await searchPerson();
    } catch (err) {
      showLoadError(`Поиск недоступен: ${err.message}`);
    }
  });

  input.addEventListener("keydown", async (event) => {
    if (event.key === "Enter") {
      try {
        await searchPerson();
      } catch (err) {
        showLoadError(`Поиск недоступен: ${err.message}`);
      }
    }
  });

  loadPerson().catch((err) => {
    showLoadError(err.message);
  });
});
