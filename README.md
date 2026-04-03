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
