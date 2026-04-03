const CYRILLIC = "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЩЭЮЯ".split("");

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

function normalizePeople(rows) {
  return rows.map((row) => ({
    id: row.id,
    name: row.full_name,
    birth_year: row.birth_year,
    death_year: row.death_year,
    occupation: row.occupation,
    region: row.region
  }));
}

let allPeople = [];

function getFilterValues() {
  const region = document.getElementById("filterRegion")?.value || "";
  const year = document.getElementById("filterYear")?.value || "";
  return { region, year };
}

function applyFilters(people) {
  const { region, year } = getFilterValues();
  return people.filter((p) => {
    const byRegion = !region || (p.region || "") === region;
    const byYear = !year || String(p.birth_year || "") === year;
    return byRegion && byYear;
  });
}

function fillFilterOptions(people) {
  const regionSelect = document.getElementById("filterRegion");
  const yearSelect = document.getElementById("filterYear");
  if (!regionSelect || !yearSelect) return;

  const regionOptions = Array.from(
    new Set(people.map((p) => (p.region || "").trim()).filter(Boolean))
  ).sort((a, b) => a.localeCompare(b, "ru"));

  const yearOptions = Array.from(
    new Set(people.map((p) => p.birth_year).filter((v) => Number.isInteger(v)))
  ).sort((a, b) => a - b);

  const currentRegion = regionSelect.value;
  const currentYear = yearSelect.value;

  regionSelect.innerHTML = '<option value="">Все регионы</option>';
  yearSelect.innerHTML = '<option value="">Все годы</option>';

  regionOptions.forEach((region) => {
    const option = document.createElement("option");
    option.value = region;
    option.textContent = region;
    regionSelect.appendChild(option);
  });

  yearOptions.forEach((year) => {
    const option = document.createElement("option");
    option.value = String(year);
    option.textContent = String(year);
    yearSelect.appendChild(option);
  });

  if (currentRegion) regionSelect.value = currentRegion;
  if (currentYear) yearSelect.value = currentYear;
}

function groupByLetter(people) {
  const groups = {};
  CYRILLIC.forEach((l) => {
    groups[l] = [];
  });

  people.forEach((p) => {
    const first = (p.name || "").charAt(0).toUpperCase();
    if (groups[first]) {
      groups[first].push(p);
    }
  });

  CYRILLIC.forEach((l) => {
    groups[l].sort((a, b) => (a.name || "").localeCompare(b.name || "", "ru"));
  });

  return groups;
}

function renderAlphabetBar(groups) {
  const bar = document.getElementById("alphabetBar");
  bar.innerHTML = "";

  CYRILLIC.forEach((letter) => {
    const a = document.createElement("a");
    a.href = `#letter-${letter}`;
    a.textContent = letter;
    if (!groups[letter] || groups[letter].length === 0) {
      a.classList.add("disabled");
      a.removeAttribute("href");
    }
    bar.appendChild(a);
  });
}

function renderRegistry(groups) {
  const container = document.getElementById("registryList");
  container.innerHTML = "";

  CYRILLIC.forEach((letter) => {
    const people = groups[letter] || [];
    if (!people.length) return;

    const section = document.createElement("section");
    section.className = "letter-section";

    const heading = document.createElement("h2");
    heading.className = "letter-heading";
    heading.id = `letter-${letter}`;
    heading.textContent = letter;
    section.appendChild(heading);

    const ul = document.createElement("ul");
    ul.className = "name-list";

    people.forEach((p) => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = `index.html?id=${p.id}`;
      a.textContent = p.name;

      const span = document.createElement("span");
      span.className = "name-id";
      span.textContent = ` #${p.id}`;
      a.appendChild(span);

      li.appendChild(a);
      ul.appendChild(li);
    });

    section.appendChild(ul);
    container.appendChild(section);
  });
}

async function fetchPeople(query = "") {
  const url = query
    ? apiUrl(`/api/persons?q=${encodeURIComponent(query)}&limit=1000`)
    : apiUrl("/api/persons?limit=1000");

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return normalizePeople(await response.json());
}

async function loadAndRender(query = "") {
  const registry = document.getElementById("registryList");
  registry.innerHTML = "Загрузка...";

  try {
    allPeople = await fetchPeople(query);
    fillFilterOptions(allPeople);

    const people = applyFilters(allPeople);
    const groups = groupByLetter(people);
    renderAlphabetBar(groups);
    renderRegistry(groups);

    if (!people.length) {
      registry.innerHTML = "Данные не найдены";
    }
  } catch (err) {
    registry.innerHTML = `Ошибка загрузки: ${err.message}`;
  }
}

function renderWithCurrentFilters() {
  const registry = document.getElementById("registryList");
  const people = applyFilters(allPeople);
  const groups = groupByLetter(people);
  renderAlphabetBar(groups);
  renderRegistry(groups);

  if (!people.length) {
    registry.innerHTML = "Данные не найдены";
  }
}

function setupSearch() {
  const input = document.getElementById("searchInput");
  const btn = document.getElementById("searchBtn");

  const doSearch = () => {
    const query = input.value.trim();
    loadAndRender(query);
  };

  btn.addEventListener("click", doSearch);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") doSearch();
  });
}

function setupFilters() {
  const applyBtn = document.querySelector(".filter-apply-btn");
  const regionSelect = document.getElementById("filterRegion");
  const yearSelect = document.getElementById("filterYear");

  if (!applyBtn || !regionSelect || !yearSelect) return;

  applyBtn.addEventListener("click", renderWithCurrentFilters);
  regionSelect.addEventListener("change", renderWithCurrentFilters);
  yearSelect.addEventListener("change", renderWithCurrentFilters);
}

document.addEventListener("DOMContentLoaded", () => {
  setupSearch();
  setupFilters();
  loadAndRender();
});
