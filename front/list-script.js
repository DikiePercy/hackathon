// Данный файл нужен для отображения списка репрессированных из базы данных. Неоюходимо заменить 



// Cyrillic alphabet
const CYRILLIC = "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЩЭЮЯ".split("");

// Mock registry data
const MOCK_PEOPLE = [
  { id: 1, name: "Абакумов Виктор Семёнович" },
  { id: 2, name: "Абрамович Лев Борисович" },
  { id: 3, name: "Авдеев Пётр Иванович" },
  { id: 4, name: "Агранов Яков Саулович" },
  { id: 5, name: "Бабель Исаак Эммануилович" },
  { id: 6, name: "Бабич Андрей Николаевич" },
  { id: 7, name: "Баранов Сергей Дмитриевич" },
  { id: 8, name: "Бергер Иосиф Маркович" },
  { id: 9, name: "Вавилов Николай Иванович" },
  { id: 10, name: "Васильев Григорий Фёдорович" },
  { id: 11, name: "Вознесенский Николай Алексеевич" },
  { id: 12, name: "Гамарник Ян Борисович" },
  { id: 13, name: "Гинзбург Евгения Семёновна" },
  { id: 14, name: "Горбатов Александр Васильевич" },
  { id: 15, name: "Грабарь Игорь Эммануилович" },
  { id: 16, name: "Губкин Иван Михайлович" },
  { id: 17, name: "Гумилёв Лев Николаевич" },
  { id: 18, name: "Гольдберг Максим Ефимович" },
  { id: 19, name: "Дыбенко Павел Ефимович" },
  { id: 20, name: "Ежов Николай Иванович" },
  { id: 21, name: "Жуковский Пётр Михайлович" },
  { id: 22, name: "Зиновьев Григорий Евсеевич" },
  { id: 23, name: "Каменев Лев Борисович" },
  { id: 24, name: "Карбышев Дмитрий Михайлович" },
  { id: 25, name: "Колчак Александр Васильевич" },
  { id: 26, name: "Королёв Сергей Павлович" },
  { id: 27, name: "Косарев Александр Васильевич" },
  { id: 28, name: "Ландау Лев Давидович" },
  { id: 29, name: "Мандельштам Осип Эмильевич" },
  { id: 30, name: "Мейерхольд Всеволод Эмильевич" },
  { id: 31, name: "Николаев Леонид Васильевич" },
  { id: 32, name: "Орджоникидзе Серго" },
  { id: 33, name: "Пятаков Георгий Леонидович" },
  { id: 34, name: "Радек Карл Бернгардович" },
  { id: 35, name: "Рокоссовский Константин Константинович" },
  { id: 36, name: "Рыков Алексей Иванович" },
  { id: 37, name: "Сахаров Андрей Дмитриевич" },
  { id: 38, name: "Солженицын Александр Исаевич" },
  { id: 39, name: "Тухачевский Михаил Николаевич" },
  { id: 40, name: "Уборевич Иероним Петрович" },
  { id: 41, name: "Флоренский Павел Александрович" },
  { id: 42, name: "Хармс Даниил Иванович" },
  { id: 43, name: "Чаянов Александр Васильевич" },
  { id: 44, name: "Шаламов Варлам Тихонович" },
  { id: 45, name: "Щербаков Александр Сергеевич" },
  { id: 46, name: "Эренбург Илья Григорьевич" },
  { id: 47, name: "Юдин Павел Фёдорович" },
  { id: 48, name: "Якир Иона Эммануилович" }
];

function groupByLetter(people) {
  const groups = {};
  CYRILLIC.forEach(l => { groups[l] = []; });
  people.forEach(p => {
    const first = p.name.charAt(0).toUpperCase();
    if (groups[first]) {
      groups[first].push(p);
    }
  });
  // Sort names within each group
  for (const l of CYRILLIC) {
    groups[l].sort((a, b) => a.name.localeCompare(b.name, "ru"));
  }
  return groups;
}

function renderAlphabetBar(groups) {
  const bar = document.getElementById("alphabetBar");
  CYRILLIC.forEach(letter => {
    const a = document.createElement("a");
    a.href = "#letter-" + letter;
    a.textContent = letter;
    if (groups[letter].length === 0) {
      a.classList.add("disabled");
      a.removeAttribute("href");
    }
    bar.appendChild(a);
  });
}

function renderRegistry(groups) {
  const container = document.getElementById("registryList");
  container.innerHTML = "";

  CYRILLIC.forEach(letter => {
    const people = groups[letter];
    if (people.length === 0) return;

    const section = document.createElement("section");
    section.className = "letter-section";

    const heading = document.createElement("h2");
    heading.className = "letter-heading";
    heading.id = "letter-" + letter;
    heading.textContent = letter;
    section.appendChild(heading);

    const ul = document.createElement("ul");
    ul.className = "name-list";

    people.forEach(p => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = "person.html?id=" + p.id;
      a.textContent = p.name;
      const span = document.createElement("span");
      span.className = "name-id";
      span.textContent = "#" + p.id;
      a.appendChild(span);
      li.appendChild(a);
      ul.appendChild(li);
    });

    section.appendChild(ul);
    container.appendChild(section);
  });
}

// Search filter
function setupSearch() {
  const input = document.getElementById("searchInput");
  const btn = document.getElementById("searchBtn");

  function doSearch() {
    const query = input.value.trim().toLowerCase();
    if (!query) {
      const groups = groupByLetter(MOCK_PEOPLE);
      renderRegistry(groups);
      return;
    }
    const filtered = MOCK_PEOPLE.filter(p => p.name.toLowerCase().includes(query));
    const groups = groupByLetter(filtered);
    renderRegistry(groups);
  }

  btn.addEventListener("click", doSearch);
  input.addEventListener("keydown", e => {
    if (e.key === "Enter") doSearch();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  if (typeof renderAuth === "function") renderAuth();
  const groups = groupByLetter(MOCK_PEOPLE);
  renderAlphabetBar(groups);
  renderRegistry(groups);
  setupSearch();
});
