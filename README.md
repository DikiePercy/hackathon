# 📚 Archive Hackathon - RAG Search System

Микросервисная система для интеллектуального поиска по архивным документам с использованием RAG (Retrieval-Augmented Generation).

## 🏗️ Архитектура

Проект состоит из 5 микросервисов:

1. **C++ Backend** (порт 8080) - Высокопроизводительный парсинг и фильтрация текста
2. **Python Backend** (порт 8000) - FastAPI, JWT auth, RAG, PostgreSQL
3. **Streamlit Frontend** (порт 8501) - Пользовательский интерфейс
4. **PostgreSQL** (порт 5432) - Основная база данных
5. **ChromaDB** (порт 8001) - Векторная база для RAG

```
┌─────────────────┐
│   Streamlit     │ :8501
│    Frontend     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│  Python Backend │────▶│ C++ Backend  │
│   (FastAPI)     │:8000│  (httplib)   │:8080
└────┬───────┬────┘     └──────────────┘
     │       │
     ▼       ▼
┌──────┐  ┌─────────┐
│ PG   │  │ ChromaDB│
│ DB   │  │(Vector) │
└──────┘  └─────────┘
```

## 🚀 Быстрый старт

### Предварительные требования

- Docker & Docker Compose
- OpenAI API ключ (или альтернатива: GigaChat, YandexGPT)

### Запуск

1. **Клонируйте репозиторий:**
```bash
git clone <your-repo>
cd hackathon
```

2. **Настройте переменные окружения:**
```bash
# Отредактируйте .env файл
nano .env

# Установите OPENAI_API_KEY и SECRET_KEY
```

3. **Запустите все сервисы:**
```bash
docker-compose up --build
```

4. **Откройте браузер:**
- Frontend: http://localhost:8501
- Python API: http://localhost:8000/docs
- C++ API: http://localhost:8080/health

## 📦 Структура проекта

```
hackathon/
├── docker-compose.yml          # Оркестрация сервисов
├── .env                        # Переменные окружения
│
├── backend_cpp/                # C++ микросервис
│   ├── main.cpp               # HTTP сервер с парсингом
│   ├── CMakeLists.txt         # Сборка CMake
│   ├── Dockerfile
│   └── third_party/           # Библиотеки
│       ├── httplib.h          # cpp-httplib
│       └── json.hpp           # nlohmann/json
│
├── backend_python/             # Python микросервис
│   ├── main.py                # FastAPI приложение
│   ├── database.py            # SQLAlchemy модели
│   ├── auth.py                # JWT авторизация
│   ├── rag_engine.py          # RAG логика
│   ├── routers/               # API endpoints
│   │   ├── auth_router.py    # /login, /register
│   │   ├── cards.py           # CRUD для карточек
│   │   └── rag.py             # /upload_document, /chat
│   ├── requirements.txt
│   └── Dockerfile
│
└── frontend_python/            # Streamlit UI
    ├── app.py                 # Интерфейс
    ├── requirements.txt
    └── Dockerfile
```

## 🔧 Основные функции

### 1️⃣ C++ Backend - Обработка текста

**Эндпоинт:** `POST /process`

**Функции:**
- ✅ Проверка на "мусорный" текст (noise detection)
- ✅ Очистка Markdown форматирования
- ✅ Чанкинг с перекрытием (1000 символов, overlap 100)

**Пример запроса:**
```json
{
  "text": "# Document\n\nSome content here...",
  "chunk_size": 1000,
  "overlap": 100
}
```

**Ответ:**
```json
{
  "is_garbage": false,
  "chunks": ["chunk 1 text...", "chunk 2 text..."]
}
```

### 2️⃣ Python Backend - API & RAG

**Аутентификация:**
- `POST /register` - Регистрация
- `POST /login` - Логин (JWT токен)

**Карточки людей/мест:**
- `GET /cards` - Список (с фильтрами)
- `POST /cards` - Создание
- `PUT /cards/{id}` - Обновление
- `DELETE /cards/{id}` - Удаление

**RAG система:**
- `POST /upload_document` - Загрузка документа для карточки
- `POST /chat` - Вопрос-ответ по документам
- `GET /chat/history` - История чата

### 3️⃣ Frontend - Streamlit

**Вкладки:**
1. **💬 Chat** - Задавайте вопросы по загруженным документам
2. **📁 Documents** - Загружайте txt/md файлы
3. **👤 Person Cards** - Управление карточками

## 🧠 Как работает RAG

1. Пользователь загружает документ (txt/md)
2. C++ backend проверяет и разбивает на чанки
3. Python backend создает эмбеддинги (OpenAI)
4. Чанки сохраняются в ChromaDB с метаданными
5. При запросе делается similarity search
6. Топ-3 релевантных чанка передаются в LLM
7. GPT генерирует ответ на основе контекста

## 🔐 Безопасность

- JWT токены с bcrypt хешированием паролей
- CORS настроен для безопасного взаимодействия
- Все пароли хешируются через passlib
- Изолированные Docker networks

## 🧪 Тестирование

```bash
# Тест C++ backend
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"text": "Test document content"}'

# Тест Python backend
curl http://localhost:8000/health

# Регистрация пользователя
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "password": "test123"}'
```

## 📝 База данных

### Таблицы PostgreSQL:

- **users** - Пользователи системы
- **person_cards** - Карточки людей/мест с координатами
- **chat_history** - История диалогов с источниками

## 🌍 Многоязычность

Система автоматически отвечает на том языке, на котором задан вопрос (через системный промпт LLM).

## 🛠️ Разработка

### Запуск без Docker (для разработки):

**C++ Backend:**
```bash
cd backend_cpp
cmake . && make
./cpp_backend
```

**Python Backend:**
```bash
cd backend_python
pip install -r requirements.txt
uvicorn main:app --reload
```

**Frontend:**
```bash
cd frontend_python
pip install -r requirements.txt
streamlit run app.py
```

## 📊 Технологии

- **C++17** - cpp-httplib, nlohmann/json
- **Python 3.11** - FastAPI, SQLAlchemy, LangChain
- **LLM** - OpenAI GPT-3.5/4
- **Vector DB** - ChromaDB
- **DB** - PostgreSQL 15
- **UI** - Streamlit
- **Auth** - JWT (python-jose, passlib)

## 🤝 Команда

Backend & C++ Lead - Реализация инфраструктуры и ядра системы

## 📜 Лицензия

MIT License

---

Создано для хакатона 2026 🚀
