const socket = io();

// DOM
const chatListEl = document.getElementById('chat-list');
const selectedUserEl = document.getElementById('selected-user');
const selectedIdEl = document.getElementById('selected-id');
const chatBoxEl = document.querySelector('.chat-box'); // en admin.html existe .chat-box
const inputEl = document.getElementById('admin-message');
const sendBtn = document.getElementById('send-admin');

// Estado
let currentUserId = null;
const chats = {}; // { userId: [msgObj, ...] }
// msgObj: { text, timestamp, sender, audio_url? }

// -----------------------------
// Conectar y anunciar admin
// -----------------------------
socket.on('connect', () => {
    console.log('ADMIN: conectado al servidor');
    // Emitimos admin_join si el servidor lo soporta (no rompe si no existe handler)
    socket.emit('admin_join');
});

// -----------------------------
// Actualizar lista de clientes
// El servidor envía 'update_chat_list' como lista: [{user_id, name}, ...]
// -----------------------------
socket.on('update_chat_list', (clientes) => {
    chatListEl.innerHTML = '';

    if (!clientes || clientes.length === 0) {
        const p = document.createElement('p');
        p.textContent = 'No hay clientes conectados';
        p.style.padding = '10px';
        chatListEl.appendChild(p);
        return;
    }

    clientes.forEach(cl => {
        const id = cl.user_id;
        const name = cl.name || 'Invitado';

        // crear elemento
        const item = document.createElement('button');
        item.className = 'chat-button';
        item.dataset.userId = id;
        item.style.display = 'block';
        item.style.width = '100%';
        item.style.textAlign = 'left';
        item.style.padding = '10px';
        item.style.marginBottom = '8px';
        item.style.borderRadius = '6px';
        item.style.border = '1px solid #ccc';
        item.style.background = (currentUserId === id) ? '#e6f0ff' : '#fff';

        // mostrar nombre + id corto
        const shortId = id.length > 10 ? id.slice(0, 8) + '...' : id;
        item.innerHTML = `<strong>${escapeHtml(name)}</strong><br><small>ID: ${shortId}</small>`;

        // marca de nuevo mensaje
        if (chats[id] && chats[id].some(m => m._unread)) {
            const badge = document.createElement('span');
            badge.textContent = ' • Nuevo';
            badge.style.color = '#d9534f';
            badge.style.marginLeft = '6px';
            item.querySelector('strong').after(badge);
        }

        item.addEventListener('click', () => {
            selectChat(id, name);
        });

        chatListEl.appendChild(item);
    });
});

// -----------------------------
// Seleccionar chat y pedir historial
// -----------------------------
function selectChat(userId, name) {
    currentUserId = userId;
    selectedUserEl.textContent = name || 'Invitado';
    selectedIdEl.textContent = userId;

    // quitar clase active visual
    Array.from(chatListEl.children).forEach(ch => {
        ch.style.background = (ch.dataset.userId === userId) ? '#e6f0ff' : '#fff';
        ch.classList.remove('new-message');
    });

    // limpiar visual
    clearChatBox();

    // pedir historial al servidor
    socket.emit('admin_select_chat', { user_id: userId });
}

// -----------------------------
// Recibir historial
// -----------------------------
socket.on('chat_history', (messages) => {
    // El servidor responde directamente SOLO para la sala del admin que pidió
    // messages es array de {text, timestamp, sender, audio_url?}
    if (!currentUserId) {
        // Si no hay chat seleccionado, guardamos en una clave temporal? No — ignoramos.
        return;
    }

    // Guardar (sobrescribir historial para el usuario actual)
    chats[currentUserId] = (messages || []).map(msg => ({ ...msg, _unread: false }));

    // Renderizar
    renderChatForCurrent();
});

// -----------------------------
// Recibir mensajes (broadcast desde servidor) -> 'message_admin'
// payload: { user_id, message }
// message: { text, timestamp, sender, audio_url? }
// -----------------------------
socket.on('message_admin', (payload) => {
    try {
        const userId = payload.user_id;
        const msg = payload.message;

        if (!userId || !msg) return;

        // inicializar array si no existe
        if (!chats[userId]) chats[userId] = [];

        // Dedupe simple: evitamos insertar si ya existe un mensaje igual (por texto+timestamp+sender)
        const exists = chats[userId].some(m => m.text === msg.text && String(m.timestamp) === String(msg.timestamp) && m.sender === msg.sender);
        if (!exists) {
            // si el admin envió este mensaje, el servidor lo re-broadcast; en ese caso lo añadimos también
            chats[userId].push({ ...msg, _unread: currentUserId !== userId });

            // Si es el chat abierto, renderizar
            if (currentUserId === userId) {
                renderMessage(msg);
                // marcar como leído
                chats[userId].forEach(m => { m._unread = false; });
            } else {
                // resaltar en la lista que hay nuevo mensaje
                const el = [...chatListEl.children].find(c => c.dataset.userId === userId);
                if (el) el.classList.add('new-message');
            }
        }
    } catch (e) {
        console.error('Error al procesar message_admin', e);
    }
});

