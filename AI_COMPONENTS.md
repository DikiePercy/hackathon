# 🧠 AI Компоненты проекта "Архив Памяти"

## 📁 Основные файлы

### 1. `backend_python/rag_engine.py` ⭐ ГЛАВНЫЙ AI ФАЙЛ
**Что делает:** Ядро RAG (Retrieval-Augmented Generation) системы

**Ключевые функции:**
- `add_documents_to_vector_db()` - добавление документов в векторную БД
- `search_documents()` - семантический поиск по документам
- `generate_answer()` - генерация ответа через Gemini
- `answer_with_rag()` - полный RAG pipeline

**AI модели:**
```python
# Embeddings (векторизация текста)
GoogleGenerativeAIEmbeddings(
    model="models/embedding-001",
    google_api_key=GEMINI_API_KEY
)

# LLM для генерации ответов
ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    temperature=0.3,  # Низкая = точнее, высокая = креативнее
    google_api_key=GEMINI_API_KEY
)
```

**System Prompt (поведение AI):**
```
Отвечай ТОЛЬКО по контексту.
Данные могут быть выдуманными, не используй знания из интернета.
Если в контексте нет ответа, прямо скажи, что информации недостаточно.
```

---

### 2. `backend_python/routers/rag.py` 
**Что делает:** API endpoints для RAG функционала

**Endpoints:**
- `POST /upload_document` - загрузка и векторизация документа
- `POST /chat` - чат с RAG системой
- `GET /chat/history` - история чата пользователя

**Флоу загрузки документа:**
```
1. Получение файла (.txt/.md)
2. → Отправка в C++ для обработки
3. → Получение чанков
4. → Векторизация через Gemini
5. → Сохранение в ChromaDB + PostgreSQL
```

---

### 3. `backend_cpp/main.cpp`
**Что делает:** Предобработка текста (не AI, но критично для качества RAG)

**Функции:**
- `is_garbage()` - фильтрация мусорных текстов
- `clean_markdown()` - очистка markdown разметки
- `chunk_text()` - разбивка на куски с overlap

**Параметры чанкинга:**
```cpp
chunk_size = 1000   // Размер куска в символах
overlap = 100       // Overlap между кусками
```

---

## 🔄 End-to-End поток данных

### Загрузка документа:
```
User (Frontend)
  ↓ POST /upload_document + file
Python Backend (rag.py)
  ↓ POST /process {"text": "..."}
C++ Backend (main.cpp)
  ↓ {"chunks": [...], "is_garbage": false}
rag_engine.py
  ↓ embeddings.embed_documents(chunks)
ChromaDB
  ↓ vectors + metadata
PostgreSQL
  ↓ metadata (document_id, person_id, etc.)
✓ Done
```

### Поиск/Чат:
```
User query: "Где служил Иванов?"
  ↓ POST /chat
rag_engine.search_documents(query)
  ↓ embeddings.embed_query(query)
ChromaDB
  ↓ top_k похожих chunks (vector search)
rag_engine.generate_answer(query, chunks)
  ↓ Gemini LLM
Response: "Иванов служил в..." + sources: [person_id_1, ...]
```

---

## 📦 Зависимости (requirements.txt)

```txt
# AI/ML Core
langchain==0.3.28
langchain-google-genai==2.0.8     # ⭐ Gemini API
langchain-community==0.3.31
chromadb==0.5.23                  # Vector DB
```

---

## 🔑 Переменные окружения

```bash
# Обязательно для AI:
GEMINI_API_KEY=your_key_here        # Google Gemini API

# ChromaDB:
CHROMA_HOST=vector_db               # Hostname
CHROMA_PORT=8000                    # Port
CHROMA_PATH=/app/chroma_db          # Fallback local path
CHROMA_COLLECTION=documents         # Collection name
```

---

## 🛠️ Как модифицировать

### Изменить модель Gemini:
**Файл:** `backend_python/rag_engine.py:42`
```python
# Было:
model="gemini-1.5-flash"

# Опции:
model="gemini-1.5-pro"      # Более точная, дороже
model="gemini-2.0-flash"    # Новейшая версия
```

### Настроить "креативность" ответов:
**Файл:** `backend_python/rag_engine.py:42`
```python
temperature=0.3   # Консервативные ответы (рекомендуется для архива)
temperature=0.7   # Более креативные ответы
```

### Изменить размер чанков:
**Файл:** `backend_cpp/main.cpp:111`
```cpp
chunk_text(cleaned, 1000, 100)   // size=1000, overlap=100

// Меньше чанки = точнее поиск, но больше запросов
chunk_text(cleaned, 500, 50)

// Больше чанки = быстрее, но менее точно
chunk_text(cleaned, 2000, 200)
```

### Изменить системный промпт:
**Файл:** `backend_python/rag_engine.py:116-120`
```python
system_prompt = (
    "Отвечай ТОЛЬКО по контексту. "
    "Данные могут быть выдуманными, не используй знания из интернета. "
    "Если в контексте нет ответа, прямо скажи, что информации недостаточно."
)
```

### Добавить больше контекста в поиск:
**Файл:** `backend_python/routers/rag.py:135`
```python
# Было:
rag_result = answer_with_rag(query, top_k=3)

# Больше контекста (медленнее, но полнее):
rag_result = answer_with_rag(query, top_k=5)
```

---

## ⚠️ Fallback механизмы

### При недоступности Gemini API:
**Файл:** `backend_python/rag_engine.py:128-132`

Автоматически возвращает найденный контекст напрямую:
```python
"⚠️ AI-сервис временно недоступен. Найденная информация:\n\n"
"{первые 500 символов контекста}"
```

### При ошибке в чате:
**Файл:** `backend_python/routers/rag.py:146-152`

Graceful degradation:
- ValueError → 503 "RAG service unavailable"
- RuntimeError → Fallback ответ
- Exception → "Произошла ошибка"

---

## 📊 Метрики качества RAG

### Что влияет на качество ответов:

1. **Качество чанкинга** (C++ backend)
   - Размер чанков: 1000 символов
   - Overlap: 100 символов
   - Очистка markdown

2. **Качество embeddings**
   - Модель: `models/embedding-001`
   - Язык: русский (Gemini хорошо знает)

3. **Количество контекста**
   - top_k=3 по умолчанию
   - Можно увеличить до 5-7

4. **Temperature LLM**
   - 0.3 = точные ответы по фактам
   - 0.7 = более развернутые, креативные

---

## 🧪 Тестирование AI

### Ручной тест загрузки:
```bash
curl -X POST http://localhost:8000/upload_document \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test.txt" \
  -F "person_id=1"
```

### Ручной тест чата:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"Где родился Иванов?"}'
```

### Проверка ChromaDB:
```bash
curl http://localhost:8001/api/v1/collections
```

---

## 🎯 Рекомендации для защиты проекта

1. **Подготовьте демо-данные** - загрузите 5-10 тестовых документов
2. **Протестируйте разные запросы** - подготовьте список вопросов
3. **Имейте fallback** - система работает даже без Gemini API
4. **Объясните архитектуру** - RAG = Retrieval + Generation
5. **Покажите логи** - докажите что AI реально работает

---

**Статус:** ✅ Все AI компоненты настроены и готовы к работе
