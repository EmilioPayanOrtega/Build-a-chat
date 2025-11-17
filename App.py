from gevent import monkey
monkey.patch_all()

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
from menu_config import menu_config
from datetime import datetime, timezone
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
# async_mode='gevent' es OK pero dejar que SocketIO seleccione si es necesario.
socketio = SocketIO(app, async_mode='gevent', manage_session=False)

# ==========================
#       DATOS EN MEMORIA
# ==========================
chats = {}  # { user_id: [ messageObj, ... ] }
clientes_conectados = {}  # { user_id: { "name": str } }


# ==========================
#       UTILITIES
# ==========================
def current_timestamp():
    """ISO 8601 UTC sin microsegundos (ej: 2025-11-10T19:00:00+00:00)"""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def make_message(text=None, sender=None, audio_url=None, extra=None):
    """Crea un objeto de mensaje consistente con message_id para dedupe."""
    msg = {
        "message_id": uuid.uuid4().hex,
        "text": text or "",
        "timestamp": current_timestamp(),
        "sender": sender or "",
    }
    if audio_url:
        msg["audio_url"] = audio_url
    if extra:
        msg.update(extra)
    return msg


def actualizar_lista_admin():
    """Emitir la lista de clientes (id + name) a todos (admin escuchará)."""
    emit('update_chat_list', [
        {'user_id': uid, 'name': info['name']}
        for uid, info in clientes_conectados.items()
    ], broadcast=True)


def top_level_menu_payload():
    """Construye payload del menú principal (solo id/label/type) para el cliente."""
    top = []
    for key, item in menu_config.items():
        top.append({
            "id": item.get("id", key),
            "label": item.get("label", key),
            "type": item.get("type", "info")
        })
    return top


# ==========================
#       RUTAS
# ==========================
@app.route('/') # Página de login
def login_page():
    return render_template('login.html')

@app.route('/cliente') # Página de panel cliente
def client_page():
    return render_template('index.html')


@app.route('/admin') # Página de panel admin
def admin_page():
    return render_template('admin.html')

# ==========================
#       SOCKET EVENTS
# ==========================
@socketio.on('connect')
def handle_connect():
    """Se conecta un socket (aún no se registra nombre)."""
    emit('connected', {'user_id': request.sid})


@socketio.on('disconnect')
def handle_disconnect():
    """Limpia estructuras y actualiza admin."""
    user_id = request.sid
    clientes_conectados.pop(user_id, None)
    chats.pop(user_id, None)
    actualizar_lista_admin()


@socketio.on('join')
def handle_join():
    """Cliente pide unirse a su sala privada y pide historial."""
    user_id = request.sid
    join_room(user_id)
    if user_id not in chats:
        chats[user_id] = []
    # enviamos historial al socket que pidió join
    emit('chat_history', chats[user_id], room=user_id)


@socketio.on('admin_join')
def handle_admin_join():
    """Cuando el panel admin se conecta, le enviamos la lista actual."""
    actualizar_lista_admin()


@socketio.on('register_name')
def handle_register_name(data):
    """El cliente registra su nombre (o 'Invitado'). Se envía bienvenida + audio."""
    user_id = request.sid
    name = data.get('name', 'Invitado')
    clientes_conectados[user_id] = {'name': name}

    # Mensaje de bienvenida (texto)
    bienvenida_texto = make_message(
        text=f'Hola {name}, bienvenido a Build a Chat. Para empezar, escriba o presione "menu" para abrir el menú interactivo 🚀',
        sender='Tecbot'
    )
    # Mensaje con audio (se envía al cliente para que pueda reproducirlo con botón)
    bienvenida_audio = make_message(
        text='',  # dejar vacío: el cliente mostrará botón ▶
        sender='Tecbot',
        audio_url='/static/audio/bienvenida.mp3'
    )

    # Guardar en historial (texto + audio)
    chats.setdefault(user_id, []).extend([bienvenida_texto, bienvenida_audio])

    # Enviar ambos al cliente (su sala)
    emit('message', bienvenida_texto, room=user_id)
    emit('message', bienvenida_audio, room=user_id)

    # Notificar al admin que hay un cliente nuevo (no enviamos el audio completo al admin)
    emit('message_admin', {
        'user_id': user_id,
        'message': {
            'message_id': bienvenida_texto['message_id'],
            'text': f'{name} se ha conectado.',
            'timestamp': bienvenida_texto['timestamp'],
            'sender': 'Sistema'
        }
    }, broadcast=True)

    # Actualizar lista de clientes
    actualizar_lista_admin()


@socketio.on('message')
def handle_message(data):
    """
    Cliente envía mensaje de texto.
    - Guardamos con message_id
    - Emitimos 'message' a la sala del usuario (para que su cliente reciba el objeto canonical)
    - Emitimos 'message_admin' al admin con el mensaje y user_id
    """
    user_id = request.sid
    name = clientes_conectados.get(user_id, {}).get('name', 'Invitado')
    text = (data.get('text') or '').strip()
    timestamp = data.get('timestamp') or current_timestamp()

    if not text:
        return

    # crear mensaje canónico (incluye id)
    msg = {
        "message_id": data.get("message_id") or uuid.uuid4().hex,
        "text": text,
        "timestamp": timestamp,
        "sender": name
    }

    # guardar en historial
    chats.setdefault(user_id, []).append(msg)

    # emitir al propio cliente (su sala) y notificar al admin
    emit('message', msg, room=user_id)
    emit('message_admin', {'user_id': user_id, 'message': msg}, broadcast=True)

    # si escribió "menu" pedimos mostrar menú (con payload)
    if text.lower() == "menu":
        emit('show_menu', {'menu': top_level_menu_payload()}, room=user_id)
        # notificar admin que el cliente abrió el menú (sin contenido del menú)
        emit('message_admin', {
            'user_id': user_id,
            'message': {
                'message_id': uuid.uuid4().hex,
                'text': f'El cliente "{name}" abrió el menú.',
                'timestamp': current_timestamp(),
                'sender': 'Sistema'
            }
        }, broadcast=True)


