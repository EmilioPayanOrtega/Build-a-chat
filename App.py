from gevent import monkey
monkey.patch_all()

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
from menu_config import menu_config


app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode='gevent', manage_session=False)

chats = {}
clientes_conectados = {}

@app.route('/')
def client_page():
    return render_template('index.html')

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

@socketio.on('connect')
def handle_connect():
    emit('connected', {'user_id': request.sid})

@socketio.on('disconnect')
def handle_disconnect():
    user_id = request.sid
    clientes_conectados.pop(user_id, None)
    chats.pop(user_id, None)
    emit('update_chat_list', [
        {'user_id': uid, 'name': info['name']}
        for uid, info in clientes_conectados.items()
    ], broadcast=True)

@socketio.on('join')
def handle_join():
    user_id = request.sid
    join_room(user_id)
    if user_id not in chats:
        chats[user_id] = []
    emit('chat_history', chats[user_id], room=user_id)

@socketio.on('register_name')
def handle_register_name(data):
    name = data.get('name', 'Invitado')
    user_id = request.sid
    clientes_conectados[user_id] = {'name': name}

    bienvenida = {
        'text': f'Hola {name}, bienvenido a Build a chat. Para empezar, escriba "Menu" para abrir el menú interactivo 🚀',
        'timestamp': data.get("timestamp"),
        'sender': 'Tecbot'
    }

    audio_bienvenida = {
        'audio_url': '/static/audio/bienvenida.mp3',
        'timestamp': data.get("timestamp"),
        'sender': 'Tecbot'
    }

    chats.setdefault(user_id, []).extend([bienvenida, audio_bienvenida])
    emit('message', bienvenida, room=user_id)
    emit('message', audio_bienvenida, room=user_id)
    emit('message_admin', {'user_id': user_id, 'message': bienvenida}, broadcast=True)
    emit('message_admin', {'user_id': user_id, 'message': audio_bienvenida}, broadcast=True)

    emit('update_chat_list', [
        {'user_id': uid, 'name': info['name']}
        for uid, info in clientes_conectados.items()
    ], broadcast=True)

@socketio.on('message')
def handle_message(data):
    user_id = request.sid
    name = clientes_conectados.get(user_id, {}).get('name', 'Invitado')
    text = data['text'].strip().lower()

    msg = {
        'text': data['text'],
        'timestamp': data.get("timestamp"),
        'sender': name
    }
    chats.setdefault(user_id, []).append(msg)

    emit('message', msg, room=user_id)
    emit('message_admin', {'user_id': user_id, 'message': msg}, broadcast=True)

    if text == "menu":
        emit('show_menu', room=user_id)

@socketio.on('menu_option_selected')
def handle_menu_option(data):
    user_id = request.sid
    option_id = data.get('id')
    option = menu_config.get(option_id)

    if not option:
        return

    if option["type"] == "link":
        emit('show_link', {
            'label': option["label"],
            'link': option["link"]
        }, room=user_id)

    elif option["type"] == "submenu":
        emit('show_submenu', {
            'submenu': [
                {"id": item["id"], "label": item["label"]}
                for item in option["submenu"]
            ]
        }, room=user_id)

    elif option["type"] == "info":
        emit('show_info', {
            'label': option["label"],
            'text': option["text"]
        }, room=user_id)

    elif option["type"] == "image":
        emit('show_map', {
            'image': option["image"],
            'label': option.get("label", "Imagen")
        }, room=user_id)

@socketio.on('submenu_option_selected')
def handle_submenu_option(data):
    user_id = request.sid
    option_id = data.get('id')

    def find_option_by_id(menu, target_id):
        if isinstance(menu, dict):
            # Caso 1: este nodo tiene el id buscado
            if menu.get("id") == target_id:
                return menu
            # Caso 2: si tiene un submenu, recorrerlo
            if "submenu" in menu:
                for item in menu["submenu"]:
                    result = find_option_by_id(item, target_id)
                    if result:
                        return result
            # Caso 3: recorrer todos los valores del diccionario si está en la raíz
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
        }, room=user_id)

    elif option["type"] == "info":
        emit('show_info', {
            'label': option["label"],
            'text': option["text"]
        }, room=user_id)

    elif option["type"] == "submenu":
        emit('show_submenu', {
            'submenu': [
                {"id": item["id"], "label": item["label"]}
                for item in option["submenu"]
            ]
        }, room=user_id)

@socketio.on('admin_select_chat')
def admin_select_chat(data):
    user_id = data['user_id']
    join_room(user_id)
    emit('chat_history', chats.get(user_id, []), room=request.sid)

@socketio.on('admin_message')
def handle_admin_message(data):
    user_id = data['user_id']
    msg = {
        'text': data['text'],
        'timestamp': data.get("timestamp"),
        'sender': 'Admin'
    }
    chats.setdefault(user_id, []).append(msg)
    emit('message', msg, room=user_id)
    emit('message_admin', {'user_id': user_id, 'message': msg}, room=request.sid)

@socketio.on('return_to_main_menu')
def handle_return_to_main_menu():
    user_id = request.sid
    emit('show_menu', room=user_id)

if __name__ == '__main__':
    socketio.run(app, debug=True)
