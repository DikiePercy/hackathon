const partnersGrid = document.getElementById("partners-grid");
const statsGrid = document.getElementById("stats-grid");

function tr(key, fallback) {
    return window.AppI18n?.t?.(key) || fallback;
}

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
        tr("about_partner_1", "State Archive of the Russian Federation"),
        tr("about_partner_2", "Memorial"),
        tr("about_partner_3", "Sakharov Center"),
        tr("about_partner_4", "RGASPI"),
        tr("about_partner_5", "Yad Vashem"),
        tr("about_partner_6", "National Archive of the Kyrgyz Republic")
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
        { n: persons, l: tr("about_stats_records", "Records in database") },
        { n: documents, l: tr("about_stats_documents", "Documents in database") }
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

    window.addEventListener("site-language-changed", async () => {
        renderPartners();
        await renderStats();
    });
});