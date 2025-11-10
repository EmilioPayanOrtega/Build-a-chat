from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime, timedelta
from threading import Lock
import time

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Control de sesiones
clients = {}  # { sid: {"id": int, "name": str, "last_active": datetime} }
admin_sid = None
client_id_counter = 1
lock = Lock()

# ======================
#       RUTAS
# ======================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/admin")
def admin_panel():
    return render_template("admin.html")


# ======================
#  FUNCIONES AUXILIARES
# ======================
def get_timestamp():
    """Devuelve un timestamp legible."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def remove_inactive_clients():
    """Desconecta clientes inactivos tras 10 minutos."""
    now = datetime.now()
    with lock:
        inactive = [
            sid for sid, data in clients.items()
            if now - data["last_active"] > timedelta(minutes=10)
        ]
        for sid in inactive:
            user_id = clients[sid]["id"]
            print(f"[AUTO-DISCONNECT] Cliente {user_id} por inactividad.")
            socketio.emit("client_disconnected", {"id": user_id}, to=admin_sid)
            leave_room(user_id)
            del clients[sid]


# ======================
#   EVENTOS DE SOCKETIO
# ======================

@socketio.on("connect")
def handle_connect():
    print(f"[INFO] Cliente conectado: {request.sid}")


@socketio.on("disconnect")
def handle_disconnect():
    global admin_sid
    sid = request.sid

    # Si es el admin
    if sid == admin_sid:
        print("[INFO] Admin desconectado.")
        admin_sid = None
        return

    # Si es un cliente
    if sid in clients:
        user_id = clients[sid]["id"]
        print(f"[INFO] Cliente {user_id} desconectado.")
        socketio.emit("client_disconnected", {"id": user_id}, to=admin_sid)
        del clients[sid]


@socketio.on("client_connected")
def client_connected(data=None):
    """Un cliente nuevo entra al chat."""
    global client_id_counter
    with lock:
        user_id = client_id_counter
        client_id_counter += 1

    name = f"Cliente {user_id}"
    clients[request.sid] = {"id": user_id, "name": name, "last_active": datetime.now()}

    join_room(user_id)
    print(f"[NUEVO CLIENTE] {name} conectado con ID {user_id}")

    emit("client_id", {"id": user_id, "name": name})
    update_admin_clients()


@socketio.on("admin_connected")
def admin_connected():
    """El administrador se conecta."""
    global admin_sid
    admin_sid = request.sid
    print("[ADMIN] Conectado")
    update_admin_clients()


def update_admin_clients():
    """Envía al admin la lista actualizada de clientes."""
    if admin_sid:
        client_list = [
            {"id": data["id"], "name": data["name"]}
            for data in clients.values()
        ]
        socketio.emit("client_list", client_list, to=admin_sid)


@socketio.on("client_message")
def handle_client_message(data):
    """Recibe mensaje del cliente y lo reenvía al admin."""
    sid = request.sid
    if sid not in clients:
        return

    clients[sid]["last_active"] = datetime.now()
    user_id = clients[sid]["id"]
    name = clients[sid]["name"]

    message = {
        "user_id": user_id,
        "sender": name,
        "text": data.get("text", ""),
        "timestamp": get_timestamp()
    }

    print(f"[MENSAJE CLIENTE] {name}: {message['text']}")

    # Reenviar al admin
    if admin_sid:
        socketio.emit("message_from_client", message, to=admin_sid)


@socketio.on("admin_message")
def handle_admin_message(data):
    """Recibe mensaje del admin y lo reenvía al cliente destino."""
    to_id = data.get("to")
    if not to_id:
        return

    message = {
        "sender": "Admin",
        "text": data.get("text", ""),
        "timestamp": data.get("timestamp", get_timestamp())
    }

    print(f"[MENSAJE ADMIN → {to_id}] {message['text']}")

    # Enviar al cliente correspondiente
    for sid, info in clients.items():
        if info["id"] == to_id:
            socketio.emit("message_from_admin", message, to=sid)
            break


# ======================
#   HILO DE LIMPIEZA
# ======================
def background_cleanup():
    while True:
        remove_inactive_clients()
        time.sleep(60)  # Verifica cada minuto

socketio.start_background_task(background_cleanup)


# ======================
#       MAIN
# ======================
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
