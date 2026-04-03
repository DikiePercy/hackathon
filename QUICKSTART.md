# 🚀 Быстрый старт

## Шаг 1: Настройка API ключа

Откройте `.env` и добавьте ваш OpenAI API ключ:

```bash
nano .env
```

Замените:
```
OPENAI_API_KEY=your-openai-api-key-here
```

На:
```
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxx
```

Также сгенерируйте секретный ключ:
```bash
openssl rand -hex 32
```

И добавьте его в `.env`:
```
SECRET_KEY=ваш_сгенерированный_ключ
```

## Шаг 2: Запуск системы

```bash
docker-compose up --build
```

Первый запуск займет 5-10 минут (загрузка образов и сборка).

## Шаг 3: Проверка

Откройте в браузере:
- **Frontend (UI)**: http://localhost:8501
- **API Docs**: http://localhost:8000/docs
- **C++ Health**: http://localhost:8080/health

## Шаг 4: Использование

1. **Регистрация**: На фронтенде создайте аккаунт
2. **Создайте карточку**: Вкладка "Person Cards" → Create New Card
3. **Загрузите документ**: Вкладка "Documents" → выберите карточку → загрузите .txt или .md файл
4. **Задайте вопрос**: Вкладка "Chat" → введите вопрос по документу

## Остановка

```bash
docker-compose down
```

Или с удалением данных:
```bash
docker-compose down -v
```

## Troubleshooting

**Если ChromaDB не запускается:**
```bash
docker-compose down -v
docker-compose up --build
```

**Если Python backend не видит C++:**
Проверьте логи:
```bash
docker-compose logs cpp_backend
docker-compose logs backend_python
```

**Если не хватает памяти:**
Увеличьте лимиты Docker (Settings → Resources).

## Тестирование без Docker

```bash
# 1. Запустите тесты структуры
./test_system.sh

# 2. Локальный запуск C++ (требует CMake)
cd backend_cpp && cmake . && make && ./cpp_backend

# 3. Локальный запуск Python (требует PostgreSQL)
cd backend_python
pip install -r requirements.txt
export DATABASE_URL="postgresql://user:pass@localhost/db"
export OPENAI_API_KEY="sk-..."
uvicorn main:app --reload
```

## Демо данные

Создайте тестовую карточку:
```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"username": "demo", "password": "demo123"}'

# Получите токен
TOKEN=$(curl -X POST http://localhost:8000/login \
  -d "username=demo&password=demo123" | jq -r .access_token)

# Создайте карточку
curl -X POST http://localhost:8000/cards \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "John Doe", "category": "scientist", "description": "Famous researcher"}'
```

## Следующие шаги

1. Загрузите реальные документы
2. Настройте категории под ваши нужды
3. Экспериментируйте с чанкингом (параметры в C++ backend)
4. Добавьте больше языков (система уже поддерживает multilingual)

---

Удачи на хакатоне! 🎉
