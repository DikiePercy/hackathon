# Hackathon

Минимальная инструкция.

## Запуск из zip на сервере

1. Создай `.env` из `.env.example` и заполни секреты.
2. Укажи отдельные папки для данных (в `.env`):

   - `DB_DATA_DIR=/srv/hackathon-data/postgres`
   - `CHROMA_DATA_DIR=/srv/hackathon-data/chroma`
   - `APP_DATA_DIR=/srv/hackathon-data/app`

3. Запусти:

```bash
chmod +x scripts/*.sh
./scripts/start.sh
```

## Важно

- Не используй `docker compose down -v` в проде, если нужно сохранить БД.

## Авторизация и роли

В `.env` задаются учетные данные админа, которые будут автоматически созданы при старте:

- `ADMIN_USERNAME=admin`
- `ADMIN_PASSWORD=AdminSecure123`
- `SECRET_KEY=<случайная длинная строка>`
- `COOKIE_SECURE=true` (в проде с HTTPS)

Роли:

- `admin`: управление карточками, импорт, модерация предложений.
- `user`: чат и отправка предложений на модерацию.

Поток предложений:

1. Пользователь отправляет запись на странице `suggestions.html`.
2. Админ рассматривает на `admin.html`.
3. Админ одобряет (запись попадает в `person_cards`) или отклоняет.

## RAG: Ollama, Gemini или Claude

В `.env` можно выбрать провайдер генерации для RAG:

- `RAG_LLM_PROVIDER=ollama` (локальная модель, бесплатно, приватно) ⭐ **Рекомендуется**
- `RAG_LLM_PROVIDER=gemini` (по умолчанию, требует API ключ)
- `RAG_LLM_PROVIDER=claude`

### Ollama (локальная модель)

Система теперь поддерживает Ollama для работы без внешних API:

- ✅ Бесплатно (не нужен API ключ)
- ✅ Приватность (данные не покидают сервер)
- ✅ Работает оффлайн
- ✅ Поддержка русского, кыргызского, турецкого языков

**Настройка:**
```bash
# В .env установите:
RAG_LLM_PROVIDER=ollama
RAG_EMBEDDING_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
RAG_OLLAMA_MODEL=llama3:8b
```

Подробнее см. `OLLAMA_SETUP.md` и `OLLAMA_INTEGRATION_COMPLETE.md`

Для Claude укажи:

- `ANTHROPIC_API_KEY=...`
- `RAG_CLAUDE_MODEL=claude-3-5-sonnet-20240620`

Для эмбеддингов (поиск по векторной базе) можно выбрать провайдер отдельно:

- `RAG_EMBEDDING_PROVIDER=gemini`
- `RAG_EMBEDDING_PROVIDER=openai`

Пример режима Claude + OpenAI embeddings (без Gemini):

- `RAG_LLM_PROVIDER=claude`
- `ANTHROPIC_API_KEY=...`
- `RAG_CLAUDE_MODEL=claude-3-5-sonnet-20240620`
- `RAG_EMBEDDING_PROVIDER=openai`
- `OPENAI_API_KEY=...`
- `RAG_OPENAI_EMBEDDING_MODEL=text-embedding-3-large`

Да, названия моделей ты задаешь сам в `.env` (например `RAG_CLAUDE_MODEL`).
