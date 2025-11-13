from gevent import monkey
monkey.patch_all()

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
from menu_config import menu_config
from datetime import datetime, timezone

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode='gevent', manage_session=False)

# ==========================
#       VARIABLES GLOBALES
# ==========================
chats = {}  # Historial por cliente (clave: user_id)
clientes_conectados = {}  # Lista de clientes activos


# ==========================
#       FUNCIONES UTILES
# ==========================
def current_timestamp():
    """Devuelve timestamp ISO 8601 en UTC."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def actualizar_lista_admin():
    """Envía al admin la lista actualizada de clientes conectados."""
    emit('update_chat_list', [
        {'user_id': uid, 'name': info['name']}
        for uid, info in clientes_conectados.items()
    ], broadcast=True)


# ==========================
#       RUTAS HTML
# ==========================
@app.route('/')
def client_page():
    return render_template('index.html')


@app.route('/admin')
def admin_page():
    return render_template('admin.html')


# ==========================
#       SOCKET EVENTS
# ==========================
@socketio.on('connect')
def handle_connect():
    """Confirma conexión y entrega el ID del cliente."""
    emit('connected', {'user_id': request.sid})


@socketio.on('disconnect')
def handle_disconnect():
    """Elimina cliente desconectado y actualiza lista del admin."""
    user_id = request.sid
    clientes_conectados.pop(user_id, None)
    chats.pop(user_id, None)
    actualizar_lista_admin()


@socketio.on('join')
def handle_join():
    """El cliente entra a su sala privada (por user_id)."""
    user_id = request.sid
    join_room(user_id)
    if user_id not in chats:
        chats[user_id] = []
    emit('chat_history', chats[user_id], room=user_id)


@socketio.on('register_name')
def handle_register_name(data):
    """Registra el nombre del cliente y envía bienvenida + audio."""
    user_id = request.sid
    name = data.get('name', 'Invitado')
    clientes_conectados[user_id] = {'name': name}

    bienvenida_texto = {
        'text': (
            f'Hola {name}, bienvenido a Build a Chat. '
            'Para empezar, escriba o presione "menu" para abrir el menú interactivo 🚀'
        ),
        'timestamp': current_timestamp(),
        'sender': 'Tecbot'
    }

    bienvenida_audio = {
        'audio_url': '/static/audio/bienvenida.mp3',
        'text': '',
        'timestamp': current_timestamp(),
        'sender': 'Tecbot'
    }

    # Guardar en historial
    chats.setdefault(user_id, []).extend([bienvenida_texto, bienvenida_audio])

    # Enviar al cliente
    emit('message', bienvenida_texto, room=user_id)
    emit('message', bienvenida_audio, room=user_id)

    # Enviar ambos al panel admin (una sola emisión por mensaje)
    for mensaje in [bienvenida_texto, bienvenida_audio]:
        emit('message_admin', {'user_id': user_id, 'message': mensaje}, broadcast=True)

    # Actualizar lista de clientes
    actualizar_lista_admin()


@socketio.on('message')
def handle_message(data):
    """Recibe mensaje del cliente y responde según sea necesario."""
    user_id = request.sid
    name = clientes_conectados.get(user_id, {}).get('name', 'Invitado')
    text = data.get("text", "").strip()
    timestamp = data.get("timestamp") or current_timestamp()

    if not text:
        return  # Evita mensajes vacíos

    msg = {'text': text, 'timestamp': timestamp, 'sender': name}
    chats.setdefault(user_id, []).append(msg)

    # Mostrar mensaje en cliente y admin
    emit('message', msg, room=user_id)
    emit('message_admin', {'user_id': user_id, 'message': msg}, broadcast=True)

    # Si el usuario escribe "menu"
    if text.lower() == "menu":
        emit('show_menu', room=user_id)


@socketio.on('menu_option_selected')
def handle_menu_option(data):
    """Procesa una opción del menú principal."""
    user_id = request.sid
    option_id = data.get('id')
    option = menu_config.get(option_id)

    if not option:
        return

    tipo = option["type"]

    if tipo == "link":
        emit('show_link', {'label': option["label"], 'link': option["link"]}, room=user_id)

    elif tipo == "submenu":
        submenu = [{"id": item["id"], "label": item["label"]} for item in option["submenu"]]
        emit('show_submenu', {'submenu': submenu}, room=user_id)

    elif tipo == "info":
        emit('show_info', {'label': option["label"], 'text': option["text"]}, room=user_id)

    elif tipo == "image":
        emit('show_map', {'image': option["image"], 'label': option.get("label", "Imagen")}, room=user_id)


@socketio.on('submenu_option_selected')
def handle_submenu_option(data):
    """Maneja selección de opciones dentro de submenús."""
    user_id = request.sid
    option_id = data.get('id')

    def find_option(menu, target):
        """Busca recursivamente una opción dentro del menú."""
        if isinstance(menu, dict):
            if menu.get("id") == target:
                return menu
            for v in menu.values():
                found = find_option(v, target)
                if found:
                    return found
        elif isinstance(menu, list):
            for item in menu:
                found = find_option(item, target)
                if found:
                    return found
        return None

    option = find_option(menu_config, option_id)
    if not option:
        return

    tipo = option["type"]

    if tipo == "link":
        emit('show_link', {'label': option["label"], 'link': option["link"]}, room=user_id)

    elif tipo == "info":
        emit('show_info', {'label': option["label"], 'text': option["text"]}, room=user_id)

    elif tipo == "submenu":
        submenu = [{"id": item["id"], "label": item["label"]} for item in option["submenu"]]
        emit('show_submenu', {'submenu': submenu}, room=user_id)


@socketio.on('admin_select_chat')
def admin_select_chat(data):
    """Permite al admin ver el historial de un cliente."""
    user_id = data['user_id']
    join_room(user_id)
    emit('chat_history', chats.get(user_id, []), room=request.sid)


@socketio.on('admin_message')
def handle_admin_message(data):
    """Permite al admin enviar mensaje al cliente."""
    user_id = data['user_id']
    timestamp = data.get("timestamp") or current_timestamp()

    msg = {'text': data['text'], 'timestamp': timestamp, 'sender': 'Admin'}
    chats.setdefault(user_id, []).append(msg)

    emit('message', msg, room=user_id)
    emit('message_admin', {'user_id': user_id, 'message': msg}, broadcast=True)


@socketio.on('return_to_main_menu')
def handle_return_to_main_menu():
    """Regresa al menú principal."""
    emit('show_menu', room=request.sid)

# Bloque de Testeo para arreglar el menú 
@socketio.on("show_menu_request")
def handle_show_menu_request():
   # Envia al cliente el evento para desplegar el menú principal
    emit("show_menu", {
        "menu": [
            {"id": "menu_ambar", "label": "Ambar"},
            {"id": "menu_asp", "label": "Aspirantes"},
            {"id": "menu_ofe", "label": "Oferta Educativa"},
            {"id": "menu_est", "label": "Estudiantes"},
            {"id": "menu_mapa", "label": "Mapa de instlaaciones"},
        ]
    })

# ==========================
#       RUN SERVER
# ==========================
if __name__ == '__main__':
    socketio.run(app, debug=True)
