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

function renderPartners() {
  const partnersGrid = document.getElementById("partners-grid");
  if (!partnersGrid) return;

  const partners = [
    "Государственный архив РФ",
    "Мемориал",
    "Сахаровский центр",
    "РГАСПИ",
    "Яд Вашем",
    "Национальный архив КР"
  ];

  partnersGrid.innerHTML = "";
  partners.forEach((p) => {
    partnersGrid.innerHTML += `
      <div class="about-card">
        <div class="partner-icon">🏛</div>
        <div class="partner-name">${p}</div>
      </div>`;
  });
}

async function renderStats() {
  const statsGrid = document.getElementById("stats-grid");
  if (!statsGrid) return;

  statsGrid.innerHTML = "Загрузка...";

  try {
    const response = await fetch(apiUrl("/api/stats"));
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const stats = await response.json();
    const rows = [
      { n: String(stats.persons ?? 0), l: "Записей в базе" },
      { n: String(stats.documents ?? 0), l: "Документов" },
      { n: String(stats.chunks_in_db ?? 0), l: "Чанков в векторной базе" }
    ];

    statsGrid.innerHTML = "";
    rows.forEach((s) => {
      statsGrid.innerHTML += `
        <div class="about-card">
          <div class="stat-number">${s.n}</div>
          <div class="stat-label">${s.l}</div>
        </div>`;
    });
  } catch (err) {
    statsGrid.innerHTML = `Ошибка загрузки статистики: ${err.message}`;
  }
}

async function renderRegions() {
  const regionsGrid = document.getElementById("regions-grid");
  if (!regionsGrid) return;

  regionsGrid.innerHTML = "Загрузка...";

  try {
    const response = await fetch(apiUrl("/api/stats"));
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const stats = await response.json();
    const regions = Array.isArray(stats.by_region) ? stats.by_region : [];

    if (!regions.length) {
      regionsGrid.innerHTML = "Нет данных по регионам";
      return;
    }

    regionsGrid.innerHTML = "";
    regions.slice(0, 24).forEach((row) => {
      regionsGrid.innerHTML += `
        <div class="about-card region-card">
          <div class="region-name">${row.region || "Unknown"}</div>
          <div class="region-count">${row.cnt || 0}</div>
        </div>`;
    });
  } catch (err) {
    regionsGrid.innerHTML = `Ошибка загрузки регионов: ${err.message}`;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  renderPartners();
  renderStats();
  renderRegions();
});