@socketio.on('menu_option_selected')
def handle_menu_option(data):
    """
    Cliente eligió una opción principal (menu_config key).
    - Enviamos al cliente el contenido correspondiente.
    - Notificamos al admin con un texto simple que diga qué opción escogió el cliente.
    """
    user_id = request.sid
    option_id = data.get('id')
    option = menu_config.get(option_id)

    if not option:
        # Notificar al cliente que no existe la opción
        emit('show_info', {'label': 'Error', 'text': 'Opción no encontrada.'}, room=user_id)
        return

    tipo = option.get('type')

    if tipo == "link":
        emit('show_link', {'label': option.get('label'), 'link': option.get('link')}, room=user_id)
    elif tipo == "submenu":
        submenu = [{"id": item["id"], "label": item["label"], "type": item.get("type", "info")} for item in option.get("submenu", [])]
        emit('show_submenu', {'submenu': submenu, 'parent_label': option.get('label')}, room=user_id)
    elif tipo == "info":
        emit('show_info', {'label': option.get('label'), 'text': option.get('text')}, room=user_id)
    elif tipo == "image":
        emit('show_map', {'image': option.get('image'), 'label': option.get('label')}, room=user_id)

    # Notificar al admin (solo texto resumen, no detalles del menú)
    client_name = clientes_conectados.get(user_id, {}).get('name', 'Invitado')
    emit('message_admin', {
        'user_id': user_id,
        'message': {
            'message_id': uuid.uuid4().hex,
            'text': f'El cliente "{client_name}" seleccionó: {option.get("label")}',
            'timestamp': current_timestamp(),
            'sender': 'Sistema'
        }
    }, broadcast=True)


@socketio.on('submenu_option_selected')
def handle_submenu_option(data):
    """
    Cliente eligió opción dentro de un submenu.
    Buscamos recursivamente en menu_config y actuamos igual que menu_option_selected.
    """
    user_id = request.sid
    option_id = data.get('id')

    def find_option(menu, target_id):
        if isinstance(menu, dict):
            if menu.get("id") == target_id:
                return menu
            for v in menu.values():
                found = find_option(v, target_id)
                if found:
                    return found
        elif isinstance(menu, list):
            for item in menu:
                found = find_option(item, target_id)
                if found:
                    return found
        return None

    option = find_option(menu_config, option_id)
    if not option:
        emit('show_info', {'label': 'Error', 'text': 'Opción no encontrada.'}, room=user_id)
        return

    tipo = option.get('type')

    if tipo == "link":
        emit('show_link', {'label': option.get('label'), 'link': option.get('link')}, room=user_id)
    elif tipo == "info":
        emit('show_info', {'label': option.get('label'), 'text': option.get('text')}, room=user_id)
    elif tipo == "submenu":
        submenu = [{"id": item["id"], "label": item["label"], "type": item.get("type", "info")} for item in option.get("submenu", [])]
        emit('show_submenu', {'submenu': submenu, 'parent_label': option.get('label')}, room=user_id)

    # Notificar admin de la selección (resumen)
    client_name = clientes_conectados.get(user_id, {}).get('name', 'Invitado')
    emit('message_admin', {
        'user_id': user_id,
        'message': {
            'message_id': uuid.uuid4().hex,
            'text': f'El cliente "{client_name}" seleccionó: {option.get("label")}',
            'timestamp': current_timestamp(),
            'sender': 'Sistema'
        }
    }, broadcast=True)


@socketio.on('admin_select_chat')
def admin_select_chat(data):
    """Admin solicita historial de un cliente: devolvemos chats[user_id]."""
    user_id = data.get('user_id')
    # Nota: no necesitamos join_room(admin, user_id) para enviar chat_history; solo emit al admin socket
    emit('chat_history', chats.get(user_id, []), room=request.sid)


@socketio.on('admin_message')
def handle_admin_message(data):
    """Admin envía mensaje dirigido a user_id."""
    user_id = data.get('user_id')
    if not user_id:
        return
    text = data.get('text', '').strip()
    if not text:
        return

    msg = {
        "message_id": data.get("message_id") or uuid.uuid4().hex,
        "text": text,
        "timestamp": data.get("timestamp") or current_timestamp(),
        "sender": "Admin"
    }

    chats.setdefault(user_id, []).append(msg)

    # Enviar al cliente
    emit('message', msg, room=user_id)
    # Notificar al resto de admins/paneles con message_admin (igual que antes)
    emit('message_admin', {'user_id': user_id, 'message': msg}, broadcast=True)


@socketio.on('return_to_main_menu')
def handle_return_to_main_menu():
    """Forzar despliegue del menú principal en el cliente que lo solicitó."""
    user_id = request.sid
    emit('show_menu', {'menu': top_level_menu_payload()}, room=user_id)


# ==========================
#       RUN SERVER
# ==========================
if __name__ == '__main__':
    socketio.run(app, debug=True)
