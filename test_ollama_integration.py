#!/usr/bin/env python3
"""
Тестирование интеграции Ollama с RAG системой
"""
import os
import sys

# Настройка путей
sys.path.insert(0, '/home/adelete/hackathon/backend_python')

# Установка переменных окружения для теста
os.environ['RAG_LLM_PROVIDER'] = 'ollama'
os.environ['RAG_EMBEDDING_PROVIDER'] = 'ollama'
os.environ['OLLAMA_BASE_URL'] = 'http://localhost:11434'
os.environ['RAG_OLLAMA_MODEL'] = 'llama3:8b'
os.environ['CHROMA_PATH'] = '/tmp/test_chroma'

print("=" * 60)
print("ТЕСТ ИНТЕГРАЦИИ OLLAMA С RAG СИСТЕМОЙ")
print("=" * 60)
print()

# Тест 1: Импорт модулей
print("1. Тестирование импорта модулей...")
try:
    from rag_engine import _build_llm, _build_embeddings, generate_answer
    print("   ✓ Модули импортированы успешно")
except Exception as e:
    print(f"   ✗ Ошибка импорта: {e}")
    sys.exit(1)

# Тест 2: Инициализация Embeddings
print()
print("2. Тестирование Ollama Embeddings...")
try:
    embeddings = _build_embeddings()
    print(f"   ✓ Embeddings инициализированы: {type(embeddings).__name__}")
except Exception as e:
    print(f"   ✗ Ошибка инициализации embeddings: {e}")
    sys.exit(1)

# Тест 3: Генерация вектора
print()
print("3. Тестирование генерации векторов...")
try:
    test_text = "Привет мир"
    vector = embeddings.embed_query(test_text)
    print(f"   ✓ Вектор сгенерирован, размерность: {len(vector)}")
except Exception as e:
    print(f"   ✗ Ошибка генерации вектора: {e}")
    sys.exit(1)

# Тест 4: Инициализация LLM
print()
print("4. Тестирование Ollama LLM...")
try:
    llm = _build_llm()
    print(f"   ✓ LLM инициализирован: {type(llm).__name__}")
except Exception as e:
    print(f"   ✗ Ошибка инициализации LLM: {e}")
    sys.exit(1)

# Тест 5: Генерация текста
print()
print("5. Тестирование генерации ответа...")
print("   (это может занять несколько секунд при первом запуске)")
try:
    context = [
        "Алматы — крупнейший город Казахстана.",
        "Население Алматы составляет около 2 миллионов человек."
    ]
    query = "Сколько человек живёт в Алматы?"
    answer = generate_answer(query=query, context_docs=context)
    print(f"   ✓ Ответ сгенерирован!")
    print(f"\n   Вопрос: {query}")
    print(f"   Ответ: {answer}")
except Exception as e:
    print(f"   ✗ Ошибка генерации: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 60)
print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
print("=" * 60)
print()
print("Ваша RAG система готова к работе с Ollama!")
print("Теперь вы можете использовать веб-интерфейс для загрузки")
print("документов и задавания вопросов.")
