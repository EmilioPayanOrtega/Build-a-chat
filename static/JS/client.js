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

function getCurrentTimestamp() {
    return new Date().toISOString(); // formato ISO UTC
}

function formatTimestampToLocal(iso) {
    if (!iso) return "";
    try {
        const date = new Date(iso);
        return date.toLocaleString("es-MX", {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit"
        });
    } catch {
        return iso;
    }
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
    if (message === "") return;

    const timestamp = getCurrentTimestamp();

    socket.emit("message", { text: message, timestamp });

    addMessageToChat({
        sender: userName,
        text: message,
        timestamp
    });

    messageInput.value = "";
}

socket.on("message", (data) => {
    if (!data.timestamp) data.timestamp = getCurrentTimestamp();
    addMessageToChat(data);
});

function addMessageToChat(data) {
    const messageElement = document.createElement("div");
    messageElement.classList.add(
        data.sender === userName ? "own-message" : "other-message"
    );

    const time = formatTimestampToLocal(data.timestamp);

    if (data.audio_url) {
        const button = document.createElement("button");
        button.innerHTML = `▶ ${data.text || ""}`;
        button.classList.add("play-button");
        button.style.display = "inline-flex";
        button.style.alignItems = "center";
        button.style.padding = "6px 10px";
        button.style.borderRadius = "8px";
        button.style.cursor = "pointer";
        button.style.whiteSpace = "nowrap";
        button.addEventListener("click", () => {
            const audio = new Audio(data.audio_url);
            audio.play();
        });
        messageElement.appendChild(button);
    } else {
        messageElement.textContent = `${data.sender}: ${data.text} (${time})`;
    }

    chatBox.appendChild(messageElement);
    chatBox.scrollTop = chatBox.scrollHeight;
}
