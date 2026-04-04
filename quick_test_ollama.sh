#!/bin/bash
# Быстрая проверка интеграции Ollama

set -e

compose_exec() {
    if docker compose version >/dev/null 2>&1; then
        docker compose exec -T python_backend "$@"
        return
    fi
    if command -v docker-compose >/dev/null 2>&1; then
        docker-compose exec -T python_backend "$@"
        return
    fi
    echo "   ❌ Docker Compose not found"
    exit 1
}

echo "╔════════════════════════════════════════════════════════╗"
echo "║        ПРОВЕРКА ИНТЕГРАЦИИ OLLAMA С RAG               ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Функция для проверки
check() {
    if [ $? -eq 0 ]; then
        echo "   ✅ OK"
    else
        echo "   ❌ ОШИБКА"
        exit 1
    fi
}

# 1. Ollama
echo "1️⃣  Проверка Ollama..."
curl -s http://localhost:11434/api/tags > /dev/null
check

# 2. Модель llama3:8b
echo "2️⃣  Проверка модели llama3:8b..."
curl -s http://localhost:11434/api/tags | grep -q "llama3:8b"
check

# 3. Backend
echo "3️⃣  Проверка Python backend..."
curl -s http://localhost:8000/health > /dev/null
check

# 4. Конфигурация
echo "4️⃣  Проверка конфигурации backend..."
compose_exec env | grep -q "RAG_LLM_PROVIDER=ollama"
check

# 5. RAG модули
echo "5️⃣  Проверка RAG модулей..."
compose_exec python3 -c "from rag_engine import _build_llm, _build_embeddings; _build_llm(); _build_embeddings()" 2>&1 | grep -v "Warning" | grep -v "FutureWarning" | grep -v "Deprecation" > /dev/null
check

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║              ✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!                ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "🎉 Ваша RAG система работает с Ollama!"
echo ""
echo "Доступные интерфейсы:"
echo "  • HTML:      http://localhost"
echo "  • Streamlit: http://localhost:8501"
echo "  • API:       http://localhost:8000"
echo ""
echo "Следующие шаги:"
echo "  1. Откройте веб-интерфейс"
echo "  2. Войдите с учётными данными администратора"
echo "  3. Загрузите документы"
echo "  4. Задавайте вопросы!"
echo ""
