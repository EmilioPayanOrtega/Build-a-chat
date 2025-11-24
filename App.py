from gevent import monkey
monkey.patch_all()

import os
import io
import base64
import re
import requests
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
from menu_config import menu_config
from datetime import datetime, timezone
import uuid

# PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET', 'secret!')
socketio = SocketIO(app, async_mode='gevent', manage_session=False)

# Config / secrets from env
GEMMA_API_KEY = os.environ.get('GEMMA_API_KEY', 'AIzaSyCFRQXMamJUTF-bXes2blXa_BwpI2MpZq0')
GEMMA_MODEL = os.environ.get('GEMMA_MODEL', 'gemini-1.5-flash')  # ajustar si necesario
SENTIMENT_API_URL = os.environ.get('SENTIMENT_API_URL', 'https://doctoradoitc.pythonanywhere.com/sentimiento/')
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', 're_3Y1HJYBb_JEsHBYs1shLbonKz2NAn4dgS')
RESEND_FROM = os.environ.get('RESEND_FROM', 'onboarding@resend.dev')
RESEND_API_URL = os.environ.get('RESEND_API_URL', 'https://api.resend.com/emails')

# In-memory data
chats = {}  # { user_id: [ messageObj, ... ] }
clientes_conectados = {}  # { user_id: { "name": str } }

# Utilities
EMAIL_REGEX = re.compile(r"^[^@]+@[^@]+\.[^@]+$")

def current_timestamp():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def make_message(text=None, sender=None, audio_url=None, extra=None):
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
    emit('update_chat_list', [
        {'user_id': uid, 'name': info['name']}
        for uid, info in clientes_conectados.items()
    ], broadcast=True)

def top_level_menu_payload():
    top = []
    for key, item in menu_config.items():
        top.append({
            "id": item.get("id", key),
            "label": item.get("label", key),
            "type": item.get("type", "info")
        })
    return top

# -----------------------
#    Rutas web
# -----------------------
@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/cliente')
def client_page():
    return render_template('index.html')

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

# -----------------------
#    Socket handlers
# -----------------------
@socketio.on('connect')
def handle_connect():
    emit('connected', {'user_id': request.sid})

@socketio.on('disconnect')
def handle_disconnect():
    user_id = request.sid
    clientes_conectados.pop(user_id, None)
    chats.pop(user_id, None)
    actualizar_lista_admin()

@socketio.on('join')
def handle_join():
    user_id = request.sid
    join_room(user_id)
    if user_id not in chats:
        chats[user_id] = []
    emit('chat_history', chats[user_id], room=user_id)

@socketio.on('admin_join')
def handle_admin_join():
    actualizar_lista_admin()

@socketio.on('register_name')
def handle_register_name(data):
    user_id = request.sid
    name = data.get('name', 'Invitado')
    clientes_conectados[user_id] = {'name': name}

    bienvenida_texto = make_message(
        text=f'Hola {name}, bienvenido a Build a Chat. Para empezar, escriba o presione "menu" para abrir el menú interactivo 🚀',
        sender='Tecbot'
    )
    bienvenida_audio = make_message(
        text='',
        sender='Tecbot',
        audio_url='/static/audio/bienvenida.mp3'
    )

    chats.setdefault(user_id, []).extend([bienvenida_texto, bienvenida_audio])
    emit('message', bienvenida_texto, room=user_id)
    emit('message', bienvenida_audio, room=user_id)

    emit('message_admin', {
        'user_id': user_id,
        'message': {
            'message_id': bienvenida_texto['message_id'],
            'text': f'{name} se ha conectado.',
            'timestamp': bienvenida_texto['timestamp'],
            'sender': 'Sistema'
        }
    }, broadcast=True)

    actualizar_lista_admin()

