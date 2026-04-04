#!/bin/bash
#
# Автоматический деплой Hackathon проекта с Ollama
# Использование: curl -fsSL https://raw.githubusercontent.com/DikiePercy/hackathon/biber-core/scripts/deploy.sh | bash
#

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║     🚀 ДЕПЛОЙ HACKATHON ПРОЕКТА С OLLAMA                 ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Проверка, что скрипт запущен не от root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}❌ Не запускайте этот скрипт от root!${NC}"
   echo "Запустите от обычного пользователя с sudo правами:"
   echo "  curl -fsSL https://raw.githubusercontent.com/DikiePercy/hackathon/biber-core/scripts/deploy.sh | bash"
   exit 1
fi

# Проверка наличия sudo
if ! sudo -v; then
    echo -e "${RED}❌ У пользователя нет sudo прав${NC}"
    exit 1
fi

# Проверка системы
echo -e "${YELLOW}📋 Проверка системы...${NC}"
if ! command -v apt &> /dev/null; then
    echo -e "${RED}❌ Этот скрипт работает только на Debian/Ubuntu${NC}"
    exit 1
fi

# Проверка RAM
TOTAL_RAM=$(free -g | awk '/^Mem:/{print $2}')
if [ "$TOTAL_RAM" -lt 8 ]; then
    echo -e "${RED}⚠️  ВНИМАНИЕ: У вас только ${TOTAL_RAM}GB RAM${NC}"
    echo "Для llama3:8b рекомендуется минимум 16GB RAM"
    echo "Вы можете использовать более лёгкую модель (phi:2.7b)"
    read -p "Продолжить? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 1. Установка зависимостей
echo -e "${YELLOW}📦 Установка зависимостей...${NC}"
sudo apt update
sudo apt install -y git curl wget

# Установка Docker
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}🐳 Установка Docker...${NC}"
    sudo apt install -y docker.io docker-compose-v2
    sudo systemctl enable docker
    sudo systemctl start docker
    sudo usermod -aG docker $USER
    echo -e "${GREEN}✅ Docker установлен${NC}"
else
    echo -e "${GREEN}✅ Docker уже установлен${NC}"
fi

# 2. Установка Ollama
if ! command -v ollama &> /dev/null; then
    echo -e "${YELLOW}🤖 Установка Ollama...${NC}"
    curl -fsSL https://ollama.com/install.sh | sh
    echo -e "${GREEN}✅ Ollama установлен${NC}"
else
    echo -e "${GREEN}✅ Ollama уже установлен${NC}"
fi

# 3. Настройка Ollama
echo -e "${YELLOW}⚙️  Настройка Ollama...${NC}"
sudo mkdir -p /etc/systemd/system/ollama.service.d/
sudo tee /etc/systemd/system/ollama.service.d/override.conf > /dev/null << 'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_NUM_PARALLEL=2"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
EOF

sudo systemctl daemon-reload
sudo systemctl enable ollama
sudo systemctl restart ollama

# Ждём запуска Ollama
sleep 3

# Проверка
if curl -s http://localhost:11434/api/tags > /dev/null; then
    echo -e "${GREEN}✅ Ollama работает${NC}"
else
    echo -e "${RED}❌ Ollama не запустился${NC}"
    exit 1
fi

# 4. Загрузка модели
echo -e "${YELLOW}📥 Загрузка модели llama3:8b (это займёт несколько минут)...${NC}"
if [ "$TOTAL_RAM" -lt 12 ]; then
    echo -e "${YELLOW}⚠️  Мало RAM, загружаем лёгкую модель phi:2.7b${NC}"
    ollama pull phi:2.7b
    OLLAMA_MODEL="phi:2.7b"
else
    ollama pull llama3:8b
    OLLAMA_MODEL="llama3:8b"
fi

# Проверка модели
if ollama list | grep -q "$OLLAMA_MODEL"; then
    echo -e "${GREEN}✅ Модель $OLLAMA_MODEL загружена${NC}"
else
    echo -e "${RED}❌ Не удалось загрузить модель${NC}"
    exit 1
fi

# 5. Клонирование проекта
INSTALL_DIR="/srv/hackathon"
echo -e "${YELLOW}📥 Клонирование проекта в $INSTALL_DIR...${NC}"

if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}⚠️  Директория $INSTALL_DIR уже существует${NC}"
    read -p "Удалить и клонировать заново? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo rm -rf "$INSTALL_DIR"
    else
        echo "Используем существующую директорию"
        cd "$INSTALL_DIR"
        git pull origin biber-core || true
    fi
fi

if [ ! -d "$INSTALL_DIR" ]; then
    sudo git clone https://github.com/DikiePercy/hackathon.git "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"
sudo chown -R $USER:$USER "$INSTALL_DIR"
git checkout biber-core

echo -e "${GREEN}✅ Проект клонирован${NC}"

# 6. Создание директорий для данных
echo -e "${YELLOW}📁 Создание директорий для данных...${NC}"
sudo mkdir -p /srv/hackathon-data/{postgres,chroma,app}
sudo chown -R $USER:$USER /srv/hackathon-data
echo -e "${GREEN}✅ Директории созданы${NC}"

