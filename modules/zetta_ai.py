# name: Zetta - AI models
# version: 13.0 (Maxli Port v2)
# developer: @hikkagpt (ported by YouRooni & AI)
# min-maxli: 0.2.5
# dependencies: aiohttp, requests, SpeechRecognition, pydub

import json
import logging
import aiohttp
import re
import base64
import io
import random
from pathlib import Path

try:
    import speech_recognition as sr
    from pydub import AudioSegment
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

# --- ПЕРЕМЕННЫЕ МОДУЛЯ ---
DB_FILE = "zetta_db.json"
db = {}
available_models = { "13": "gpt-4o", "14": "gpt-4o-mini", "16": "gpt-3.5-turbo" }

# --- УПРАВЛЕНИЕ БД МОДУЛЯ ---
def load_db(): global db; db = json.load(open(DB_FILE, 'r')) if Path(DB_FILE).exists() else {}
def save_db(): open(DB_FILE, 'w').write(json.dumps(db, indent=4))
def db_get(key, default=None): return db.get(key, default)
def db_set(key, value): db[key] = value; save_db()

# --- ОСНОВНЫЕ ФУНКЦИИ ---
async def send_request_to_api(api_url, payload):
    try:
        async with aiohttp.ClientSession() as session, session.post(api_url, json=payload, timeout=120) as response:
            data = await response.json(); answer = data.get("answer", "🚫 Ответ не получен.").strip()
            return base64.b64decode(answer).decode('utf-8')
    except Exception as e: return f"🚫 Ошибка API: {e}"

# --- КОМАНДЫ ---
async def ai_command(api, message, args):
    """Отправляет одиночный запрос к ИИ. Использование: .ai <запрос>"""
    if not args: return await api.edit(message, "🤔 Введите запрос.")
    await api.edit(message, "🤔 Думаю...")
    api_url = "http://195.62.49.61:5001/OnlySq-Zetta/v1/models"
    payload = {"model": db_get("default_model", "gpt-4o-mini"), "request": {"messages": [{"role": "user", "content": " ".join(args)}]}}
    answer = await send_request_to_api(api_url, payload)
    await api.edit(message, f"💡 Ответ:\n{answer}")

async def chat_command(api, message, args):
    """Включает/выключает режим чата. Использование: .chat on/off"""
    chat_id = api.get_target_chat_id()
    if not chat_id: return await api.edit(message, "❌ Не удалось определить чат.")
    active_chats = db_get("active_chats", {})
    if args and args[0].lower() == 'off':
        if str(chat_id) in active_chats:
            del active_chats[str(chat_id)]; db_set("active_chats", active_chats)
            await api.edit(message, "📴 Режим чата выключен.")
    else:
        active_chats[str(chat_id)] = True; db_set("active_chats", active_chats)
        await api.edit(message, "💬 Режим чата включен.")

async def model_command(api, message, args):
    """Устанавливает модель ИИ. .model <номер> или .model list"""
    if not args: return await api.edit(message, f"Текущая модель: {db_get('default_model', 'gpt-4o-mini')}")
    if args[0].lower() == 'list':
        model_list = "\n".join([f"{k}. {v}" for k, v in available_models.items()])
        return await api.edit(message, f"📝 Доступные модели:\n{model_list}")
    if args[0] in available_models:
        model_name = available_models[args[0]]; db_set("default_model", model_name)
        await api.edit(message, f"✅ Модель изменена на: {model_name}")
    else: await api.edit(message, "🚫 Неверный номер модели.")

# --- ВОТЧЕР ---
async def watcher(api, message):
    """Следит за сообщениями в активных чатах."""
    active_chats = db_get("active_chats", {})
    if not message.text or not api.last_known_chat_id or str(api.last_known_chat_id) not in active_chats:
        return
    if message.sender == api.me.id: return # Игнорируем свои сообщения в вотчере
    
    chat_history = db_get("chat_history", {})
    chat_id_str = str(api.last_known_chat_id)
    if chat_id_str not in chat_history: chat_history[chat_id_str] = []
    
    chat_history[chat_id_str].append({"role": "user", "content": message.text})
    if len(chat_history[chat_id_str]) > 10: chat_history[chat_id_str] = chat_history[chat_id_str][-10:]
    
    api_url = "http://195.62.49.61:5001/OnlySq-Zetta/v1/models"
    payload = {"model": db_get("default_model", "gpt-4o-mini"), "request": {"messages": chat_history[chat_id_str]}}
    answer = await send_request_to_api(api_url, payload)
    
    if answer:
        chat_history[chat_id_str].append({"role": "assistant", "content": answer})
        db_set("chat_history", chat_history)
        await api.reply(message, answer, notify=True)

# --- РЕГИСТРАЦИЯ ---
async def register(bot_api):
    load_db()
    bot_api.register_command("ai", ai_command)
    bot_api.register_command("chat", chat_command)
    bot_api.register_command("model", model_command)
    bot_api.register_watcher(watcher)