@socketio.on('message')
def handle_message(data):
    user_id = request.sid
    name = clientes_conectados.get(user_id, {}).get('name', 'Invitado')
    text = (data.get('text') or '').strip()
    timestamp = data.get('timestamp') or current_timestamp()
    if not text:
        return

    msg = {
        "message_id": data.get("message_id") or uuid.uuid4().hex,
        "text": text,
        "timestamp": timestamp,
        "sender": name
    }

    chats.setdefault(user_id, []).append(msg)
    emit('message', msg, room=user_id)
    emit('message_admin', {'user_id': user_id, 'message': msg}, broadcast=True)

    if text.lower() == "menu":
        emit('show_menu', {'menu': top_level_menu_payload()}, room=user_id)
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
    user_id = request.sid
    option_id = data.get('id')
    option = menu_config.get(option_id)
    if not option:
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
    user_id = data.get('user_id')
    emit('chat_history', chats.get(user_id, []), room=request.sid)

@socketio.on('admin_message')
def handle_admin_message(data):
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
    emit('message', msg, room=user_id)
    emit('message_admin', {'user_id': user_id, 'message': msg}, broadcast=True)

@socketio.on('return_to_main_menu')
def handle_return_to_main_menu():
    user_id = request.sid
    emit('show_menu', {'menu': top_level_menu_payload()}, room=user_id)

# -----------------------
#  SUMMARY: generar y enviar PDF por correo
#  socket event: 'request_summary_email' payload: {'email': 'dest@dominio.com'}
# -----------------------

def call_gemma_generate_text(prompt_text):
    """
    Llamada simple a la API generativa de Google (Gemma / Gemini).
    Ajusta endpoint/modelo según tus credenciales/SDK.
    """
    if not GEMMA_API_KEY:
        raise RuntimeError("GEMMA_API_KEY no configurada en env")

    # Usamos el endpoint REST de Generative Language API (v1beta2)
    url = f"https://generativelanguage.googleapis.com/v1beta2/models/{GEMMA_MODEL}:generateText"
    headers = {
        "Authorization": f"Bearer {GEMMA_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "prompt": {
            "text": prompt_text
        },
        "temperature": 0.2,
        "maxOutputTokens": 500
    }

    resp = requests.post(url, json=body, headers=headers, timeout=30)
    resp.raise_for_status()
    j = resp.json()

    # Intentamos extraer el texto de varias estructuras posibles
    if isinstance(j, dict):
        # "candidates" estructura
        if 'candidates' in j and len(j['candidates']) > 0:
            candidate = j['candidates'][0]
            # candidate puede tener 'output' o 'content' / 'text'
            if isinstance(candidate, dict):
                if 'output' in candidate and isinstance(candidate['output'], str):
                    return candidate['output']
                if 'content' in candidate:
                    c = candidate['content']
                    # buscar texto en content
                    if isinstance(c, list):
                        for part in c:
                            if isinstance(part, dict) and 'text' in part:
                                return part['text']
        # fallback a 'output' -> list -> content -> text
        out = j.get('output') or j.get('outputs')
        if out and isinstance(out, list):
            for part in out:
                if isinstance(part, dict):
                    content = part.get('content')
                    if content and isinstance(content, list):
                        for c in content:
                            if isinstance(c, dict) and 'text' in c:
                                return c['text']
        # último recurso
        return str(j)
    return str(j)

def analyze_sentiment(text):
    """Llama a tu API de polaridad (la que diste)."""
    if not SENTIMENT_API_URL:
        return None
    try:
        r = requests.post(SENTIMENT_API_URL, json={"texto": text}, timeout=15)
        r.raise_for_status()
        return r.json()  # asume JSON con la respuesta de sentimiento
    except Exception as e:
        return {"error": str(e)}

