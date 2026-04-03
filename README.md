# FastAPI Backend Starter

Минимальный бэкенд на FastAPI с двумя группами эндпоинтов:
- health-check
- CRUD-пример для items (в памяти)

## Установка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Запуск

```bash
python run.py
```

Приложение будет доступно по адресу:
- http://localhost:8000
- Swagger UI: http://localhost:8000/docs

## Эндпоинты

- GET /health
- GET /items
- GET /items/{item_id}
- POST /items

Пример тела для POST /items:

```json
{
	"name": "Laptop",
	"description": "For demo"
}
```
