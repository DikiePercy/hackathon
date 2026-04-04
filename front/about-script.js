const partnersGrid = document.getElementById("partners-grid");
const statsGrid = document.getElementById("stats-grid");

function resolveApiBase() {
    const params = new URLSearchParams(window.location.search);
    const fromQuery = params.get("api");
    if (fromQuery) {
        return fromQuery.replace(/\/$/, "");
    }
    return "http://localhost:8000";
}

const API_BASE = resolveApiBase();

function renderPartners() {
    if (!partnersGrid) return;
    const partners = [
        "Государственный архив РФ",
        "Мемориал",
        "Сахаровский центр",
        "РГАСПИ",
        "Яд Вашем",
        "Национальный архив РК"
    ];

    partnersGrid.innerHTML = "";
    partners.forEach((partner) => {
        partnersGrid.innerHTML += `
            <div class="about-card">
                <div class="partner-icon">🏛</div>
                <div class="partner-name">${partner}</div>
            </div>`;
    });
}

async function renderStats() {
    if (!statsGrid) return;
    statsGrid.innerHTML = "";

    let persons = "-";
    let documents = "-";

    try {
        const response = await fetch(`${API_BASE}/api/stats`);
        if (response.ok) {
            const stats = await response.json();
            persons = String(stats.persons ?? "-");
            documents = String(stats.documents ?? "-");
        }
    } catch (_err) {
        persons = "-";
        documents = "-";
    }

    const cards = [
        { n: persons, l: "Записей в базе" },
        { n: documents, l: "Документов в базе" }
    ];

    cards.forEach((stat) => {
        statsGrid.innerHTML += `
            <div class="about-card">
                <div class="stat-number">${stat.n}</div>
                <div class="stat-label">${stat.l}</div>
            </div>`;
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    renderPartners();
    await renderStats();
});