# 🏛️ Голос из Архива | Voice from the Archive

![Python](https://img.shields.io/badge/Python-3.11-blue.svg?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg?logo=fastapi)
![Streamlit](https://img.shields.io/badge/Streamlit-1.25+-FF4B4B.svg?logo=streamlit)
![C++](https://img.shields.io/badge/C++-17-00599C.svg?logo=c%2B%2B)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791.svg?logo=postgresql)
![Ollama](https://img.shields.io/badge/AI-Ollama_(Llama_3)-black.svg?logo=meta)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker)

**«Архив памяти»** — интеллектуальная поисковая система для сохранения исторической памяти о жертвах политических репрессий. Система использует AI (RAG — Retrieval-Augmented Generation) для анализа архивных документов и ответов на вопросы на естественном языке.

**Работает полностью локально** (без облачных API), обеспечивая максимальную приватность архивных данных.

---

## 🎯 Проблема и решение

**Проблема:** Архивные документы о репрессированных разрозненны и недоступны. Поиск информации занимает дни.

**Решение:** RAG-система с локальным AI, которая понимает вопросы на русском, кыргызском и турецком языках и отвечает на основе реальных архивных документов.

---

## ✨ Ключевые возможности

- 🤖 **AI-Архивариус (Smart RAG):** Чат-бот отвечает на вопросы, опираясь **только** на загруженные архивные документы
- 🔐 **Privacy-First AI:** Локальный Ollama (Llama 3 8B) - данные не покидают сервер
- 🌍 **Multilingual:** Поддержка русского, кыргызского, турецкого языков
- 📚 **База репрессированных:** Удобные карточки с биографиями, статьями обвинения, датами реабилитации
- 🔤 **Алфавитный указатель:** Быстрый поиск по алфавиту и фильтрация по профессиям
- ⚡ **Гибридный поиск:** Векторный (семантика) + лексический (ключевые слова) = точность 85%+
- 👥 **Гражданское участие:** Пользователи предлагают карточки, администратор модерирует

---

## 🏗️ Архитектура

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│  Frontend   │────▶│   FastAPI   │────▶│  PostgreSQL  │
│ (Streamlit) │     │   Backend   │     │   Database   │
└─────────────┘     └─────────────┘     └──────────────┘
                           │
                           ├────▶ ChromaDB (Vector Store)
                           │
                           ├────▶ Ollama (Local AI)
                           │
                           └────▶ C++ Processing Node
```

**Микросервисы:**
1. **Frontend (Streamlit)** - пользовательский интерфейс
2. **Backend (FastAPI)** - API, авторизация (JWT), RAG-оркестрация
3. **C++ Processing Node** - обработка текстов, chunking, очистка
4. **PostgreSQL** - структурированные данные (карточки, документы)
5. **ChromaDB** - векторная база для семантического поиска
6. **Ollama** - локальный LLM для генерации ответов

---

## 🚀 Быстрый старт

### Требования
- Docker & Docker Compose
- 16GB RAM (минимум)
- Ollama с моделью llama3:8b

### 1. Установка Ollama
```bash
# Linux/Mac
curl -fsSL https://ollama.com/install.sh | sh

# Скачать модель (4.7GB)
ollama pull llama3:8b

# Проверить
ollama list
```

### 2. Запуск проекта
```bash
git clone https://github.com/DikiePercy/hackathon.git
cd hackathon

# Настроить переменные окружения
cp .env.example .env
# Отредактировать .env если нужно

# Запустить Docker
docker-compose up -d

# Проверить статус
docker-compose ps
```

### 3. Открыть приложение
- **Frontend:** http://localhost:8080
- **Streamlit:** http://localhost:8501
- **API Docs:** http://localhost:8000/docs

### 4. Первый запуск
1. Зарегистрировать администратора через Streamlit
2. Войти в систему
3. Загрузить архивные документы (PDF/TXT)
4. Задать вопрос в RAG чате

---

## 📚 Документация

### Для хакатона:
- **[PITCH.md](PITCH.md)** - Краткий питч (2-3 минуты)
- **[HACKATHON_PRESENTATION.md](HACKATHON_PRESENTATION.md)** - Полная презентация (10-15 минут)
- **[CHECKLIST.md](CHECKLIST.md)** - Чеклист подготовки к защите

### Для деплоя:
- **[QUICK_DEPLOY.md](QUICK_DEPLOY.md)** - Быстрый деплой за 5 минут
- **[README_HOSTING.md](README_HOSTING.md)** - Полное руководство по хостингу
- **[HOSTING_COMPARISON.md](HOSTING_COMPARISON.md)** - Сравнение провайдеров

---

## 🛠️ Технологии

### Backend
- **Python 3.11:** FastAPI, LangChain, SQLAlchemy
- **C++ 17:** Text processing, httplib server
- **Ollama:** Local LLM (llama3:8b, 4.7GB)
- **ChromaDB:** Vector database
- **PostgreSQL 15:** Relational database

### Frontend
- **Streamlit:** Admin interface
- **HTML/CSS/JS:** User interface
- **Nginx:** Reverse proxy

### DevOps
- **Docker Compose:** Container orchestration
- **Git:** Version control
- **GitHub Actions:** CI/CD (optional)

---

## 📊 Производительность

- ⚡ **Скорость ответа:** 2-5 секунд (CPU) или 0.5-1 сек (GPU)
- 👥 **Throughput:** 20 одновременных пользователей
- 🎯 **Точность:** 85%+ релевантных ответов
- 💾 **Размер модели:** 4.7GB (llama3:8b)
- 💰 **Хостинг:** от $13/месяц (VPS) или $144/месяц (GPU)

---

## 🌟 Социальная значимость

**Кому помогает:**
- **Родственникам** - найти информацию о предках
- **Историкам** - быстрый поиск в архивах
- **Обществу** - сохранение исторической памяти

**Потенциал:**
- Интеграция с государственными архивами
- Расширение на другие исторические периоды
- Мобильное приложение
- Открыт для партнёрства с музеями и архивами

---

## 🔒 Безопасность

- ✅ JWT токены с HttpOnly cookies
- ✅ Bcrypt хеширование паролей
- ✅ CORS whitelist
- ✅ Role-based access (admin/user)
- ✅ SQL injection protection
- ✅ XSS protection
- ✅ Локальный AI (данные не покидают сервер)

---

## 🤝 Вклад в проект

Проект открыт для contributions! Мы приветствуем:
- Добавление новых архивных документов
- Улучшение алгоритмов поиска
- Перевод на другие языки
- Оптимизация производительности
- Исправление багов

```bash
git checkout -b feature/your-feature
git commit -m "Add your feature"
git push origin feature/your-feature
# Создать Pull Request
```

---

## 📄 Лицензия

MIT License - см. [LICENSE](LICENSE)

---

## 📞 Контакты

- **GitHub:** https://github.com/DikiePercy/hackathon
- **Issues:** https://github.com/DikiePercy/hackathon/issues

---

## 🏆 Хакатон

Этот проект создан для хакатона. Для подготовки к защите:

1. Прочитать **[PITCH.md](PITCH.md)** - запомнить ключевые тезисы
2. Прочитать **[CHECKLIST.md](CHECKLIST.md)** - подготовиться к демо
3. Запустить систему и протестировать основные функции
4. Подготовить 3-5 примеров вопросов для демо

**Удачи на хакатоне! 🚀**

---

Made with ❤️ for preserving historical memory
