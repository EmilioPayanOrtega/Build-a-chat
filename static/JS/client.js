const socket = io();
let userId = null;
let userName = null;

window.addEventListener("DOMContentLoaded", () => {
    userName = prompt("Ingresa tu nombre:");
    if (!userName) userName = "Invitado";
    document.getElementById("user-name").textContent = userName;
    socket.emit("register_name", { name: userName });
});

socket.on("connected", (data) => {
    userId = data.user_id;
    socket.emit("join");
});

// Genera ISO (UTC)
function getCurrentTimestamp() {
    return new Date().toISOString();
}

// Convierte ISO a formato local igual al invitado
function formatTimestampToLocal(iso) {
    if (!iso) return "";
    const date = new Date(iso);
    if (isNaN(date)) return iso;
    return date.toLocaleString("es-MX", {
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
messageInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") sendMessage();
});

function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;
    const timestamp = getCurrentTimestamp();
    socket.emit("message", { text: message, timestamp });
    addMessageToChat({ sender: userName, text: message, timestamp });
    messageInput.value = "";
}

socket.on("message", (data) => {
    // si por alguna razón falta timestamp, generamos uno local
    if (!data.timestamp) data.timestamp = getCurrentTimestamp();
    addMessageToChat(data);
});

function addMessageToChat(data) {
    // Si es un mensaje de solo audio (audio_url) lo renderizamos con wrapper especial
    if (data.audio_url) {
        // wrapper sin la burbuja blanca para audio
        const wrapper = document.createElement("div");
        wrapper.classList.add(data.sender === userName ? "own-message" : "other-message", "audio-wrapper");
        // botón circular solo con ▶
        const btn = document.createElement("button");
        btn.type = "button";
        btn.classList.add("audio-button");
        btn.innerText = "▶";
        btn.addEventListener("click", () => {
            const audio = new Audio(data.audio_url);
            audio.play();
        });
        wrapper.appendChild(btn);

        // opcional: mostrar timestamp pequeño debajo del botón (si quieres)
        const ts = formatTimestampToLocal(data.timestamp);
        if (ts) {
            const tsSpan = document.createElement("div");
            tsSpan.classList.add("audio-ts");
            tsSpan.innerText = ts;
            wrapper.appendChild(tsSpan);
        }

        chatBox.appendChild(wrapper);
        chatBox.scrollTop = chatBox.scrollHeight;
        return;
    }

    // Mensaje normal
    const messageElement = document.createElement("div");
    messageElement.classList.add(data.sender === userName ? "own-message" : "other-message");
    const time = formatTimestampToLocal(data.timestamp);
    messageElement.textContent = `${data.sender}: ${data.text} (${time})`;
    chatBox.appendChild(messageElement);
    chatBox.scrollTop = chatBox.scrollHeight;
}
