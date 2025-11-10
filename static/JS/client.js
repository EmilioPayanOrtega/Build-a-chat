const socket = io();
let userId = null;
let userName = null;

window.addEventListener("DOMContentLoaded", () => {
    userName = prompt("Ingresa tu nombre:");
    if (!userName) userName = "Invitado";

    document.getElementById("user-name").textContent = userName;
    socket.emit("register_name", { name: userName });
});

socket.on("connected", function (data) {
    userId = data.user_id;
    socket.emit("join");
});

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

const chatBox = document.getElementById("chat-box");
const messageInput = document.getElementById("message");
const sendButton = document.getElementById("send");

sendButton.addEventListener("click", sendMessage);
messageInput.addEventListener("keypress", function (event) {
    if (event.key === "Enter") sendMessage();
});

function sendMessage() {
    const message = messageInput.value.trim();
    if (message === "") return;

    const timestamp = getCurrentTimestamp();

    socket.emit("message", {
        text: message,
        timestamp: timestamp
    });

    // Mostrar el mensaje en la vista local inmediatamente
    addMessageToChat({
        sender: userName,
        text: message,
        timestamp: timestamp
    });

    messageInput.value = "";
}

// Escucha mensajes desde el servidor
socket.on("message", function (data) {
    // Asegura que siempre haya timestamp
    if (!data.timestamp) {
        data.timestamp = getCurrentTimestamp();
    }
    addMessageToChat(data);
});

// Función para mostrar mensajes en el chat
function addMessageToChat(data) {
    const messageElement = document.createElement("div");
    messageElement.classList.add(
        data.sender === userName ? "own-message" : "other-message"
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

