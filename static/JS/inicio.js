// ===============================
// Socket.IO
// ===============================
const socket = io();
let userId = null;
let userName = null;

window.addEventListener("DOMContentLoaded", () => {
    let userName = sessionStorage.getItem("user_name");
    if (!userName){ //Si no existe, manda de regreso al login
        window.location.href = "/";
        return;
    }

    document.getElementById("user-name").textContent = userName;
    socket.emit("register_name", { name: userName });
});

socket.on("connected", (data) => {
    userId = data.user_id;
    socket.emit("join");
});

// ===============================
// DOM
// ===============================
const chatBox = document.getElementById("chat-box");
const messageInput = document.getElementById("message");
const sendButton = document.getElementById("send");
const menuButton = document.getElementById("menu-btn");

// ===============================
// Listeners
// ===============================
sendButton.addEventListener("click", sendMessage);
messageInput.addEventListener("keypress", (event) => {
    if (event.key === "Enter") sendMessage();
});

if (menuButton) {
    menuButton.addEventListener("click", () => {
        socket.emit("message", { text: "menu", timestamp: getCurrentTimestamp() });
    });
}

// ===============================
// Utilidades
// ===============================
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
    document.querySelectorAll(".menu-container, .submenu-container, .info-container, .image-container")
        .forEach(el => el.remove());
}

// ===============================
// Botón universal (MEJORADO)
// — Ahora soporta abrir links directamente
// ===============================
function createButton(label, id, className, emitEvent, extraData = null) {
    const btn = document.createElement("button");
    btn.textContent = label;
    btn.className = className;
    btn.dataset.id = id;

    btn.addEventListener("click", () => {
        clearMenus();

        // 🔥 Comportamiento para LINKS
        if (extraData && extraData.type === "link" && extraData.link) {
            window.open(extraData.link, "_blank", "noopener");
            return;
        }

        // Comportamiento normal
        socket.emit(emitEvent, { id });
    });

    return btn;
}

function addReturnButton(container) {
    const returnBtn = document.createElement("button");
    returnBtn.textContent = "Regresar al menú principal";
    returnBtn.className = "submenu-button";
    returnBtn.addEventListener("click", () => {
        socket.emit("return_to_main_menu");
    });
    container.appendChild(returnBtn);
}

// ===============================
// Mostrar mensajes normales
// ===============================
socket.on("message", (data) => {
    if (!data.timestamp) data.timestamp = getCurrentTimestamp();

    // --- AUDIO ---
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

    // --- TEXTO NORMAL ---
    const div = document.createElement("div");
    const isOwn = data.sender === userName;
    div.classList.add(isOwn ? "own-message" : "other-message");
    if (isOwn){                         /* Forzar alineación */
        div.style.marginLeft = "auto";
        div.style.marginRight = "0";
    }
    const ts = formatTimestampToLocal(data.timestamp);
    div.textContent = `${data.sender}: ${data.text} ${ts ? `(${ts})` : ""}`;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
});

// ===============================
// MENÚ PRINCIPAL
// ===============================
socket.on("show_menu", (data) => {
    clearMenus();

    const menu = Array.isArray(data?.menu) ? data.menu : [];
    const container = document.createElement("div");
    container.classList.add("menu-container");

    const title = document.createElement("div");
    title.classList.add("menu-message");
    title.textContent = "Menú Principal";
    container.appendChild(title);

    menu.forEach(item => {
        const btn = createButton(
            item.label,
            item.id,
            "menu-button",
            "menu_option_selected",
            item // <-- importante para soporte de links
        );
        container.appendChild(btn);
    });

    chatBox.appendChild(container);
    chatBox.scrollTop = chatBox.scrollHeight;
});

// ===============================
// SUBMENÚ
// ===============================
socket.on("show_submenu", (data) => {
    clearMenus();

    const submenu = Array.isArray(data?.submenu) ? data.submenu : [];
    const container = document.createElement("div");
    container.classList.add("submenu-container");

    const title = document.createElement("div");
    title.classList.add("menu-message");
    title.textContent = data?.parent_label ? `Submenú: ${data.parent_label}` : "Submenú";
    container.appendChild(title);

    submenu.forEach(item => {
        const btn = createButton(
            item.label,
            item.id,
            "submenu-button",
            "submenu_option_selected",
            item // <-- soporte de links
        );
        container.appendChild(btn);
    });

    addReturnButton(container);
    chatBox.appendChild(container);
    chatBox.scrollTop = chatBox.scrollHeight;
});

// ===============================
// ENLACE (versión limpia)
// ===============================
socket.on("show_link", (data) => {
    clearMenus();

    const container = document.createElement("div");
    container.classList.add("submenu-container");

    const btn = document.createElement("button");
    btn.className = "submenu-button";
    btn.textContent = data.label || "Abrir enlace";

    btn.addEventListener("click", () => {
        window.open(data.link, "_blank", "noopener");
    });

    container.appendChild(btn);
    addReturnButton(container);

    chatBox.appendChild(container);
    chatBox.scrollTop = chatBox.scrollHeight;
});

// ===============================
// INFO
// ===============================
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

// ===============================
// MAPA
// ===============================
socket.on("show_map", (data) => {
    clearMenus();

    const container = document.createElement("div");
    container.classList.add("image-container", "other-message");

    if (data.label) {
        const title = document.createElement("div");
        title.classList.add("menu-message");
        title.textContent = data.label;
        container.appendChild(title);
    }

    const img = document.createElement("img");
    img.src = data.image;
    img.alt = data.label || "Imagen";
    img.classList.add("menu-image");
    container.appendChild(img);

    addReturnButton(container);
    chatBox.appendChild(container);
    chatBox.scrollTop = chatBox.scrollHeight;
});

// ===============================
// Enviar mensaje
// ===============================
function sendMessage() {
    const msg = messageInput.value.trim();
    if (msg === "") return;

    socket.emit("message", { text: msg, timestamp: getCurrentTimestamp() });
    messageInput.value = "";
}
