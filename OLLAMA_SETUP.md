# Настройка Ollama для RAG системы

## ✅ Выполнено

Система настроена для использования **Ollama** (llama3:8b) вместо Gemini API.

## Что изменилось

### 1. Backend Python (`rag_engine.py`)
- Добавлена поддержка Ollama для LLM генерации
- Добавлена поддержка Ollama для embeddings
- Добавлены переменные окружения:
  - `OLLAMA_BASE_URL` - URL сервера Ollama (по умолчанию: http://localhost:11434)
  - `RAG_OLLAMA_MODEL` - модель Ollama (по умолчанию: llama3:8b)

### 2. Docker Compose
- Python backend теперь использует `network_mode: "host"` для доступа к Ollama на хосте
- Обновлены URL для внутренних сервисов (localhost вместо имён контейнеров)
- Добавлены переменные окружения для Ollama

### 3. Конфигурационные файлы
- `.env` - обновлён для использования Ollama
- `.env.example` - добавлены примеры настроек Ollama

## Текущая конфигурация

```bash
# RAG провайдеры
RAG_LLM_PROVIDER=ollama
RAG_EMBEDDING_PROVIDER=ollama

# Ollama настройки
OLLAMA_BASE_URL=http://localhost:11434
RAG_OLLAMA_MODEL=llama3:8b
```

## Как использовать

### 1. Запустить систему
```bash
cd /home/adelete/hackathon
docker-compose up -d
```

### 2. Проверить статус
```bash
# Проверка Ollama
curl http://localhost:11434/api/tags

# Проверка backend
curl http://localhost:8000/health
```

### 3. Использовать через веб-интерфейс
- Откройте http://localhost (HTML frontend) или http://localhost:8501 (Streamlit)
- Войдите с учётными данными администратора
- Загрузите документы
- Задавайте вопросы - теперь ответы генерирует локальная модель Ollama!

## Преимущества Ollama

✅ **Бесплатно** - не нужен API ключ  
✅ **Приватность** - данные не покидают ваш сервер  
✅ **Оффлайн** - работает без интернета  
✅ **Кастомизация** - можно использовать любые модели Ollama

## Доступные модели

Текущая модель: `llama3:8b` (4.7 GB)

Другие рекомендуемые модели:
- `llama3:70b` - более мощная версия (требует больше RAM)
- `mistral:7b` - быстрая и эффективная
- `gemma:7b` - от Google
- `qwen2:7b` - хороша для многоязычности

### Смена модели

```bash
# Скачать новую модель
ollama pull mistral:7b

# Обновить .env
echo "RAG_OLLAMA_MODEL=mistral:7b" >> .env

# Перезапустить backend
docker-compose restart python_backend
```

## Переключение обратно на Gemini

Если нужно вернуться на Gemini:

```bash
# Обновите .env
RAG_LLM_PROVIDER=gemini
RAG_EMBEDDING_PROVIDER=gemini
GEMINI_API_KEY=your-api-key-here

# Перезапустите backend
docker-compose restart python_backend
```

## Поддержка нескольких языков

Модель llama3:8b поддерживает:
- 🇷🇺 Русский
- 🇰🇬 Кыргызский (ограниченно)
- 🇹🇷 Турецкий
- 🇬🇧 Английский
- И многие другие

## Производительность

**Типичное время ответа с llama3:8b:**
- Первый запрос: ~3-5 секунд (загрузка модели)
- Последующие: ~1-3 секунды (модель в памяти)

**Требования:**
- RAM: минимум 8 GB (рекомендуется 16 GB)
- CPU: многоядерный процессор
- Диск: ~5 GB для модели

## Отладка

### Проверка логов Ollama
```bash
journalctl -u ollama -f
```

### Проверка логов backend
```bash
docker logs -f hackathon_python
```

### Тестирование Ollama напрямую
```bash
curl http://localhost:11434/api/generate -d '{
  "model": "llama3:8b",
  "prompt": "Привет, как дела?",
  "stream": false
}'
```

## Возможные проблемы

### Backend не может подключиться к Ollama
- Убедитесь, что Ollama запущен: `systemctl status ollama`
- Проверьте, что модель загружена: `ollama list`

### Медленные ответы
- Проверьте загрузку CPU: `htop`
- Убедитесь, что достаточно RAM: `free -h`
- Рассмотрите использование меньшей модели

### Ошибки при загрузке документов
- Проверьте логи: `docker logs hackathon_python`
- Убедитесь, что ChromaDB работает: `curl http://localhost:8001/api/v1/heartbeat`

## Контакты

Если возникли вопросы или проблемы, проверьте:
- Логи: `docker-compose logs`
- Статус сервисов: `docker-compose ps`
- Здоровье системы: `curl http://localhost:8000/health`
