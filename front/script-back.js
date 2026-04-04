// Этот скрипт отвечает за загрузку данных о человеке и отображение их на странице. Используйте бекенд тут для отображения рандомного чела из базы данных

// Определяем API URL автоматически
function resolveApiBase() {
    // Если мы на production (не localhost), используем относительные пути
    if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
        return window.location.protocol + '//' + window.location.hostname + ':8000';
    }
    // Для локальной разработки
    return 'http://localhost:8000';
}

const API_BASE = resolveApiBase();

const personNameElem = document.getElementById('personName');
if (personNameElem) {
    const mockData = {
        full_name: "Гольдберг Максим Ефимович",
        birth_year: 1900,
        death_year: 1937,
        nationality: "еврей",
        occupation: "Начальник строительства БМК",
        biography: "Максим Ефимович родился в 1900 году в Варшаве... Приговор приведен в исполнение."
    };

    // Пытаемся получить данные с бэкенда
    fetch(`${API_BASE}/api/person/18`)
        .then(response => response.json())
        .then(data => renderPerson(data))
        .catch(() => renderPerson(mockData));
}

function renderPerson(data) {
    if (!personNameElem) return;
    personNameElem.innerText = data.full_name;
    document.getElementById('personYears').innerText = `${data.birth_year} — ${data.death_year}`;
    document.getElementById('biographyText').innerText = data.biography;
    // ... заполнение остальных полей таблицы ...
}
