const socket = io();

let adminId = null;
let selectedClientId = null;
let clients = {}; // {clientId: {name, messages: []}}

// ===============================
// 1️⃣ Al iniciar, registra al admin
// ===============================
window.addEventListener("DOMContentLoaded", () => {
    const adminName = prompt("Ingresa tu nombre de administrador:") || "Administrador";
    document.getElementById("chat-header").textContent = `Panel del Admin - ${adminName}`;
    socket.emit("register_admin", { name: adminName });
});

// ===============================
// 2️⃣ Referencias del DOM
// ===============================
const chatList = document.getElementById("chat-list");
const chatBox = document.getElementById("chat-box");
const messageInput = document.getElementById("message");
const sendButton = document.getElementById("send");

sendButton.addEventListener("click", sendMessage);
messageInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") sendMessage();
});

// ===============================
// 3️⃣ Funciones de utilidad
// ===============================
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

// ===============================
// 4️⃣ Manejo de clientes conectados
// ===============================
socket.on("connected_clients", (data) => {
    clients = data.clients;
    renderClientList();
});

socket.on("new_client", (data) => {
    clients[data.id] = { name: data.name || "Invitado", messages: [] };
    renderClientList();
});

socket.on("client_disconnected", (clientId) => {
    delete clients[clientId];
    renderClientList();
});

// ===============================
// 5️⃣ Mostrar lista de clientes
// ===============================
function renderClientList() {
    chatList.innerHTML = "";
    Object.entries(clients).forEach(([id, client]) => {
        const btn = document.createElement("button");
        btn.textContent = `${client.name}\nID: ${id}`;
        btn.classList.add("client-btn");
        btn.addEventListener("click", () => selectClient(id));
        chatList.appendChild(btn);
    });
}

// ===============================
// 6️⃣ Seleccionar cliente y cargar chat
// ===============================
function selectClient(clientId) {
    selectedClientId = clientId;
    const client = clients[clientId];
    document.getElementById("chat-header").textContent = `Chat con ${client.name} (${clientId})`;
    renderChat(client.messages);
}

// ===============================
// 7️⃣ Envío de mensajes del admin
// ===============================
function sendMessage() {
    const text = messageInput.value.trim();
    if (!text || !selectedClientId) return;

    const timestamp = getCurrentTimestamp();
    const msg = {
        sender: "Administrador",
        text,
        timestamp,
        to: selectedClientId
    };

    socket.emit("admin_message", msg);
    addMessageToChat(msg);
    clients[selectedClientId].messages.push(msg);
    messageInput.value = "";
}

// ===============================
// 8️⃣ Recepción de mensajes de clientes
// ===============================
socket.on("client_message", (data) => {
    const { client_id, text, timestamp, sender, from_menu } = data;
    if (!clients[client_id]) {
        clients[client_id] = { name: sender || "Invitado", messages: [] };
    }

    const formatted = {
        sender: sender || "Invitado",
        text: from_menu
            ? `🧭 El cliente ${sender || "Invitado"} seleccionó: ${text}`
            : text,
        timestamp
    };

    clients[client_id].messages.push(formatted);

    // Si el admin está viendo ese chat, lo muestra
    if (selectedClientId === client_id) {
        addMessageToChat(formatted);
    }

    renderClientList();
});

// ===============================
// 9️⃣ Renderizar mensajes del chat
// ===============================
function renderChat(messages) {
    chatBox.innerHTML = "";
    messages.forEach((m) => addMessageToChat(m));
    chatBox.scrollTop = chatBox.scrollHeight;
}

function addMessageToChat(data) {
    const messageElement = document.createElement("div");
    const isOwn = data.sender === "Administrador";
    messageElement.classList.add(isOwn ? "own-message" : "other-message");

    const time = formatTimestampToLocal(data.timestamp);
    messageElement.textContent = `${data.sender}: ${data.text} (${time})`;

    chatBox.appendChild(messageElement);
    chatBox.scrollTop = chatBox.scrollHeight;
}
