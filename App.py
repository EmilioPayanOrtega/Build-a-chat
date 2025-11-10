from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
from datetime import datetime

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# ==============================
# Diccionarios de usuarios
# ==============================
clients = {}        # { sid: {"name": "Invitado", "room": "user_x"} }
admins = {}         # { sid: {"name": "Admin"} }

# ==============================
# Rutas principales
# ==============================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/audio/<path:filename>')
def serve_audio(filename):
    return send_from_directory('static/audio', filename)

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory('static/images', filename)

# ==============================
# Funciones de utilidad
# ==============================
def current_time():
    return datetime.now().isoformat()

def broadcast_clients():
    """Envia al admin la lista actualizada de clientes conectados"""
    client_data = {sid: {"name": info["name"]} for sid, info in clients.items()}
    socketio.emit("connected_clients", {"clients": client_data}, to=list(admins.keys()))

# ==============================
# Eventos de conexión
# ==============================
@socketio.on("connect")
def handle_connect():
    print(f"🔌 Nueva conexión: {request.sid}")

@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid
    if sid in clients:
        name = clients[sid]["name"]
        print(f"❌ Cliente desconectado: {name}")
        del clients[sid]
        socketio.emit("client_disconnected", sid, to=list(admins.keys()))
    elif sid in admins:
        print(f"🧹 Admin desconectado: {admins[sid]['name']}")
        del admins[sid]
    broadcast_clients()

# ==============================
# Registro de clientes
# ==============================
@socketio.on("register_name")
def handle_register_name(data):
    name = data.get("name", "Invitado")
    sid = request.sid
    clients[sid] = {"name": name, "room": sid}
    join_room(sid)
    emit("connected", {"user_id": sid})
    print(f"👤 Cliente registrado: {name} ({sid})")

    # Avisar a los admins
    socketio.emit("new_client", {"id": sid, "name": name}, to=list(admins.keys()))
    broadcast_clients()

# ==============================
# Registro de administrador
# ==============================
@socketio.on("register_admin")
def handle_register_admin(data):
    name = data.get("name", "Administrador")
    sid = request.sid
    admins[sid] = {"name": name}
    print(f"🛡️ Admin conectado: {name} ({sid})")
    broadcast_clients()

# ==============================
# Cliente envía mensaje
# ==============================
@socketio.on("message")
def handle_message(data):
    sid = request.sid
    if sid not in clients:
        return

    text = data.get("text", "")
    timestamp = data.get("timestamp", current_time())
    sender_name = clients[sid]["name"]

    msg = {
        "client_id": sid,
        "sender": sender_name,
        "text": text,
        "timestamp": timestamp,
        "from_menu": False
    }

    print(f"💬 Mensaje de {sender_name}: {text}")

    # Enviar al cliente (su propio chat)
    emit("message", {"sender": sender_name, "text": text, "timestamp": timestamp}, room=sid)

    # Enviar a los administradores
    socketio.emit("client_message", msg, to=list(admins.keys()))

# ==============================
# Admin envía mensaje
# ==============================
@socketio.on("admin_message")
def handle_admin_message(data):
    target = data.get("to")
    text = data.get("text", "")
    timestamp = data.get("timestamp", current_time())

    if not target or target not in clients:
        print(f"⚠️ Admin intentó enviar mensaje a cliente no válido ({target})")
        return

    msg = {
        "sender": "Administrador",
        "text": text,
        "timestamp": timestamp
    }

    print(f"📤 Admin → {clients[target]['name']}: {text}")

    # Enviar al cliente
    emit("message", msg, room=target)

# ==============================
# Menús interactivos del cliente
# ==============================
@socketio.on("menu_option_selected")
def handle_menu_option_selected(data):
    sid = request.sid
    option_id = data.get("id")

    menus = {
        "menu_ambar": ["Información General", "Instalaciones", "Misión y Visión"],
        "menu_asp": ["Requisitos", "Proceso de Inscripción"],
        "menu_ofe": ["Carreras", "Certificaciones", "Talleres"],
        "menu_est": ["Calendario Escolar", "Biblioteca", "Actividades"],
        "menu_map": []
    }

    submenu = menus.get(option_id, [])

    # Si es el mapa, mostrar imagen
    if option_id == "menu_map":
        emit("show_map", {"image": "/images/mapa.png"})
        # Avisar a admin
        socketio.emit("client_message", {
            "client_id": sid,
            "sender": clients[sid]["name"],
            "text": "Mapa",
            "timestamp": current_time(),
            "from_menu": True
        }, to=list(admins.keys()))
        return

    if submenu:
        emit("show_submenu", {"submenu": [{"label": s, "id": s.lower()} for s in submenu]})
    else:
        emit("show_info", {"label": "Menú", "text": "Sin información disponible."})

    # Avisar al admin
    socketio.emit("client_message", {
        "client_id": sid,
        "sender": clients[sid]["name"],
        "text": option_id,
        "timestamp": current_time(),
        "from_menu": True
    }, to=list(admins.keys()))

# ==============================
# Submenús seleccionados
# ==============================
@socketio.on("submenu_option_selected")
def handle_submenu_option_selected(data):
    sid = request.sid
    option_id = data.get("id", "")
    label = option_id.replace("_", " ").title()

    emit("show_info", {
        "label": label,
        "text": f"Información sobre {label}."
    })

    socketio.emit("client_message", {
        "client_id": sid,
        "sender": clients[sid]["name"],
        "text": label,
        "timestamp": current_time(),
        "from_menu": True
    }, to=list(admins.keys()))

# ==============================
# Retorno al menú principal
# ==============================
@socketio.on("return_to_main_menu")
def handle_return_to_main_menu():
    sid = request.sid
    emit("show_menu")
    socketio.emit("client_message", {
        "client_id": sid,
        "sender": clients[sid]["name"],
        "text": "Regresó al menú principal",
        "timestamp": current_time(),
        "from_menu": True
    }, to=list(admins.keys()))

# ==============================
# Ejecución del servidor
# ==============================
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
