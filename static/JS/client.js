const socket = io();
let userId = null;
let userName = null;

// track rendered messages to avoid duplicates (usa message_id si el servidor lo envía)
const renderedMessageIds = new Set();

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
const menuButton = document.getElementById("menu-btn");

sendButton.addEventListener("click", sendMessage);

// botón Menú: en vez de emitir un evento custom, enviamos un mensaje "menu"
// así el servidor lo tratará igual que si el usuario escribiera "menu"
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
    // no renderizamos localmente para evitar duplicados; esperamos al broadcast del servidor
    socket.emit("message", { text: message, timestamp });

    // si el usuario escribió "menu" manualmente también lo maneja el servidor (ya lo enviamos)
    messageInput.value = "";
}

// === Recepción de mensajes ===
socket.on("message", (data) => {
    if (!data) return;
    if (!data.timestamp) data.timestamp = getCurrentTimestamp();
    // dedupe por message_id si viene
    if (data.message_id && renderedMessageIds.has(data.message_id)) return;
    addMessageToChat(data);
});

// === Renderizado de mensajes ===
function addMessageToChat(data) {
    // marca message_id como renderizado
    if (data.message_id) renderedMessageIds.add(data.message_id);

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
    messageElement.textContent = `${data.sender}: ${data.text} ${time ? `(${time})` : ""}`;
    chatBox.appendChild(messageElement);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// === Eventos del menú ===
// El servidor envía: emit('show_menu', {'menu': [...top items...]})
socket.on("show_menu", (data) => {
    // evita que se muestre repetidas veces (opcional): siempre mostramos
    addMessageToChat({
        sender: "Tecbot",
        text: "Aquí está el menú principal. Selecciona una opción:",
        timestamp: getCurrentTimestamp()
    });

    const menuDiv = document.createElement("div");
    menuDiv.classList.add("menu-container");

    // data.menu debe ser array con items {id, label, type}
    if (data && Array.isArray(data.menu) && data.menu.length > 0) {
        data.menu.forEach(item => {
            const btn = document.createElement("button");
            btn.classList.add("menu-btn");
            btn.dataset.id = item.id;
            btn.textContent = `🔹 ${item.label}`;
            btn.addEventListener("click", () => {
                socket.emit("menu_option_selected", { id: item.id });
            });
            menuDiv.appendChild(btn);
        });
    } else {
        const errorText = document.createElement("p");
        errorText.textContent = "No se pudo cargar el menú. Intenta de nuevo más tarde.";
        menuDiv.appendChild(errorText);
    }

    chatBox.appendChild(menuDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
});

// servidor envía enlace
socket.on("show_link", (data) => {
    addMessageToChat({
        sender: "Tecbot",
        text: `${data.label}: ${data.link}`,
        timestamp: getCurrentTimestamp()
    });
});

// servidor envía info
socket.on("show_info", (data) => {
    addMessageToChat({
        sender: "Tecbot",
        text: `${data.label}: ${data.text}`,
        timestamp: getCurrentTimestamp()
    });
});

// servidor envía submenu: { submenu: [ {id,label,...} ], parent_label? }
socket.on("show_submenu", (data) => {
    addMessageToChat({
        sender: "Tecbot",
        text: data?.parent_label ? `Submenú de ${data.parent_label}:` : "Submenú:",
        timestamp: getCurrentTimestamp()
    });

    const menuDiv = document.createElement("div");
    menuDiv.classList.add("menu-container");

    if (data && Array.isArray(data.submenu) && data.submenu.length > 0) {
        data.submenu.forEach(item => {
            const btn = document.createElement("button");
            btn.classList.add("menu-btn");
            btn.dataset.id = item.id;
            btn.textContent = `🔹 ${item.label}`;
            btn.addEventListener("click", () => {
                socket.emit("submenu_option_selected", { id: item.id });
            });
            menuDiv.appendChild(btn);
        });
    } else {
        menuDiv.innerHTML = `
            <button class="menu-btn" data-id="option1">🔹 Opción 1</button>
            <button class="menu-btn" data-id="option2">🔹 Opción 2</button>
            <button class="menu-btn" data-id="option3">🔹 Opción 3</button>
        `;
        // attach listeners to fallback buttons
        menuDiv.querySelectorAll(".menu-btn").forEach(b => {
            b.addEventListener("click", () => {
                const id = b.dataset.id;
                socket.emit("submenu_option_selected", { id });
            });
        });
    }

    chatBox.appendChild(menuDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
});

// mostrar mapa/imágen
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
