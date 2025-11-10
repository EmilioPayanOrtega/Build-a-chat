const socket = io();
const chatList = document.getElementById("chat-list");
const chatBox = document.getElementById("chat-box");
const messageInput = document.getElementById("admin-message");
const sendButton = document.getElementById("send-admin");

let selectedChat = null;
const adminId = "Admin";

function getCurrentTimestamp() {
    return new Date().toISOString();
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

sendButton.addEventListener("click", sendMessage);
messageInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") sendMessage();
});

function sendMessage() {
    const message = messageInput.value.trim();
    if (message && selectedChat) {
        const messageData = {
            user_id: selectedChat,
            text: message,
            sender: adminId,
            timestamp: getCurrentTimestamp()
        };
        socket.emit("admin_message", messageData);
        messageInput.value = "";
    }
}

function displayMessage(data) {
    const messageElement = document.createElement("div");
    const senderIsAdmin = data.sender === "Admin";
    const senderLabel = senderIsAdmin ? "Tú" : data.sender;
    const humanTs = formatTimestampToLocal(data.timestamp);

    if (data.audio_url) {
        const button = document.createElement("button");
        button.innerHTML = `▶ ${senderLabel}: ${data.text || ""}`;
        button.classList.add("play-button");
        button.style.display = "inline-flex";
        button.style.alignItems = "center";
        button.style.padding = "6px 10px";
        button.style.borderRadius = "8px";
        button.addEventListener("click", () => {
            const audio = new Audio(data.audio_url);
            audio.play();
        });
        messageElement.appendChild(button);
    } else {
        messageElement.textContent = ` ${senderLabel}: ${data.text} (${humanTs})`;
    }

    messageElement.classList.add(senderIsAdmin ? "own-message" : "other-message");
    chatBox.appendChild(messageElement);
    chatBox.scrollTop = chatBox.scrollHeight;
}

socket.on("update_chat_list", (clients) => {
    chatList.innerHTML = "";
    clients.forEach((client) => {
        const name = client.name || "Invitado";
        const clientElement = document.createElement("button");
        clientElement.innerHTML = `<strong>${name}</strong><br><small>ID: ${client.user_id}</small>`;
        clientElement.classList.add("chat-button");
        clientElement.addEventListener("click", () => {
            selectedChat = client.user_id;
            document.getElementById("selected-user").textContent = name;
            document.getElementById("selected-id").textContent = client.user_id;
            socket.emit("admin_select_chat", { user_id: selectedChat });
        });
        chatList.appendChild(clientElement);
    });
});

socket.on("chat_history", (messages) => {
    chatBox.innerHTML = "";
    messages.forEach((msg) => displayMessage(msg));
});

socket.on("message_admin", (data) => {
    if (selectedChat === data.user_id) {
        displayMessage(data.message);
    }
});
