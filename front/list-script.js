const CYRILLIC = "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЩЭЮЯ".split("");
const LATIN = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");
const DEFAULT_ALPHABET = [...CYRILLIC, ...LATIN];
let allPeople = [];
let activeAlphabet = [...DEFAULT_ALPHABET];

function tr(key, fallback) {
  return window.AppI18n?.t?.(key) || fallback;
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

function mapPerson(person) {
  const name = person.full_name || "";
  const region = person.region || "";
  const district = person.district || "";
  const occupation = person.occupation || "";
  const charge = person.charge || "";
  const birthYear = person.birth_year || "";
  const deathYear = person.death_year || "";

  return {
    id: person.id,
    name,
    birth_year: person.birth_year,
    death_year: person.death_year,
    region,
    district,
    occupation,
    charge,
    search_blob: `${name} ${region} ${district} ${occupation} ${charge} ${birthYear} ${deathYear}`.toLowerCase()
  };
}

function getFirstLetter(name) {
  const first = (name || "").trim().charAt(0).toUpperCase();
  if (!first) return "#";
  if (DEFAULT_ALPHABET.includes(first)) return first;
  return "#";
}

function computeAlphabet(people) {
  const seen = new Set();
  people.forEach((p) => {
    seen.add(getFirstLetter(p.name));
  });

  const ordered = DEFAULT_ALPHABET.filter((letter) => seen.has(letter));
  if (seen.has("#")) ordered.push("#");

  return ordered.length ? ordered : [...DEFAULT_ALPHABET];
}

function groupByLetter(people, alphabet) {
  const groups = {};
  alphabet.forEach((l) => { groups[l] = []; });

  people.forEach((p) => {
    const first = getFirstLetter(p.name);
    if (groups[first]) {
      groups[first].push(p);
    }
  });

  for (const l of alphabet) {
    groups[l].sort((a, b) => a.name.localeCompare(b.name, "ru"));
  }
  return groups;
}

function renderAlphabetBar(alphabet, groups) {
  const bar = document.getElementById("alphabetBar");
  bar.innerHTML = "";
  alphabet.forEach((letter) => {
    const a = document.createElement("a");
    a.href = "#letter-" + letter;
    a.textContent = letter;
    if (!groups[letter] || groups[letter].length === 0) {
      a.classList.add("disabled");
      a.removeAttribute("href");
    }
    bar.appendChild(a);
  });
}

function renderRegistry(alphabet, groups) {
  const container = document.getElementById("registryList");
  container.innerHTML = "";

  alphabet.forEach((letter) => {
    const people = groups[letter] || [];
    if (!people.length) return;

    const section = document.createElement("section");
    section.className = "letter-section";

    const heading = document.createElement("h2");
    heading.className = "letter-heading";
    heading.id = "letter-" + letter;
    heading.textContent = letter;
    section.appendChild(heading);

    const ul = document.createElement("ul");
    ul.className = "name-list";

    people.forEach((p) => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = "index.html?id=" + p.id;

      const years = [p.birth_year, p.death_year].filter(Boolean).join("-");
      const details = [p.region, p.occupation, years].filter(Boolean).join(" | ");
      a.innerHTML = `${p.name}<span class="name-id">#${p.id}${details ? " | " + details : ""}</span>`;

      li.appendChild(a);
      ul.appendChild(li);
    });

    section.appendChild(ul);
    container.appendChild(section);
  });
}

function getFilterValues() {
  return {
    query: (document.getElementById("searchInput").value || "").trim().toLowerCase(),
    region: (document.getElementById("filterRegion").value || "").trim().toLowerCase(),
    year: (document.getElementById("filterYear").value || "").trim()
  };
}

function initSearchFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const q = (params.get("q") || "").trim();
  if (!q) return;

  const input = document.getElementById("searchInput");
  if (input) {
    input.value = q;
  }
}

function applyFilters() {
  const { query, region, year } = getFilterValues();

  const filtered = allPeople.filter((p) => {
    const byQuery = !query || p.search_blob.includes(query);
    const byRegion = !region || (p.region || "").toLowerCase() === region;
    const byYear = !year || String(p.birth_year || "") === year || String(p.death_year || "") === year;
    return byQuery && byRegion && byYear;
  });

  const groups = groupByLetter(filtered, activeAlphabet);
  renderAlphabetBar(activeAlphabet, groups);
  renderRegistry(activeAlphabet, groups);
}

function fillRegionFilter() {
  const select = document.getElementById("filterRegion");
  const existing = new Set();

  allPeople.forEach((p) => {
    if (p.region) {
      existing.add(p.region);
    }
  });

  const values = Array.from(existing)
    .map((v) => v.trim())
    .filter(Boolean)
    .sort((a, b) => a.localeCompare(b, "ru"));
  const selected = (select.value || "").trim();
  select.innerHTML = `<option value=''>${tr("filter_all_regions", "All regions")}</option>`;
  values.forEach((region) => {
    const option = document.createElement("option");
    option.value = region;
    option.textContent = region;
    select.appendChild(option);
  });
  if (selected && values.includes(selected)) {
    select.value = selected;
  }
}

function fillYearFilter() {
  const select = document.getElementById("filterYear");
  const existing = new Set();

  allPeople.forEach((p) => {
    if (p.birth_year) existing.add(String(p.birth_year));
    if (p.death_year) existing.add(String(p.death_year));
  });

  const values = Array.from(existing).sort((a, b) => Number(a) - Number(b));
  const selected = (select.value || "").trim();
  select.innerHTML = `<option value=''>${tr("filter_all_years", "All years")}</option>`;
  values.forEach((year) => {
    const option = document.createElement("option");
    option.value = year;
    option.textContent = year;
    select.appendChild(option);
  });
  if (selected && values.includes(selected)) {
    select.value = selected;
  }
}

function setupSearch() {
  const input = document.getElementById("searchInput");
  const btn = document.getElementById("searchBtn");
  const applyBtn = document.querySelector(".filter-apply-btn");

  btn.addEventListener("click", applyFilters);
  applyBtn.addEventListener("click", applyFilters);

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      applyFilters();
    }
  });
}

async function loadPeople() {
  const pageSize = 500;
  let offset = 0;
  const collected = [];

  while (true) {
    const response = await fetch(`${API_BASE}/api/persons?limit=${pageSize}&offset=${offset}`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    const page = Array.isArray(data) ? data : [];
    collected.push(...page);

    if (page.length < pageSize) {
      break;
    }
    offset += pageSize;
  }

  allPeople = collected.map(mapPerson);
  activeAlphabet = computeAlphabet(allPeople);
}

async function loadStats() {
  const personsEl = document.getElementById("statsPersons");
  const docsEl = document.getElementById("statsDocuments");
  if (!personsEl || !docsEl) return;

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

function showError(message) {
  const container = document.getElementById("registryList");
  container.innerHTML = `<div class='letter-empty'>${tr("list_error_prefix", "Failed to load list:")} ${message}</div>`;
}

document.addEventListener("DOMContentLoaded", async () => {
  setupSearch();
  loadStats();
  initSearchFromUrl();
  try {
    await loadPeople();
    fillRegionFilter();
    fillYearFilter();
    applyFilters();
  } catch (err) {
    showError(err.message);
  }

  window.addEventListener("site-language-changed", () => {
    fillRegionFilter();
    fillYearFilter();
    applyFilters();
  });
});
