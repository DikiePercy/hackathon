const partnersGrid = document.getElementById('partners-grid');
    const statsGrid = document.getElementById('stats-grid');

    if (partnersGrid && statsGrid) {
        const partners = ["Государственный архив РФ", "Мемориал", "Сахаровский центр", "РГАСПИ", "Яд Вашем", "Национальный архив РК"];
        //Добавьте статистику в массив stats из бекенда
        const stats = [
            { n: "48 291", l: "Записей в базе" },
            { n: "12 750", l: "Документов оцифровано" },
            { n: "37", l: "Регионов охвачено" }
        ];

        partners.forEach(p => {
            partnersGrid.innerHTML += `
                <div class="about-card">
                    <div class="partner-icon">🏛</div>
                    <div class="partner-name">${p}</div>
                </div>`;
        });

        stats.forEach(s => {
            statsGrid.innerHTML += `
                <div class="about-card">
                    <div class="stat-number">${s.n}</div>
                    <div class="stat-label">${s.l}</div>
                </div>`;
        });
    }