from gevent import monkey
monkey.patch_all()

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
from menu_config import menu_config
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode='gevent', manage_session=False)

# Estructuras en memoria
chats = {}                # { user_sid: [message, ...] }
clientes_conectados = {}  # { user_sid: {"name": ...} }

def current_timestamp():
    """Devuelve timestamp consistente para mensajes."""
    return datetime.now().strftime("%d/%m/%Y, %H:%M:%S")

# -------------------------
# Rutas
# -------------------------
@app.route('/')
def client_page():
    return render_template('index.html')

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

# -------------------------
# Conexiones
# -------------------------
@socketio.on('connect')
def handle_connect():
    # Le decimos al cliente su sid (user_id)
    emit('connected', {'user_id': request.sid})

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    # Remover cliente conectado (si existe)
    clientes_conectados.pop(sid, None)
    # NOTA: si quieres conservar historial tras desconexión, no hagas pop de chats aquí.
    chats.pop(sid, None)

    # Actualizar lista de clientes en los administradores
    emit('update_chat_list', [
        {'user_id': uid, 'name': info['name']}
        for uid, info in clientes_conectados.items()
    ], broadcast=True)

# -------------------------
# Unirse / historial
# -------------------------
@socketio.on('join')
def handle_join():
    sid = request.sid
    join_room(sid)
    if sid not in chats:
        chats[sid] = []
    emit('chat_history', chats[sid], room=sid)

# -------------------------
# Registro de nombre
# -------------------------
@socketio.on('register_name')
def handle_register_name(data):
    name = data.get('name', 'Invitado')
    sid = request.sid
    clientes_conectados[sid] = {'name': name}

    ts = data.get("timestamp") or current_timestamp()

    bienvenida = {
        'text': f'Hola {name}, bienvenido a Build a chat. Para empezar, escriba "Menu" para abrir el menú interactivo 🚀',
        'timestamp': ts,
        'sender': 'Tecbot'
    }

    audio_bienvenida = {
        'audio_url': '/static/audio/bienvenida.mp3',
        'timestamp': ts,
        'sender': 'Tecbot'
    }

    chats.setdefault(sid, []).extend([bienvenida, audio_bienvenida])

    # Emitir al propio cliente
    emit('message', bienvenida, room=sid)
    emit('message', audio_bienvenida, room=sid)

    # Notificar a los paneles admin (broadcast para que lo reciban todos los admin windows)
    emit('message_admin', {'user_id': sid, 'message': bienvenida}, broadcast=True)
    emit('message_admin', {'user_id': sid, 'message': audio_bienvenida}, broadcast=True)

    # Actualizar listado de clientes en admin
    emit('update_chat_list', [
        {'user_id': uid, 'name': info['name']}
        for uid, info in clientes_conectados.items()
    ], broadcast=True)

# -------------------------
# Mensaje desde cliente
# -------------------------
@socketio.on('message')
def handle_message(data):
    sid = request.sid
    name = clientes_conectados.get(sid, {}).get('name', 'Invitado')
    text = data.get('text', '').strip()
    lower_text = text.lower()

    # Garantizar timestamp — si el cliente no lo envía, el servidor genera uno
    ts = data.get("timestamp") or current_timestamp()

    msg = {
        'text': text,
        'timestamp': ts,
        'sender': name
    }

    # Guardar en historial (clave: sid)
    chats.setdefault(sid, []).append(msg)

    # Enviar el mensaje al propio cliente (para que lo vea)
    emit('message', msg, room=sid)

    # Enviar notificación al admin (con el message embebido)
    # Broadcast para que todos los paneles admin escuchen
    emit('message_admin', {
        'user_id': sid,
        'message': msg
    }, broadcast=True)

    # Si el cliente escribió "menu", mostrar el menú
    if lower_text == "menu":
        emit('show_menu', room=sid)

# -------------------------
# Manejo de opciones del menú (raíz)
# -------------------------
@socketio.on('menu_option_selected')
def handle_menu_option(data):
    sid = request.sid
    option_id = data.get('id')
    option = menu_config.get(option_id)

    if not option:
        return

    if option["type"] == "link":
        emit('show_link', {
            'label': option["label"],
            'link': option["link"]
        }, room=sid)

    elif option["type"] == "submenu":
        emit('show_submenu', {
            'submenu': [
                {"id": item["id"], "label": item["label"]}
                for item in option.get("submenu", [])
            ]
        }, room=sid)

    elif option["type"] == "info":
        emit('show_info', {
            'label': option["label"],
            'text': option["text"]
        }, room=sid)

    elif option["type"] == "image":
        emit('show_map', {
            'image': option["image"],
            'label': option.get("label", "Imagen")
        }, room=sid)

# -------------------------
# Manejo de opciones en submenus (búsqueda recursiva)
# -------------------------
@socketio.on('submenu_option_selected')
def handle_submenu_option(data):
    sid = request.sid
    option_id = data.get('id')

    def find_option_by_id(menu, target_id):
        if isinstance(menu, dict):
            if menu.get("id") == target_id:
                return menu
            if "submenu" in menu:
                for item in menu["submenu"]:
                    result = find_option_by_id(item, target_id)
                    if result:
                        return result
            for key in menu:
                result = find_option_by_id(menu[key], target_id)
                if result:
                    return result
        elif isinstance(menu, list):
            for item in menu:
                result = find_option_by_id(item, target_id)
                if result:
                    return result
        return None

    option = find_option_by_id(menu_config, option_id)

    if not option:
        return

    if option["type"] == "link":
        emit('show_link', {
            'label': option["label"],
            'link': option["link"]
        }, room=sid)

    elif option["type"] == "info":
        emit('show_info', {
            'label': option["label"],
            'text': option["text"]
        }, room=sid)

    elif option["type"] == "submenu":
        emit('show_submenu', {
            'submenu': [
                {"id": item["id"], "label": item["label"]}
                for item in option.get("submenu", [])
            ]
        }, room=sid)

# -------------------------
# Admin selecciona chat (ver historial)
# -------------------------
@socketio.on('admin_select_chat')
def admin_select_chat(data):
    user_id = data['user_id']
    # El admin se une a la room del user_id (opcional, útil si quieres emitir al admin por room)
    join_room(user_id)
    emit('chat_history', chats.get(user_id, []), room=request.sid)

# -------------------------
# Admin envía mensaje al cliente
# -------------------------
@socketio.on('admin_message')
def handle_admin_message(data):
    user_id = data.get('user_id')
    if not user_id:
        return

    ts = data.get("timestamp") or current_timestamp()

    msg = {
        'text': data.get('text', ''),
        'timestamp': ts,
        'sender': 'Admin'
    }

    chats.setdefault(user_id, []).append(msg)

    # Enviar al cliente destino
    emit('message', msg, room=user_id)

    # Notificar a los paneles admin (broadcast para que lo vean todos los admin windows)
    emit('message_admin', {
        'user_id': user_id,
        'message': msg
    }, broadcast=True)

# -------------------------
# Volver al menú principal
# -------------------------
@socketio.on('return_to_main_menu')
def handle_return_to_main_menu():
    user_id = request.sid
    emit('show_menu', room=user_id)

# -------------------------
# Ejecutar servidor
# -------------------------
if __name__ == '__main__':
    socketio.run(app, debug=True)
