document.addEventListener("DOMContentLoaded", () => {
    const chatHistory = document.getElementById("chatHistory");
    const chatInput = document.getElementById("chatInput");
    const sendBtn = document.getElementById("sendBtn");

    function sendMessage() {
        const text = chatInput.value.trim();
        if (!text) return;

        // 1. Отрисовываем сообщение пользователя
        appendMessage(text, "user");
        chatInput.value = "";

        // 2. Показываем индикатор загрузки ИИ
        const loadingId = appendMessage("Печатает...", "ai");

        // 3. TODO ДЛЯ БЭКЕНДЕРОВ: Здесь должен быть запрос к вашему API
        // Пример (заглушка):
        /*
        fetch('/api/ask-gemini', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: text })
        })
        .then(response => response.json())
        .then(data => {
            updateMessage(loadingId, data.answer);
        })
        .catch(error => {
            updateMessage(loadingId, "Ошибка соединения с сервером.");
        });
        */

        // Временная имитация ответа для теста фронтенда
        setTimeout(() => {
            updateMessage(loadingId, "Это тестовый ответ. Бэкенд с Gemini скоро будет подключен!");
        }, 1500);
    }

    function appendMessage(text, sender) {
        const msgDiv = document.createElement("div");
        msgDiv.classList.add("message", sender);
        msgDiv.textContent = text;
        
        // Генерируем уникальный ID, чтобы потом обновить текст (для лоадера)
        const id = "msg-" + Date.now();
        msgDiv.id = id;

        chatHistory.appendChild(msgDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight; // Скролл вниз
        return id;
    }

    function updateMessage(id, text) {
        const msgDiv = document.getElementById(id);
        if (msgDiv) {
            msgDiv.textContent = text;
        }
    }

    // Обработчики событий: клик по кнопке и нажатие Enter
    sendBtn.addEventListener("click", sendMessage);
    chatInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") sendMessage();
    });
});