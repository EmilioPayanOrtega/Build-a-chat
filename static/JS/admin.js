// -----------------------------
// Panel de Administración
// -----------------------------

const socket = io();

// Contenedores
const chatList = document.getElementById('chat-list');
const selectedUser = document.getElementById('selected-user');
const selectedId = document.getElementById('selected-id');
const chatWindow = document.querySelector('.chat-window');
const messageInput = document.getElementById('admin-message');
const sendButton = document.getElementById('send-admin');

// Estado actual
let currentUserId = null;
let chats = {}; // { user_id: [mensajes] }

// Al conectar, avisamos que somos admin
socket.on('connect', () => {
    console.log('Conectado al servidor como ADMIN.');
    socket.emit('admin_join');
});

// -----------------------------
// ACTUALIZAR LISTA DE CLIENTES
// -----------------------------
socket.on('update_chat_list', (clientes) => {
    chatList.innerHTML = '';

    if (!clientes || clientes.length === 0) {
        chatList.innerHTML = '<p class="no-clients">No hay clientes conectados.</p>';
        return;
    }

    clientes.forEach(cliente => {
        const item = document.createElement('div');
        item.classList.add('chat-item');
        item.dataset.userId = cliente.user_id;
        item.innerHTML = `
            <strong>${cliente.name}</strong>
            <span class="client-id">${cliente.user_id.substring(0, 6)}...</span>
        `;

        // Al hacer clic, seleccionar chat
        item.addEventListener('click', () => {
            seleccionarChat(cliente.user_id, cliente.name);
        });

        chatList.appendChild(item);
    });
});

// -----------------------------
// SELECCIONAR CHAT
// -----------------------------
function seleccionarChat(userId, name) {
    currentUserId = userId;
    selectedUser.textContent = name;
    selectedId.textContent = userId.substring(0, 6) + '...';
    document.querySelectorAll('.chat-item').forEach(i => i.classList.remove('active'));
    const activo = [...chatList.children].find(i => i.dataset.userId === userId);
    if (activo) activo.classList.add('active');

    // Limpiar ventana
    const messagesBox = ensureMessagesBox();
    messagesBox.innerHTML = '';

    // Solicitar historial
    socket.emit('admin_select_chat', { user_id: userId });
}

// -----------------------------
// RECIBIR HISTORIAL DEL CHAT
// -----------------------------
socket.on('chat_history', (messages) => {
    if (!currentUserId) return;
    chats[currentUserId] = messages || [];

    const messagesBox = ensureMessagesBox();
    messagesBox.innerHTML = '';

    messages.forEach(msg => renderMessage(msg, messagesBox));

    scrollToBottom(messagesBox);
});

// -----------------------------
// NUEVOS MENSAJES EN TIEMPO REAL
// -----------------------------
socket.on('message_admin', (data) => {
    const { user_id, message } = data;
    if (!chats[user_id]) chats[user_id] = [];
    chats[user_id].push(message);

    // Si el chat actual es el seleccionado, mostrarlo
    if (currentUserId === user_id) {
        const messagesBox = ensureMessagesBox();
        renderMessage(message, messagesBox);
        scrollToBottom(messagesBox);
    }

    // Resaltar si hay mensaje nuevo en otro chat
    if (currentUserId !== user_id) {
        const item = [...chatList.children].find(i => i.dataset.userId === user_id);
        if (item) item.classList.add('new-message');
    }
});

// -----------------------------
// ENVIAR MENSAJE COMO ADMIN
// -----------------------------
function enviarMensaje() {
    if (!currentUserId) {
        alert('Selecciona un chat primero.');
        return;
    }

    const text = messageInput.value.trim();
    if (text === '') return;

    const msg = {
        user_id: currentUserId,
        text: text,
        timestamp: new Date().toISOString(),
    };

    socket.emit('admin_message', msg);
    messageInput.value = '';

    const messagesBox = ensureMessagesBox();
    renderMessage({ text, sender: 'Admin', timestamp: msg.timestamp }, messagesBox);
    scrollToBottom(messagesBox);
}

sendButton.addEventListener('click', enviarMensaje);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') enviarMensaje();
});

// -----------------------------
// UTILIDADES DE INTERFAZ
// -----------------------------

function ensureMessagesBox() {
    let box = chatWindow.querySelector('.chat-box');
    if (!box) {
        box = document.createElement('div');
        box.classList.add('chat-box');
        chatWindow.insertBefore(box, chatWindow.querySelector('.chat-input'));
    }
    return box;
}

function renderMessage(msg, container) {
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('message');
    msgDiv.classList.add(msg.sender === 'Admin' ? 'sent' : 'received');

    let content = '';

    if (msg.audio_url) {
        content = `<audio controls src="${msg.audio_url}" class="audio-message"></audio>`;
    } else if (msg.text) {
        content = `<p>${msg.text}</p>`;
    }

    msgDiv.innerHTML = `
        <div class="message-content">
            <span class="sender">${msg.sender}</span>
            ${content}
            <span class="timestamp">${formatTime(msg.timestamp)}</span>
        </div>
    `;

    container.appendChild(msgDiv);
}

function scrollToBottom(container) {
    container.scrollTop = container.scrollHeight;
}

function formatTime(timestamp) {
    try {
        const date = new Date(timestamp);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
        return '';
    }
}
