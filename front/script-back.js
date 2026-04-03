 // Этот скрипт отвечает за загрузку данных о человеке и отображение их на странице. Используйте бекенд тут для отображения рандомного чела из базы данных
 
 
 
 
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
        fetch('http://localhost:8000/api/person/18')
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