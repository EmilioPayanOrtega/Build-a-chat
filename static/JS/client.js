// static/JS/client.js
const socket = io();
let userId = null;
let userName = sessionStorage.getItem("user_name");

// track rendered messages to avoid duplicates
const renderedMessageIds = new Set();

// === Conexión inicial ===
window.addEventListener("DOMContentLoaded", () => {
    userName = sessionStorage.getItem("user_name");
    if (!userName) { // Si no existe, manda de regreso al login
        window.location.href = "/";
        return;
    }

    document.getElementById("user-name").textContent = userName;
    socket.emit("register_name", { name: userName });

    // Añadir botón "Enviar resumen (PDF)" fijo en la UI del cliente
    injectSummaryButton();
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

function isValidEmail(email) {
    // chequeo básico
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(email).toLowerCase());
}

const chatBox = document.getElementById("chat-box");
const messageInput = document.getElementById("message");
const sendButton = document.getElementById("send");
const menuButton = document.getElementById("menu-btn");

sendButton?.addEventListener("click", sendMessage);

// botón Menú = envía "menu"
menuButton?.addEventListener("click", () => {
    const timestamp = getCurrentTimestamp();
    socket.emit("message", { text: "menu", timestamp });
});

// Enter para enviar
messageInput?.addEventListener("keypress", (e) => {
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

    // TEXTO NORMAL (con timestamp separado)
    const wrapper = document.createElement("div");
    const isOwn = data.sender === userName;

    wrapper.style.display = "flex";
    wrapper.style.flexDirection = "column";
    wrapper.style.maxWidth = "80%";
    wrapper.style.alignSelf = isOwn ? "flex-end" : "flex-start";
    wrapper.style.margin = "6px 0";

    // Burbuja de texto
    const bubble = document.createElement("div");
    bubble.classList.add(isOwn ? "own-message" : "other-message");
    bubble.textContent = `${data.sender}: ${data.text}`;

    // Timestamp separado (debajo de la burbuja)
    const ts = document.createElement("div");
    ts.classList.add("timestamp");
    ts.style.fontSize = "12px";
    ts.style.color = "#666";
    ts.style.marginTop = "6px";
    ts.innerText = formatTimestampToLocal(data.timestamp);

    // Armado
    wrapper.appendChild(bubble);
    wrapper.appendChild(ts);

    chatBox.appendChild(wrapper);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// =====================
// SUMMARY (PDF) FLOW
// =====================

function injectSummaryButton() {
    // Crear botón flotante / fijo en la UI del cliente
    const container = document.createElement("div");
    container.id = "summary-container";
    container.style.position = "fixed";
    container.style.right = "20px";
    container.style.bottom = "20px";
    container.style.zIndex = "9999";

    const btn = document.createElement("button");
    btn.id = "summary-btn";
    btn.textContent = "📨 Enviar resumen (PDF)";
    btn.style.background = "var(--primary)";
    btn.style.color = "#fff";
    btn.style.border = "none";
    btn.style.padding = "10px 14px";
    btn.style.borderRadius = "8px";
    btn.style.cursor = "pointer";
    btn.style.boxShadow = "0 4px 12px rgba(0,0,0,0.12)";
    btn.addEventListener("click", onSummaryClick);

    container.appendChild(btn);
    document.body.appendChild(container);
}

function onSummaryClick() {
    // Pedir correo
    const email = prompt("Ingresa el correo donde deseas recibir el resumen (PDF):");
    if (!email) {
        alert("Operación cancelada.");
        return;
    }
    if (!isValidEmail(email)) {
        alert("Correo inválido. Intenta de nuevo.");
        return;
    }

    // Mostrar mensaje en el chat (no contiene link, solo confirmación)
    addMessageToChat({
        sender: "Sistema",
        text: `Se ha solicitado el envío del resumen al correo: ${email}. Se te notificará cuando esté listo.`,
        timestamp: getCurrentTimestamp()
    });

    // Deshabilitar botón mientras se procesa
    const btn = document.getElementById("summary-btn");
    if (btn) {
        btn.disabled = true;
        btn.style.opacity = "0.6";
        btn.textContent = "Generando resumen…";
    }

    // Emitir evento al backend — el backend usará SID para localizar el historial del usuario
    socket.emit("request_summary", { email });
}

// Escuchar resultado desde backend
// payload: { status: "ok"|"error", message: "texto descriptivo" }
socket.on("summary_result", (payload) => {
    const btn = document.getElementById("summary-btn");
    if (btn) {
        btn.disabled = false;
        btn.style.opacity = "1";
        btn.textContent = "📨 Enviar resumen (PDF)";
    }

    if (!payload) {
        addMessageToChat({
            sender: "Sistema",
            text: "Ocurrió un error: respuesta vacía del servidor.",
            timestamp: getCurrentTimestamp()
        });
        return;
    }

    if (payload.status === "ok") {
        addMessageToChat({
            sender: "Sistema",
            text: `Resumen enviado correctamente. ${payload.message || ""}`,
            timestamp: getCurrentTimestamp()
        });
    } else {
        addMessageToChat({
            sender: "Sistema",
            text: `Error al generar/enviar resumen: ${payload.message || "desconocido"}`,
            timestamp: getCurrentTimestamp()
        });
    }
});

// Para otros casos en que quieras mostrar progreso en pasos desde el servidor (opcional)
socket.on("summary_progress", (data) => {
    // data: { step: "texto corto", detail?: "..." }
    if (!data || !data.step) return;
    addMessageToChat({
        sender: "Sistema",
        text: `Progreso: ${data.step}${data.detail ? " — " + data.detail : ""}`,
        timestamp: getCurrentTimestamp()
    });
});
