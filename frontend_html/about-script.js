// document.addEventListener("DOMContentLoaded", () => {
//     // Данные для статистики
//     const statsData = [
//         { number: "48 291", label: "Записей в базе" },
//         { number: "12 750", label: "Документов оцифровано" },
//         { number: "37", label: "Регионов охвачено" }
//     ];

//     // Данные для партнеров
//     const partnersData = [
//         "Государственный архив РФ", "Мемориал", "Сахаровский центр",
//         "РГАСПИ", "Яд Вашем", "Национальный архив РК"
//     ];

//     // Рендерим статистику
//     const statsList = document.getElementById('stats-list');
//     statsData.forEach(item => {
//         const div = document.createElement('div');
//         div.className = 'archive-stat-block';
//         div.innerHTML = `
//             <div class="archive-stat-number">${item.number}</div>
//             <div style="font-size: 0.8rem; opacity: 0.8">${item.label}</div>
//         `;
//         statsList.appendChild(div);
//     });

//     // Рендерим партнеров
//     const partnersList = document.getElementById('partners-list');
//     partnersData.forEach(name => {
//         const div = document.createElement('div');
//         div.className = 'partner-item';
//         div.innerHTML = `<div style="font-size: 1.5rem; margin-bottom: 5px">🏛️</div> ${name}`;
//         partnersList.appendChild(div);
//     });
// });