// -----------------------------
// Enviar mensaje como admin
// NO renderizamos localmente aquí para evitar duplicados.
// Esperamos al broadcast 'message_admin' para mostrarlo.
// -----------------------------
function sendAdminMessage() {
    if (!currentUserId) {
        alert('Selecciona primero un cliente de la lista.');
        return;
    }
    const text = inputEl.value.trim();
    if (!text) return;

    const payload = {
        user_id: currentUserId,
        text: text,
        timestamp: new Date().toISOString()
    };

    // Enviar al servidor. El servidor responderá con 'message_admin' broadcast que vamos a recibir.
    socket.emit('admin_message', payload);

    // limpiar input (no renderizamos aquí para evitar duplicados)
    inputEl.value = '';
}

sendBtn.addEventListener('click', sendAdminMessage);
inputEl.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendAdminMessage();
});

// -----------------------------
// Helpers UI
// -----------------------------
function clearChatBox() {
    if (!chatBoxEl) return;
    chatBoxEl.innerHTML = '';
}

function renderChatForCurrent() {
    if (!currentUserId) return;
    clearChatBox();
    const arr = chats[currentUserId] || [];
    arr.forEach(m => renderMessage(m));
    // marcar leidos
    arr.forEach(m => m._unread = false);
    scrollToBottom();
}

function renderMessage(msg) {
    if (!chatBoxEl) return;
    const wrapper = document.createElement('div');

    // decide clase (estética mínima; tu CSS puede mapear .own-message/.other-message)
    const isAdmin = msg.sender === 'Admin' || msg.sender === 'Administrador';
    wrapper.className = isAdmin ? 'own-message' : 'other-message';

    // mensaje de audio
    if (msg.audio_url) {
        const audioWrap = document.createElement('div');
        audioWrap.className = 'audio-wrapper';
        const btn = document.createElement('button');
        btn.className = 'audio-button';
        btn.type = 'button';
        btn.innerText = '▶';
        btn.addEventListener('click', () => {
            const audio = new Audio(msg.audio_url);
            audio.play();
        });
        audioWrap.appendChild(btn);

        // timestamp
        const ts = document.createElement('div');
        ts.className = 'audio-ts';
        ts.innerText = formatTimestamp(msg.timestamp);
        audioWrap.appendChild(ts);

        chatBoxEl.appendChild(audioWrap);
        return;
    }

    // texto
    const textEl = document.createElement('div');
    textEl.style.display = 'inline-block';
    textEl.style.padding = '8px 12px';
    textEl.style.borderRadius = '10px';
    textEl.style.maxWidth = '70%';
    textEl.style.wordBreak = 'break-word';
    textEl.style.background = isAdmin ? '#007bff' : '#fff';
    textEl.style.color = isAdmin ? '#fff' : '#000';
    textEl.innerText = `${msg.sender}: ${msg.text}`;

    // timestamp
    const tsEl = document.createElement('div');
    tsEl.style.fontSize = '12px';
    tsEl.style.color = '#666';
    tsEl.style.marginTop = '6px';
    tsEl.innerText = formatTimestamp(msg.timestamp);

    const container = document.createElement('div');
    container.style.margin = '6px 0';
    container.appendChild(textEl);
    container.appendChild(tsEl);

    // alineación
    container.style.alignSelf = isAdmin ? 'flex-end' : 'flex-start';

    chatBoxEl.appendChild(container);
    scrollToBottom();
}

function scrollToBottom() {
    if (!chatBoxEl) return;
    chatBoxEl.scrollTop = chatBoxEl.scrollHeight;
}

function formatTimestamp(iso) {
    if (!iso) return '';
    try {
        const d = new Date(iso);
        if (isNaN(d)) return iso;
        return d.toLocaleString('es-MX', {
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
    } catch {
        return iso;
    }
}

// escape html simple
function escapeHtml(s) {
    if (!s) return s;
    return s.replace(/[&<>"'`]/g, (m) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;', '`':'&#96;'})[m]);
}