#!/bin/bash
# Quick fix для проблемы с GEMINI_API_KEY

echo "🔧 Исправление GEMINI_API_KEY..."
echo ""

# Проверка .env
if [ ! -f .env ]; then
    echo "❌ .env файл не найден!"
    exit 1
fi

# Проверка что ключ есть в .env
if ! grep -q "GEMINI_API_KEY=" .env; then
    echo "❌ GEMINI_API_KEY не найден в .env"
    exit 1
fi

echo "✓ .env файл найден"
echo "✓ GEMINI_API_KEY присутствует"
echo ""

# Проверка docker-compose
if ! docker-compose ps >/dev/null 2>&1; then
    echo "⚠️  Docker compose не запущен"
    echo "Запускаю все сервисы..."
    docker-compose up -d
    echo ""
    echo "⏳ Ожидание запуска (30 сек)..."
    sleep 30
else
    echo "✓ Docker compose запущен"
    echo ""
    echo "🔄 Перезапуск python_backend..."
    docker-compose restart python_backend
    echo ""
    echo "⏳ Ожидание перезапуска (10 сек)..."
    sleep 10
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Проверка переменной окружения в контейнере:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if docker-compose exec -T python_backend env | grep -q "GEMINI_API_KEY="; then
    echo "✅ GEMINI_API_KEY загружен в контейнер!"
    KEY_VALUE=$(docker-compose exec -T python_backend env | grep "GEMINI_API_KEY=" | cut -d= -f2)
    if [ -n "$KEY_VALUE" ] && [ "$KEY_VALUE" != "" ]; then
        echo "✅ Ключ не пустой (длина: ${#KEY_VALUE} символов)"
    else
        echo "⚠️  Ключ пустой! Проверь .env файл"
    fi
else
    echo "❌ GEMINI_API_KEY НЕ загружен в контейнер"
    echo ""
    echo "Попробуй полный перезапуск:"
    echo "   docker-compose down"
    echo "   docker-compose up -d"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Проверка логов на наличие ошибок:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

docker-compose logs python_backend --tail=20 | grep -i "error\|warning\|gemini" || echo "Ошибок не найдено"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Исправление завершено!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Теперь обнови страницу в браузере и попробуй снова"
echo ""