def create_pdf_bytes(title, summary_text, sentiment_result, chat_history):
    """Genera un PDF en memoria y devuelve bytes."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    w, h = letter
    margin = 40
    y = h - margin

    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, y, title)
    y -= 24

    c.setFont("Helvetica", 10)
    c.drawString(margin, y, f"Fecha: {datetime.now().astimezone().isoformat()}")
    y -= 18

    # Sentiment
    if sentiment_result:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin, y, "Análisis de polaridad:")
        y -= 16
        c.setFont("Helvetica", 10)
        c.drawString(margin, y, str(sentiment_result))
        y -= 20

    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Resumen breve:")
    y -= 14
    c.setFont("Helvetica", 10)

    # wrap summary lines
    for line in summary_text.splitlines():
        if not line:
            continue
        # dividir en trozos de ~90 chars para evitar overflow
        while len(line) > 90:
            c.drawString(margin, y, line[:90])
            line = line[90:]
            y -= 12
            if y < margin + 60:
                c.showPage()
                y = h - margin
                c.setFont("Helvetica", 10)
        c.drawString(margin, y, line)
        y -= 12
        if y < margin + 60:
            c.showPage()
            y = h - margin
            c.setFont("Helvetica", 10)

    y -= 6
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Conversación (últimos mensajes):")
    y -= 14
    c.setFont("Helvetica", 9)

    # Chat history
    for m in (chat_history or [])[-100:]:  # limitar
        text = f"{m.get('timestamp','')[:19]} {m.get('sender','')}: {m.get('text','')}"
        # simple wrapping per 90 chars
        while len(text) > 90:
            c.drawString(margin, y, text[:90])
            text = text[90:]
            y -= 12
            if y < margin + 40:
                c.showPage()
                y = h - margin
                c.setFont("Helvetica", 9)
        c.drawString(margin, y, text)
        y -= 12
        if y < margin + 40:
            c.showPage()
            y = h - margin
            c.setFont("Helvetica", 9)

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()

def send_email_with_resend(to_email, subject, html_body, pdf_bytes, filename="summary.pdf"):
    """Envía correo con Resend. Adjunta el PDF en base64 en attachments."""
    if not RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY no configurada")

    encoded = base64.b64encode(pdf_bytes).decode('utf-8')
    payload = {
        "from": RESEND_FROM,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
        "attachments": [
            {
                "content": encoded,
                "filename": filename,
                "type": "application/pdf"
            }
        ]
    }
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    r = requests.post(RESEND_API_URL, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

@socketio.on('request_summary_email')
def handle_request_summary_email(data):
    """
    Espera: { 'email': 'dest@example.com' }
    Flujo:
      - valida email
      - obtiene historial del user (chats[request.sid])
      - crea prompt, llama Gemma para generar resumen
      - llama API de sentimiento (opcional)
      - genera PDF
      - envía PDF por Resend
      - emite resultado al cliente con 'summary_status'
    """
    user_id = request.sid
    email = (data or {}).get('email', '').strip()
    if not email or not EMAIL_REGEX.match(email):
        emit('summary_status', {'ok': False, 'error': 'Email inválido.'}, room=user_id)
        return

    # obtener historial
    history = chats.get(user_id, [])
    # formar texto para resumen
    text_for_summary = "\n".join([f"{m.get('sender','')}: {m.get('text','')}" for m in history[-200:]])
    if not text_for_summary:
        emit('summary_status', {'ok': False, 'error': 'No hay historial para resumir.'}, room=user_id)
        return

    prompt = (
        "Resume brevemente la siguiente conversación en español (máximo 6-8 líneas). "
        "Incluye puntos importantes y recomendaciones si aplica.\n\n"
        f"{text_for_summary}"
    )

    emit('summary_status', {'ok': None, 'message': 'Generando resumen...'}, room=user_id)

    try:
        # 1) Generar resumen con Gemma
        summary_text = call_gemma_generate_text(prompt)

        # 2) Analizar polaridad (sobre el resumen)
        sentiment = analyze_sentiment(summary_text)

        # 3) Generar PDF bytes
        title = f"Resumen de chat - {clientes_conectados.get(user_id, {}).get('name','Invitado')}"
        pdf_bytes = create_pdf_bytes(title, summary_text, sentiment, history)

        # 4) Enviar por Resend
        subject = f"Resumen de tu chat con Tecbot"
        html_body = f"<p>Adjunto encontrarás el resumen de tu conversación.</p><p>Resumen breve:<br>{summary_text}</p>"
        send_resp = send_email_with_resend(email, subject, html_body, pdf_bytes)

        # éxito
        emit('summary_status', {'ok': True, 'message': 'Resumen enviado por correo.'}, room=user_id)
    except Exception as e:
        print("Error al generar/enviar summary:", e)
        emit('summary_status', {'ok': False, 'error': str(e)}, room=user_id)

# -----------------------
#  Run
# -----------------------
if __name__ == '__main__':
    socketio.run(app, debug=True)
