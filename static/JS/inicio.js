// static/JS/inicio.js
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

// DOM
const chatBox = document.getElementById("chat-box");
const messageInput = document.getElementById("message");
const sendButton = document.getElementById("send");
const menuButton = document.getElementById("menu-btn"); // debe existir en index.html

// listeners
sendButton.addEventListener("click", sendMessage);
messageInput.addEventListener("keypress", (event) => {
    if (event.key === "Enter") sendMessage();
});
if (menuButton) {
    menuButton.addEventListener("click", () => {
        // Enviamos un "menu" como mensaje para que el servidor lo registre y emita show_menu
        socket.emit("message", { text: "menu", timestamp: getCurrentTimestamp() });
    });
}

// utilidades
function getCurrentTimestamp() {
    return new Date().toISOString();
}
function formatTimestamp(iso) {
    try {
        const d = new Date(iso);
        if (isNaN(d)) return iso || "";
        return d.toLocaleString("es-MX", {
            year: "numeric", month: "2-digit", day: "2-digit",
            hour: "2-digit", minute: "2-digit", second: "2-digit"
        });
    } catch {
        return iso || "";
    }
}

function clearMenus() {
    document.querySelectorAll(".menu-container, .submenu-container, .info-container, .image-container").forEach(el => el.remove());
}

// crea botón estándar (configurable)
function createButton(label, id, className, emitEvent) {
    const btn = document.createElement("button");
    btn.textContent = label;
    btn.className = className;
    btn.dataset.id = id;
    btn.addEventListener("click", () => {
        clearMenus();
        // Para consistencia usamos los eventos que el servidor espera
        socket.emit(emitEvent, { id });
    });
    return btn;
}

function addReturnButton(container) {
    const returnBtn = document.createElement("button");
    returnBtn.textContent = "Regresar al menú principal";
    returnBtn.className = "submenu-button";
    returnBtn.addEventListener("click", () => {
        // pedir al servidor que muestre el menú principal
        socket.emit("return_to_main_menu");
    });
    if (container) container.appendChild(returnBtn);
}

// === Recepción de mensajes generales ===
socket.on("message", (data) => {
    // Si no tiene timestamp lo completamos
    if (!data.timestamp) data.timestamp = getCurrentTimestamp();

    // Mensaje con audio
    if (data.audio_url) {
        const audioWrapper = document.createElement("div");
        audioWrapper.classList.add("audio-wrapper", data.sender === userName ? "own-message" : "other-message");

        const btn = document.createElement("button");
        btn.type = "button";
        btn.classList.add("audio-button");
        btn.innerText = "▶";
        btn.addEventListener("click", () => {
            const audio = new Audio(data.audio_url);
            audio.play();
        });

        const ts = document.createElement("div");
        ts.classList.add("audio-ts");
        ts.innerText = formatTimestamp(data.timestamp);

        audioWrapper.appendChild(btn);
        audioWrapper.appendChild(ts);
        chatBox.appendChild(audioWrapper);
        chatBox.scrollTop = chatBox.scrollHeight;
        return;
    }

    // Mensaje de texto normal
    const messageElement = document.createElement("div");
    messageElement.classList.add(data.sender === userName ? "own-message" : "other-message");
    const time = formatTimestamp(data.timestamp);
    messageElement.textContent = `${data.sender}: ${data.text} ${time ? `(${time})` : ""}`;
    chatBox.appendChild(messageElement);
    chatBox.scrollTop = chatBox.scrollHeight;
});

// === Menú dinámico enviado por servidor ===
// show_menu -> payload: { menu: [ {id,label,type}, ... ] }
socket.on("show_menu", (data) => {
    clearMenus();

    const menu = Array.isArray(data?.menu) ? data.menu : [];
    const container = document.createElement("div");
    container.classList.add("menu-container");

    const title = document.createElement("div");
    title.classList.add("menu-message");
    title.textContent = "Menú Principal";
    container.appendChild(title);

    if (menu.length === 0) {
        const p = document.createElement("p");
        p.textContent = "No hay opciones disponibles.";
        container.appendChild(p);
    } else {
        menu.forEach(item => {
            // item tiene { id, label, type }
            const btn = createButton(item.label, item.id, "menu-button", "menu_option_selected");
            container.appendChild(btn);
        });
    }

    chatBox.appendChild(container);
    chatBox.scrollTop = chatBox.scrollHeight;
});

// show_submenu -> payload: { submenu: [ {id,label,type}, ... ], parent_label?: string }
socket.on("show_submenu", (data) => {
    clearMenus();

    const submenu = Array.isArray(data?.submenu) ? data.submenu : [];
    const container = document.createElement("div");
    container.classList.add("submenu-container");

    const title = document.createElement("div");
    title.classList.add("menu-message");
    title.textContent = data?.parent_label ? `Submenú: ${data.parent_label}` : "Submenú";
    container.appendChild(title);

    if (submenu.length === 0) {
        const p = document.createElement("p");
        p.textContent = "No hay opciones en este submenú.";
        container.appendChild(p);
    } else {
        submenu.forEach(item => {
            const btn = createButton(item.label, item.id, "submenu-button", "submenu_option_selected");
            container.appendChild(btn);
        });
    }

    addReturnButton(container);
    chatBox.appendChild(container);
    chatBox.scrollTop = chatBox.scrollHeight;
});

// show_link -> payload: { label, link }
socket.on("show_link", (data) => {
    clearMenus();

    const container = document.createElement("div");
    container.classList.add("submenu-container");

    const link = document.createElement("a");
    link.href = data.link;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.classList.add("submenu-button");
    link.textContent = data.label || data.link || "Abrir enlace";

    // También añadimos un pequeño comportamiento para abrir en nueva pestaña (por si el estilo requiere botón)
    link.addEventListener("click", (e) => {
        // default ya abre en _blank; esto evita navegación en el mismo frame si el CSS cambia
        window.open(data.link, "_blank", "noopener");
    });

    container.appendChild(link);
    addReturnButton(container);
    chatBox.appendChild(container);
    chatBox.scrollTop = chatBox.scrollHeight;
});

// show_info -> payload: { label, text }
socket.on("show_info", (data) => {
    clearMenus();

    const container = document.createElement("div");
    container.classList.add("info-container", "other-message");

    const title = document.createElement("strong");
    title.textContent = data.label || "Información";
    container.appendChild(title);

    const p = document.createElement("p");
    p.textContent = data.text || "";
    container.appendChild(p);

    addReturnButton(container);
    chatBox.appendChild(container);
    chatBox.scrollTop = chatBox.scrollHeight;
});

// show_map -> payload: { image, label }
socket.on("show_map", (data) => {
    clearMenus();

    const container = document.createElement("div");
    container.classList.add("image-container", "other-message");

    const title = document.createElement("div");
    title.classList.add("menu-message");
    if (data.label) title.textContent = data.label;
    if (data.label) container.appendChild(title);

    const img = document.createElement("img");
    img.src = data.image;
    img.alt = data.label || "Imagen";
    img.classList.add("menu-image");
    container.appendChild(img);

    addReturnButton(container);
    chatBox.appendChild(container);
    chatBox.scrollTop = chatBox.scrollHeight;
});
