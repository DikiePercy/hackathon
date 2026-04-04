#rabota za frontedbeka

const translations = {
    ru: {
        nav_main: "Главная",
        nav_db: "База данных",
        nav_chat: "Чат AI",
        nav_suggestions: "Предложить запись",
        nav_admin: "Админ",
        nav_about: "О проекте",
        nav_contacts: "Контакты",
        site_title: "АРХИВ ПАМЯТИ",
        search_placeholder: "Поиск по имени, фамилии...",
        search_btn: "Найти",
        hero_find: "Найти человека",
        hero_find_desc: "Введите имя или фамилию в строку поиска, чтобы найти информацию о жертве репрессий.",
        hero_add: "Добавить сведения",
        hero_add_desc: "Помогите дополнить архив — загрузите документы и воспоминания о ваших родственниках.",
        hero_help: "Помочь проекту",
        hero_help_desc: "Станьте волонтёром или поддержите проект. Каждый вклад помогает сохранить память.",
        footer_text: "© 2024 Архив Памяти. Открытая энциклопедия жертв политических репрессий.",
        btn_register: "Регистрация",
        btn_login: "Войти",
        btn_logout: "Выйти"
    },
    ky: {
        nav_main: "Башкы бет",
        nav_db: "Маалымат базасы",
        nav_chat: "AI Маек",
        nav_suggestions: "Жазуу сунуш кылуу",
        nav_admin: "Админ",
        nav_about: "Долбоор жөнүндө",
        nav_contacts: "Байланышуу",
        site_title: "Тарых Архиви",
        search_placeholder: "Аты-жөнү боюнча издөө...",
        search_btn: "Издөө",
        hero_find: "Адамды табуу",
        hero_find_desc: "Репрессиянын курмандыгы жөнүндө маалымат табуу үчүн аты-жөнүн киргизиңиз.",
        hero_add: "Маалымат кошуу",
        hero_add_desc: "Архивди толуктоого жардам бериңиз — туугандарыңыз жөнүндө документтерди жүктөп салыңыз.",
        hero_help: "Долбоорго жардам",
        hero_help_desc: "Ыктыярчы болуңуз же долбоорду колдоңуз. Ар бир салым эсте калтырууга жардам берет.",
        footer_text: "© 2024 Эс Куржуну. Саясий репрессиянын курмандыктарынын ачык энциклопедиясы.",
        btn_register: "Каттоо",
        btn_login: "Кирүү",
        btn_logout: "Чыгуу"
    },
    en: {
        nav_main: "Home",
        nav_db: "Database",
        nav_chat: "AI Chat",
        nav_suggestions: "Submit Entry",
        nav_admin: "Admin",
        nav_about: "About",
        nav_contacts: "Contacts",
        site_title: "MEMORY ARCHIVE",
        search_placeholder: "Search by name, surname...",
        search_btn: "Search",
        hero_find: "Find a Person",
        hero_find_desc: "Enter a name or surname in the search bar to find information about victims of repression.",
        hero_add: "Add Information",
        hero_add_desc: "Help expand the archive — upload documents and memories about your relatives.",
        hero_help: "Support the Project",
        hero_help_desc: "Become a volunteer or support the project. Every contribution helps preserve memory.",
        footer_text: "© 2024 Memory Archive. Open encyclopedia of political repression victims.",
        btn_register: "Register",
        btn_login: "Login",
        btn_logout: "Logout"
    },
    tr: {
        nav_main: "Ana Sayfa",
        nav_db: "Veritabanı",
        nav_chat: "AI Sohbet",
        nav_suggestions: "Kayıt Öner",
        nav_admin: "Yönetici",
        nav_about: "Hakkında",
        nav_contacts: "İletişim",
        site_title: "HAFIZA ARŞİVİ",
        search_placeholder: "Ad, soyadına göre ara...",
        search_btn: "Ara",
        hero_find: "Bir Kişi Bul",
        hero_find_desc: "Baskı kurbanları hakkında bilgi bulmak için arama çubuğuna bir ad veya soyadı girin.",
        hero_add: "Bilgi Ekle",
        hero_add_desc: "Arşivi genişletmeye yardım edin — akrabalarınız hakkında belgeler ve anılar yükleyin.",
        hero_help: "Projeyi Destekle",
        hero_help_desc: "Gönüllü olun veya projeyi destekleyin. Her katkı hafızayı korumaya yardımcı olur.",
        footer_text: "© 2024 Hafıza Arşivi. Siyasi baskı kurbanlarının açık ansiklopedisi.",
        btn_register: "Kayıt Ol",
        btn_login: "Giriş Yap",
        btn_logout: "Çıkış Yap"
    }
};

function setLanguage(lang) {
    localStorage.setItem('archive_lang', lang);
    applyLanguage(lang);
}

function applyLanguage(lang) {
    const t = translations[lang] || translations['ru'];
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (t[key]) {
            if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                el.placeholder = t[key];
            } else {
                el.textContent = t[key];
            }
        }
    });
    
    // Подсвечиваем активную кнопку языка
    document.querySelectorAll('.lang-btn').forEach(btn => {
        const btnLang = btn.getAttribute('data-lang');
        btn.classList.toggle('active', btnLang === lang);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const savedLang = localStorage.getItem('archive_lang') || 'ru';
    applyLanguage(savedLang);
});