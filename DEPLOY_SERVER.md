# Ubuntu Server Deployment

This guide provides a simple zip-based deployment flow with one start script.

## One script

- `scripts/start.sh` - builds and starts services from local files.

## 1. Prepare server

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin unzip
sudo usermod -aG docker $USER
```

Re-login, then check:

```bash
docker --version
docker compose version
```

## 2. Upload and unpack zip

```bash
mkdir -p ~/hackathon && cd ~/hackathon
unzip hackathon.zip
```

## 3. Configure environment

```bash
cp .env.example .env
nano .env
```

Set at minimum:

- `SECRET_KEY`
- `GEMINI_API_KEY`

Recommended for persistent data outside project directory:

- `DB_DATA_DIR=/srv/hackathon-data/postgres`
- `CHROMA_DATA_DIR=/srv/hackathon-data/chroma`
- `APP_DATA_DIR=/srv/hackathon-data/app`

## 4. Start

```bash
chmod +x scripts/*.sh
./scripts/start.sh
```

Check status:

```bash
docker compose ps
curl http://localhost:8000/health
```

## 5. Update with new zip

1. Replace project files with new zip contents.
2. Run again:

```bash
./scripts/start.sh
```

## Useful operations

View logs:

```bash
docker compose logs -f python_backend
docker compose logs -f frontend
docker compose logs -f db
```

Restart services:

```bash
docker compose restart
```

Stop stack without deleting data:

```bash
docker compose down
```

## Important safety rules

- Do not use `docker compose down -v` in production if you need to keep DB data.
- Keep `.env` only on server; do not commit secrets.
