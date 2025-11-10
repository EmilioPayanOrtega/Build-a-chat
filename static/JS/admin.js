const socket = io();
let currentChatId = null;
let chats = {}; // Almacena el historial por cliente

const chatBox = document.getElementById("chat-box");
const chatList = document.getElementById("chat-list");
const messageInput = document.getElementById("message");
const sendButton = document.getElementById("send");

// Registrar al admin
socket.emit("admin_connected");

// Mostrar lista de clientes conectados
socket.on("client_list", (clients) => {
    chatList.innerHTML = "";
    clients.forEach((client) => {
        const btn = document.createElement("button");
        btn.textContent = `${client.name} (ID: ${client.id})`;
        btn.addEventListener("click", () => openChat(client.id, client.name));
        chatList.appendChild(btn);
    });
});

// Abrir chat con un cliente
function openChat(clientId, clientName) {
    currentChatId = clientId;
    document.getElementById("chat-header").textContent = `Chat con ${clientName}`;
    chatBox.innerHTML = "";

    if (!chats[clientId]) chats[clientId] = [];

    // Cargar historial del cliente
    chats[clientId].forEach((msg) => addMessageToChat(msg));
}

// Enviar mensaje al cliente seleccionado
sendButton.addEventListener("click", sendMessage);
messageInput.addEventListener("keypress", function (event) {
    if (event.key === "Enter") sendMessage();
});

function sendMessage() {
    const message = messageInput.value.trim();
    if (message === "" || !currentChatId) return;

    const timestamp = getCurrentTimestamp();

    const data = {
        to: currentChatId,
        text: message,
        sender: "Admin",
        timestamp: timestamp
    };

    socket.emit("admin_message", data);
    addMessageToChat(data);

    // Guardar historial
    if (!chats[currentChatId]) chats[currentChatId] = [];
    chats[currentChatId].push(data);

    messageInput.value = "";
}

// Recibir mensaje de un cliente
socket.on("message_from_client", (data) => {
    if (!data.timestamp) data.timestamp = getCurrentTimestamp();

    if (!chats[data.user_id]) chats[data.user_id] = [];
    chats[data.user_id].push(data);

    // Mostrar solo si el chat actual coincide
    if (currentChatId === data.user_id) {
        addMessageToChat(data);
    } else {
        // Opcional: marcar visualmente que hay mensaje nuevo
        highlightChat(data.user_id);
    }
});

// Agregar mensaje al chat
function addMessageToChat(data) {
    const messageElement = document.createElement("div");
    messageElement.classList.add(
        data.sender === "Admin" ? "own-message" : "other-message"
    );

    // Si el mensaje tiene audio
    if (data.audio_url) {
        const button = document.createElement("button");
        button.textContent = data.text || "▶ Reproducir";
        button.classList.add("play-button");
        button.addEventListener("click", () => {
            const audio = new Audio(data.audio_url);
            audio.play();
        });
        messageElement.appendChild(button);
    } else {
        messageElement.textContent = `${data.sender}: ${data.text} (${data.timestamp})`;
    }

    chatBox.appendChild(messageElement);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// Destacar chats con mensajes nuevos
function highlightChat(clientId) {
    const buttons = chatList.querySelectorAll("button");
    buttons.forEach((btn) => {
        if (btn.textContent.includes(`ID: ${clientId}`)) {
            btn.style.backgroundColor = "#cde3ff";
            setTimeout(() => (btn.style.backgroundColor = "#fff"), 1500);
        }
    });
}

// Obtener timestamp legible
function getCurrentTimestamp() {
    const now = new Date();
    return now.toLocaleString("es-MX", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
    });
}