# 7. Настройка .env
echo -e "${YELLOW}🔧 Настройка .env...${NC}"

if [ ! -f .env ]; then
    cp .env.example .env
    
    # Генерируем безопасный SECRET_KEY
    SECRET_KEY=$(openssl rand -hex 32)
    sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" .env
    
    # Настраиваем Ollama
    sed -i "s/RAG_LLM_PROVIDER=.*/RAG_LLM_PROVIDER=ollama/" .env
    sed -i "s/RAG_EMBEDDING_PROVIDER=.*/RAG_EMBEDDING_PROVIDER=ollama/" .env
    sed -i "s/RAG_OLLAMA_MODEL=.*/RAG_OLLAMA_MODEL=$OLLAMA_MODEL/" .env
    
    # Production настройки
    sed -i "s/COOKIE_SECURE=.*/COOKIE_SECURE=false/" .env  # Поменяйте на true если есть SSL
    
    # Пути к данным
    echo "" >> .env
    echo "# Production data directories" >> .env
    echo "DB_DATA_DIR=/srv/hackathon-data/postgres" >> .env
    echo "CHROMA_DATA_DIR=/srv/hackathon-data/chroma" >> .env
    echo "APP_DATA_DIR=/srv/hackathon-data/app" >> .env
    
    echo -e "${GREEN}✅ .env файл создан${NC}"
    echo -e "${YELLOW}⚠️  Не забудьте изменить ADMIN_PASSWORD в .env!${NC}"
else
    echo -e "${YELLOW}⚠️  .env уже существует, не изменяем${NC}"
fi

# 8. Запуск Docker контейнеров
echo -e "${YELLOW}🐳 Сборка и запуск Docker контейнеров...${NC}"
echo "Это займёт несколько минут..."

# Из-за того что мы добавили пользователя в группу docker,
# нужно перелогиниться. Используем newgrp для этой сессии.
newgrp docker << EOFGRP
docker-compose build
docker-compose up -d
EOFGRP

echo -e "${GREEN}✅ Контейнеры запущены${NC}"

# 9. Ожидание запуска
echo -e "${YELLOW}⏳ Ожидание запуска сервисов (30 секунд)...${NC}"
sleep 30

# 10. Проверка работы
echo -e "${YELLOW}🔍 Проверка работы...${NC}"

# Проверка контейнеров
if docker-compose ps | grep -q "Up"; then
    echo -e "${GREEN}✅ Контейнеры запущены${NC}"
else
    echo -e "${RED}❌ Не все контейнеры запущены${NC}"
    docker-compose ps
    exit 1
fi

# Проверка health endpoint
if curl -s http://localhost:8000/health | grep -q "ok"; then
    echo -e "${GREEN}✅ Backend работает!${NC}"
    curl -s http://localhost:8000/health
else
    echo -e "${RED}❌ Backend не отвечает${NC}"
    echo "Проверьте логи: docker-compose logs python_backend"
    exit 1
fi

# Финальные инструкции
echo ""
echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║              🎉 ДЕПЛОЙ ЗАВЕРШЁН УСПЕШНО!                 ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo -e "${GREEN}✅ Проект установлен в: ${NC}$INSTALL_DIR"
echo -e "${GREEN}✅ Модель Ollama: ${NC}$OLLAMA_MODEL"
echo ""
echo -e "${YELLOW}📋 Следующие шаги:${NC}"
echo ""
echo "1. Измените пароль администратора:"
echo "   cd $INSTALL_DIR"
echo "   nano .env  # Найдите ADMIN_PASSWORD и измените"
echo "   docker-compose restart python_backend"
echo ""
echo "2. Проверьте работу:"
echo "   curl http://localhost:8000/health"
echo "   curl http://localhost"
echo ""
echo "3. Настройте Nginx и SSL (см. QUICK_DEPLOY.md):"
echo "   cat $INSTALL_DIR/QUICK_DEPLOY.md"
echo ""
echo "4. Настройте firewall:"
echo "   sudo ufw allow 22/tcp"
echo "   sudo ufw allow 80/tcp"
echo "   sudo ufw allow 443/tcp"
echo "   sudo ufw enable"
echo ""
echo -e "${GREEN}📚 Документация:${NC}"
echo "   - $INSTALL_DIR/QUICK_DEPLOY.md - быстрый старт"
echo "   - $INSTALL_DIR/DEPLOYMENT_WITH_OLLAMA.md - полная документация"
echo "   - $INSTALL_DIR/OLLAMA_RU.md - инструкция по Ollama"
echo ""
echo -e "${GREEN}🌐 Доступ:${NC}"
echo "   - Frontend: http://$(hostname -I | awk '{print $1}')"
echo "   - API: http://$(hostname -I | awk '{print $1}'):8000"
echo "   - Streamlit: http://$(hostname -I | awk '{print $1}'):8501"
echo ""
echo -e "${YELLOW}⚠️  ВАЖНО:${NC}"
echo "   - Измените ADMIN_PASSWORD в .env"
echo "   - Настройте SSL сертификат для production"
echo "   - Настройте firewall"
echo ""
echo -e "${GREEN}🚀 Готово к использованию!${NC}"
echo ""
