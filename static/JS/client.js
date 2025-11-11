const socket = io();
let userId = null;
let userName = null;

// === Conexión inicial ===
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

// === Utilidades ===
function getCurrentTimestamp() {
    return new Date().toISOString();
}

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

// === Envío de mensajes ===
function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;
    const timestamp = getCurrentTimestamp();
    socket.emit("message", { text: message, timestamp });
    messageInput.value = "";
}

// === Recepción de mensajes ===
socket.on("message", (data) => {
    if (!data.timestamp) data.timestamp = getCurrentTimestamp();
    addMessageToChat(data);
});

// === Renderizado de mensajes ===
function addMessageToChat(data) {
    // Mensaje con audio
    if (data.audio_url) {
        const wrapper = document.createElement("div");
        wrapper.classList.add(data.sender === userName ? "own-message" : "other-message", "audio-wrapper");

        const btn = document.createElement("button");
        btn.type = "button";
        btn.classList.add("audio-button");
        btn.innerText = "▶";
        btn.addEventListener("click", () => {
            const audio = new Audio(data.audio_url);
            audio.play();
        });
        wrapper.appendChild(btn);

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

// === Eventos del menú ===
socket.on("show_menu", () => {
    addMessageToChat({
        sender: "Tecbot",
        text: "Aquí está el menú principal. Selecciona una opción:",
        timestamp: getCurrentTimestamp()
    });

    const menuDiv = document.createElement("div");
    menuDiv.classList.add("menu-container");
    menuDiv.innerHTML = `
        <button class="menu-btn" data-id="option1">🔹 Opción 1</button>
        <button class="menu-btn" data-id="option2">🔹 Opción 2</button>
        <button class="menu-btn" data-id="option3">🔹 Opción 3</button>
    `;
    chatBox.appendChild(menuDiv);
    chatBox.scrollTop = chatBox.scrollHeight;

    menuDiv.querySelectorAll(".menu-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const id = btn.getAttribute("data-id");
            socket.emit("menu_option_selected", { id });
        });
    });
});

socket.on("show_link", (data) => {
    addMessageToChat({
        sender: "Tecbot",
        text: `${data.label}: ${data.link}`,
        timestamp: getCurrentTimestamp()
    });
});

socket.on("show_info", (data) => {
    addMessageToChat({
        sender: "Tecbot",
        text: `${data.label}: ${data.text}`,
        timestamp: getCurrentTimestamp()
    });
});

socket.on("show_submenu", (data) => {
    addMessageToChat({
        sender: "Tecbot",
        text: "Submenú:",
        timestamp: getCurrentTimestamp()
    });

    const submenuDiv = document.createElement("div");
    submenuDiv.classList.add("menu-container");

    data.submenu.forEach(item => {
        const btn = document.createElement("button");
        btn.classList.add("menu-btn");
        btn.textContent = `🔹 ${item.label}`;
        btn.addEventListener("click", () => {
            socket.emit("submenu_option_selected", { id: item.id });
        });
        submenuDiv.appendChild(btn);
    });

    chatBox.appendChild(submenuDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
});

socket.on("show_map", (data) => {
    addMessageToChat({
        sender: "Tecbot",
        text: `Mostrando: ${data.label}`,
        timestamp: getCurrentTimestamp()
    });

    const img = document.createElement("img");
    img.src = data.image;
    img.alt = data.label;
    img.classList.add("menu-image");
    chatBox.appendChild(img);
    chatBox.scrollTop = chatBox.scrollHeight;
});

