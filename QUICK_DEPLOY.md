# 🚀 Быстрый деплой с Ollama

## 📋 Минимальные требования

- **CPU:** 4+ ядра
- **RAM:** 16GB (для llama3:8b)
- **Диск:** 50GB SSD
- **OS:** Ubuntu 22.04 LTS

## ⚡ Быстрый старт (5 минут)

### 1. Подключитесь к серверу

```bash
ssh user@your-server.com
```

### 2. Запустите автоматический деплой

```bash
# Скачайте и запустите скрипт
curl -fsSL https://raw.githubusercontent.com/DikiePercy/hackathon/biber-core/scripts/deploy.sh | bash
```

**ИЛИ вручную:**

```bash
# 1. Установите зависимости
sudo apt update && sudo apt install -y git docker.io docker-compose-v2 curl

# 2. Установите Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3:8b

# 3. Настройте Ollama
sudo mkdir -p /etc/systemd/system/ollama.service.d/
echo '[Service]' | sudo tee /etc/systemd/system/ollama.service.d/override.conf
echo 'Environment="OLLAMA_HOST=0.0.0.0:11434"' | sudo tee -a /etc/systemd/system/ollama.service.d/override.conf
sudo systemctl daemon-reload && sudo systemctl restart ollama

# 4. Клонируйте проект
cd /srv
sudo git clone https://github.com/DikiePercy/hackathon.git
sudo chown -R $USER:$USER hackathon
cd hackathon && git checkout biber-core

# 5. Настройте .env
cp .env.example .env
nano .env  # Измените SECRET_KEY, ADMIN_PASSWORD

# Или автоматически:
SECRET_KEY=$(openssl rand -hex 32)
sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" .env
sed -i "s/RAG_LLM_PROVIDER=.*/RAG_LLM_PROVIDER=ollama/" .env
sed -i "s/RAG_EMBEDDING_PROVIDER=.*/RAG_EMBEDDING_PROVIDER=ollama/" .env
sed -i "s/COOKIE_SECURE=.*/COOKIE_SECURE=true/" .env

# 6. Создайте директории для данных
sudo mkdir -p /srv/hackathon-data/{postgres,chroma,app}
sudo chown -R $USER:$USER /srv/hackathon-data

# 7. Запустите
docker-compose up -d

# 8. Проверьте
sleep 15
curl http://localhost:8000/health
```

**Ожидаемый результат:**
```json
{"status":"ok","cpp_backend":"ok","persons":21,"documents":0,"chunks":0}
```

---

## 🌐 Настройка домена и SSL

### 1. Установите Nginx

```bash
sudo apt install nginx certbot python3-certbot-nginx
```

### 2. Создайте конфигурацию

```bash
sudo tee /etc/nginx/sites-available/hackathon << 'EOF'
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    location / {
        return 301 https://$server_name$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    client_max_body_size 10M;
    
    location / {
        proxy_pass http://localhost:80;
        proxy_set_header Host $host;
    }
    
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_read_timeout 300s;
    }
    
    location /auth {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/hackathon /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
```

### 3. Получите SSL сертификат

```bash
sudo systemctl stop nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
sudo systemctl start nginx
```

---

## 🔥 Настройка Firewall

```bash
sudo apt install ufw
sudo ufw allow 22/tcp    # SSH (ВАЖНО!)
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw --force enable
```

**ВАЖНО:** НЕ открывайте порт 11434 (Ollama должен быть доступен только локально)

---

## 📊 Проверка работы

```bash
# Статус сервисов
docker-compose ps

# Логи
docker-compose logs -f python_backend

# Ollama
sudo systemctl status ollama

# Тест API
curl https://yourdomain.com/health
```

---

## 🔄 Обновление проекта

```bash
cd /srv/hackathon
git pull origin biber-core
docker-compose build
docker-compose down && docker-compose up -d
```

---

## 💡 Оптимизация

### Используйте более быструю модель

```bash
# Для слабого сервера (8GB RAM)
ollama pull phi:2.7b

# Обновите .env
echo "RAG_OLLAMA_MODEL=phi:2.7b" >> .env
docker-compose restart python_backend
```

### Ограничьте параллельные запросы к Ollama

```bash
sudo tee -a /etc/systemd/system/ollama.service.d/override.conf << 'EOF'
Environment="OLLAMA_NUM_PARALLEL=2"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
EOF

sudo systemctl daemon-reload
sudo systemctl restart ollama
```

---

## 🌍 Рекомендуемые хостинг провайдеры

| Провайдер | Конфигурация | Цена | Ссылка |
|-----------|--------------|------|--------|
| **Contabo** | 8 vCPU, 30GB RAM | $13/мес | [contabo.com](https://contabo.com) |
| **Hetzner** | CPX41 (8 vCPU, 16GB RAM) | $25/мес | [hetzner.com](https://hetzner.com) |
| **DigitalOcean** | 8GB RAM, 4 vCPU | $48/мес | [digitalocean.com](https://digitalocean.com) |

**Рекомендация:** Contabo для лучшего соотношения цена/качество

---

## 🚨 Частые проблемы

### Ollama не доступен из Docker

```bash
# Проверьте
sudo ss -tlnp | grep 11434

# Должно быть: 0.0.0.0:11434
# Если 127.0.0.1:11434, то настройте override.conf (см. выше)
```

### Out of Memory

```bash
# Используйте меньшую модель
ollama pull phi:2.7b
echo "RAG_OLLAMA_MODEL=phi:2.7b" >> /srv/hackathon/.env
docker-compose restart python_backend
```

### Медленно работает

**Решения:**
1. Используйте сервер с GPU
2. Увеличьте RAM
3. Используйте более лёгкую модель (phi:2.7b)

---

## 📞 Поддержка

Полная документация: `DEPLOYMENT_WITH_OLLAMA.md`

---

**Готово! Ваш проект работает на production! 🎉**

Откройте: `https://yourdomain.com`
