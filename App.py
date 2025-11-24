# app.py (versión corregida y más robusta)
from gevent import monkey
monkey.patch_all()

import os
import io
import base64
import re
import requests
import logging
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from menu_config import menu_config
from datetime import datetime, timezone
import uuid

# PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# --- Config basic logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("build-a-chat")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET', 'secret!')

# allow CORS for socket connections (use more strict origins in production if puedes)
socketio = SocketIO(app, async_mode='gevent', manage_session=False, cors_allowed_origins="*")

# Config / secrets from env
GEMMA_API_KEY = os.environ.get('GEMMA_API_KEY')
GEMMA_MODEL = os.environ.get('GEMMA_MODEL', 'gemma2-9b-it')
SENTIMENT_API_URL = os.environ.get('SENTIMENT_API_URL')  
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
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

@app.route('/healthz')
def healthz():
    return jsonify({"ok": True}), 200

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
    chats.setdefault(user_id, [])
    emit('chat_history', chats[user_id], room=user_id)

@socketio.on('admin_join')
def handle_admin_join():
    actualizar_lista_admin()

@socketio.on('register_name')
def handle_register_name(data):
    user_id = request.sid
    name = (data or {}).get('name', 'Invitado')
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
#  compatibilidad: también aceptamos 'request_summary' (legacy)
# -----------------------

def _gemma_call_with_key_or_bearer(url_path, body):
    """
    Helper: si GEMMA_API_KEY parece 'AIza...' usamos ?key=..., si no usamos Authorization Bearer.
    """
    if not GEMMA_API_KEY:
        raise RuntimeError("GEMMA_API_KEY no configurada en env")

    if GEMMA_API_KEY.startswith("AIza"):
        # API key style (public key param)
        url = f"{url_path}?key={GEMMA_API_KEY}"
        headers = {"Content-Type": "application/json"}
    else:
        url = url_path
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GEMMA_API_KEY}"
        }
    return requests.post(url, json=body, headers=headers, timeout=30)

def call_gemma_generate_text(prompt_text):
    """
    Llamada a la API Generative Language. Maneja distintos formatos de respuesta.
    """
    # endpoint base: intentamos generateContent v1 (estructura más común)
    base_url = f"https://generativelanguage.googleapis.com/v1/models/{GEMMA_MODEL}:generateContent"
    body = {
        "contents": [
            {"parts": [{"text": prompt_text}]}
        ]
    }

    resp = _gemma_call_with_key_or_bearer(base_url, body)
    resp.raise_for_status()
    data = resp.json()

    # Extraer texto de varios formatos conocidos
    try:
        # candidatos estilo: data["candidates"][0]["content"]["parts"][0]["text"]
        if isinstance(data, dict):
            if "candidates" in data and isinstance(data["candidates"], list) and len(data["candidates"]) > 0:
                cand = data["candidates"][0]
                if isinstance(cand, dict):
                    # candidate.content.parts
                    cont = cand.get("content")
                    if isinstance(cont, dict):
                        parts = cont.get("parts")
                        if isinstance(parts, list) and parts and isinstance(parts[0], dict) and "text" in parts[0]:
                            return parts[0]["text"]
                    # candidate.output string
                    out_str = cand.get("output")
                    if isinstance(out_str, str):
                        return out_str

            # fallback a output -> content
            out = data.get("output") or data.get("outputs")
            if isinstance(out, list):
                for part in out:
                    if isinstance(part, dict):
                        content = part.get("content")
                        if isinstance(content, list):
                            for c in content:
                                if isinstance(c, dict) and "text" in c:
                                    return c["text"]

        # si no encontramos nada conocido, devolvemos la representación string (útil para debug)
        return str(data)
    except Exception:
        return str(data)

def analyze_sentiment(text):
    """Llama a tu API de polaridad (opcional)."""
    if not SENTIMENT_API_URL:
        return None
    try:
        r = requests.post(SENTIMENT_API_URL, json={"texto": text}, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning("Error al llamar API de sentimiento: %s", e)
        return {"error": str(e)}

def create_pdf_bytes(title, summary_text, sentiment_result, chat_history):
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

    if sentiment_result:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin, y, "Análisis de polaridad:")
        y -= 16
        c.setFont("Helvetica", 10)
        try:
            c.drawString(margin, y, str(sentiment_result))
        except Exception:
            c.drawString(margin, y, repr(sentiment_result))
        y -= 20

    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Resumen breve:")
    y -= 14
    c.setFont("Helvetica", 10)

    for line in (summary_text or "").splitlines():
        if not line:
            continue
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

    for m in (chat_history or [])[-100:]:
        text = f"{m.get('timestamp','')[:19]} {m.get('sender','')}: {m.get('text','')}"
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

def _handle_summary_request(user_id, email):
    """Flujo interno para generar y enviar el resumen (sin socket)."""
    if not EMAIL_REGEX.match(email):
        return {"ok": False, "error": "Email inválido."}

    history = chats.get(user_id, [])
    text_for_summary = "\n".join([f"{m.get('sender','')}: {m.get('text','')}" for m in history[-200:]])
    if not text_for_summary:
        return {"ok": False, "error": "No hay historial para resumir."}

    prompt = (
        "Resume brevemente la siguiente conversación en español (máximo 6-8 líneas). "
        "Incluye puntos importantes y recomendaciones si aplica.\n\n"
        f"{text_for_summary}"
    )

    # 1) Generar resumen
    try:
        summary_text = call_gemma_generate_text(prompt)
    except Exception as e:
        logger.exception("Error al llamar Gemma/Gemini")
        return {"ok": False, "error": f"Error Gemma: {e}"}

    # 2) Analizar polaridad (opcional)
    sentiment = analyze_sentiment(summary_text) if SENTIMENT_API_URL else None

    # 3) Crear PDF
    title = f"Resumen de chat - {clientes_conectados.get(user_id, {}).get('name','Invitado')}"
    pdf_bytes = create_pdf_bytes(title, summary_text, sentiment, history)

    # 4) Enviar por Resend
    try:
        send_resp = send_email_with_resend(email, f"Resumen de tu chat con Tecbot", f"<p>Resumen:<br>{summary_text}</p>", pdf_bytes)
    except Exception as e:
        logger.exception("Error al enviar por Resend")
        return {"ok": False, "error": f"Error al enviar correo: {e}"}

    return {"ok": True, "message": "Resumen enviado por correo."}

@socketio.on('request_summary_email')
def handle_request_summary_email(data):
    user_id = request.sid
    email = (data or {}).get('email', '').strip()
    # send immediate status
    emit('summary_status', {'ok': None, 'message': 'Iniciando generación de resumen...'}, room=user_id)

    result = _handle_summary_request(user_id, email)
    if result.get("ok"):
        emit('summary_status', {'ok': True, 'message': result.get("message")}, room=user_id)
    else:
        emit('summary_status', {'ok': False, 'error': result.get("error")}, room=user_id)

# backward-compatible event name
@socketio.on('request_summary')
def handle_request_summary_legacy(data):
    handle_request_summary_email(data)

# -----------------------
#  Run
# -----------------------
if __name__ == '__main__':
    # Log if env vars missing (do not crash; will error at runtime when used)
    logger.info("GEMMA_API_KEY present: %s", bool(GEMMA_API_KEY))
    logger.info("RESEND_API_KEY present: %s", bool(RESEND_API_KEY))
    logger.info("SENTIMENT_API_URL present: %s", bool(SENTIMENT_API_URL))
    socketio.run(app, debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
