
### 🎯 Рекомендации для production:

- [ ] Добавить retry logic (httpx-retry или tenacity)
- [ ] Circuit breaker для C++ backend (если часто падает)
- [ ] Metrics/logging для мониторинга C++ вызовов
- [ ] Health check в background task (не блокировать startup)
