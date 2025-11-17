const socket = io();
let userId = null;
let userName = null;

// track rendered messages to avoid duplicates
const renderedMessageIds = new Set();

// === Conexión inicial ===
window.addEventListener("DOMContentLoaded", () => {
    let userName = sessionStorage.getItem("user_name");
    if (!userName){ //Si no existe, manda de regreso al login
        window.location.href = "/";
        return;
    }

    document.getElementById("user-name").textContent = userName;
    socket.emit("register_name", { name: userName });
});

window.addEventListener("beforeunload", () => {
  sessionStorage.removeItem("user_name");
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
const menuButton = document.getElementById("menu-btn");

sendButton.addEventListener("click", sendMessage);

// botón Menú = envía "menu"
menuButton?.addEventListener("click", () => {
    const timestamp = getCurrentTimestamp();
    socket.emit("message", { text: "menu", timestamp });
});

// Enter para enviar
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

// === Recepción ===
socket.on("message", (data) => {
    if (!data) return;
    if (!data.timestamp) data.timestamp = getCurrentTimestamp();
    if (data.message_id && renderedMessageIds.has(data.message_id)) return;
    addMessageToChat(data);
});

// === Renderizado ===
function addMessageToChat(data) {
    if (data.message_id) renderedMessageIds.add(data.message_id);

    // AUDIO
    if (data.audio_url) {
        const wrapper = document.createElement("div");
        wrapper.classList.add(
            data.sender === userName ? "own-message" : "other-message",
            "audio-wrapper"
        );

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

    // TEXTO NORMAL
    const div = document.createElement("div");
    div.classList.add(data.sender === userName ? "own-message" : "other-message");
    const ts = formatTimestampToLocal(data.timestamp);
    div.textContent = `${data.sender}: ${data.text} ${ts ? `(${ts})` : ""}`;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// === MENÚ PRINCIPAL ===
socket.on("show_menu", (data) => {
    addMessageToChat({
        sender: "Tecbot",
        text: "Aquí está el menú principal. Selecciona una opción:",
        timestamp: getCurrentTimestamp()
    });

    const menuDiv = document.createElement("div");
    menuDiv.classList.add("menu-container");

    if (Array.isArray(data.menu) && data.menu.length > 0) {
        data.menu.forEach(item => {
            const btn = document.createElement("button");
            btn.classList.add("menu-button");
            btn.dataset.id = item.id;
            btn.textContent = `🔹 ${item.label}`;
            btn.addEventListener("click", () => {
                socket.emit("menu_option_selected", { id: item.id });
            });
            menuDiv.appendChild(btn);
        });
    } else {
        const error = document.createElement("p");
        error.textContent = "No se pudo cargar el menú.";
        menuDiv.appendChild(error);
    }

    chatBox.appendChild(menuDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
});

// === INFO ===
socket.on("show_info", (data) => {
    addMessageToChat({
        sender: "Tecbot",
        text: `${data.label}: ${data.text}`,
        timestamp: getCurrentTimestamp()
    });
});

// === LINKS (FUSIONADO: abre la URL directamente) ===
socket.on("show_link", (data) => {
    addMessageToChat({
        sender: "Tecbot",
        text: `Abriendo: ${data.label}`,
        timestamp: getCurrentTimestamp()
    });

    // *** ESTA ES LA PARTE QUE TE FALTABA ***
    if (data.link) {
        window.open(data.link, "_blank");
    }
});

// === SUBMENÚ ===
socket.on("show_submenu", (data) => {
    addMessageToChat({
        sender: "Tecbot",
        text: data?.parent_label
            ? `Submenú de ${data.parent_label}:`
            : "Submenú:",
        timestamp: getCurrentTimestamp()
    });

    const menuDiv = document.createElement("div");
    menuDiv.classList.add("menu-container");

    if (Array.isArray(data.submenu) && data.submenu.length > 0) {
        data.submenu.forEach(item => {
            const btn = document.createElement("button");
            btn.classList.add("menu-button");
            btn.dataset.id = item.id;
            btn.textContent = `🔹 ${item.label}`;
            btn.addEventListener("click", () => {
                socket.emit("submenu_option_selected", { id: item.id });
            });
            menuDiv.appendChild(btn);
        });
    }

    chatBox.appendChild(menuDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
});

// === IMÁGENES ===
socket.on("show_map", (data) => {
    addMessageToChat({
        sender: "Tecbot",
        text: `Mostrando: ${data.label}`,
        timestamp: getCurrentTimestamp()
    });

    const img = document.createElement("img");
    img.src = data.image;
    img.alt = data.label || "Imagen";
    img.classList.add("menu-image");
    chatBox.appendChild(img);
    chatBox.scrollTop = chatBox.scrollHeight;
});
