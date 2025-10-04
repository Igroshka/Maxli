# name: Auto Responder
# version: 1.0.0
# developer: YouRooni & AI
# min-maxli: 0.2.5

import json
import re
from pathlib import Path

# --- ПЕРЕМЕННЫЕ МОДУЛЯ ---
DB_FILE = "autoresponder_db.json"
db = {}

# --- УПРАВЛЕНИЕ БД МОДУЛЯ ---
def load_db():
    global db
    if Path(DB_FILE).exists():
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            db = json.load(f)
    else:
        db = {"rules": []}

def save_db():
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=4, ensure_ascii=False)

# --- КОМАНДЫ ---

async def add_rule_command(api, message, args):
    """Добавляет правило. Разделители: |. Cинтаксис: .aradd <триггер> | <ответ> | [scope]"""
    full_args = " ".join(args)
    parts = [p.strip() for p in full_args.split('|')]

    if len(parts) < 2:
        await api.edit(message, "⚠️ Ошибка синтаксиса.\nИспользуй: .aradd <триггер> | <ответ> | [scope]\nScope может быть: pm, group, all (по умолч.)")
        return

    trigger, response = parts[0], parts[1]
    scope = parts[2].lower() if len(parts) > 2 else "all"
    is_regex = False

    if scope not in ["pm", "group", "all"]:
        await api.edit(message, f"❌ Неверный scope: '{scope}'.\nДоступные: pm, group, all.")
        return

    if trigger.lower().startswith("regex:"):
        is_regex = True
        trigger = trigger[6:].strip()
        try:
            re.compile(trigger)
        except re.error as e:
            await api.edit(message, f"❌ Ошибка в регулярном выражении:\n{e}")
            return
    
    rule = {
        "trigger": trigger,
        "response": response,
        "scope": scope,
        "is_regex": is_regex
    }

    db.setdefault("rules", []).append(rule)
    save_db()
    await api.edit(message, f"✅ Правило добавлено!\nТриггер: {trigger}\nОтвет: {response}\nОбласть: {scope}")

async def delete_rule_command(api, message, args):
    """Удаляет правило по номеру из списка или по точному тексту триггера."""
    if not args:
        await api.edit(message, "⚠️ Укажи номер правила из .arlist или его точный триггер.")
        return

    arg = " ".join(args)
    rules = db.get("rules", [])
    
    if not rules:
        await api.edit(message, "Нет правил для удаления."); return

    found = False
    # Попытка удаления по номеру
    try:
        index = int(arg) - 1
        if 0 <= index < len(rules):
            removed = rules.pop(index)
            found = True
    except ValueError:
        # Если не число, ищем по тексту триггера
        for i, rule in enumerate(rules):
            if rule["trigger"] == arg:
                removed = rules.pop(i)
                found = True
                break
    
    if found:
        save_db()
        await api.edit(message, f"✅ Правило с триггером '{removed['trigger']}' удалено.")
    else:
        await api.edit(message, "❌ Правило не найдено.")


async def list_rules_command(api, message, args):
    """Показывает список всех правил автоответчика."""
    rules = db.get("rules", [])
    if not rules:
        await api.edit(message, "📝 Правила автоответчика пусты.\nДобавь новое командой .aradd")
        return

    response = "📝 Список правил автоответчика:\n\n"
    for i, rule in enumerate(rules, 1):
        trigger_type = "regex" if rule["is_regex"] else "text"
        response += f"{i}. [{trigger_type}] {rule['trigger']}\n"
        response += f"   ➔ {rule['response']}\n"
        response += f"   (Scope: {rule['scope']})\n\n"
    
    await api.edit(message, response)

# --- ВОТЧЕР (ОСНОВНАЯ ЛОГИКА) ---

async def responder_watcher(api, message):
    """Проверяет каждое входящее сообщение на соответствие правилам."""
    # Игнорируем свои сообщения и сообщения без текста
    if (api.me and message.sender == api.me.id) or not message.text:
        return

    rules = db.get("rules", [])
    if not rules:
        return

    # Определяем тип текущего чата (pm или group)
    chat_id = api.last_known_chat_id
    if not chat_id: return
    
    current_chat = next((c for c in (api.client.dialogs + api.client.chats) if c.id == chat_id), None)
    if not current_chat: return
    
    # В pymax DIALOG - это личка, CHAT - это группа
    current_scope = "pm" if current_chat.type.name == "DIALOG" else "group"

    for rule in rules:
        # Проверяем, подходит ли правило по области действия
        if rule["scope"] != "all" and rule["scope"] != current_scope:
            continue

        match = False
        if rule["is_regex"]:
            if re.search(rule["trigger"], message.text, re.IGNORECASE):
                match = True
        else:
            if rule["trigger"].lower() in message.text.lower():
                match = True
        
        if match:
            # Нашли совпадение, отвечаем и прекращаем поиск
            await api.reply(message, rule["response"], notify=True)
            return

# --- РЕГИСТРАЦИЯ ---
async def register(bot_api):
    """Регистрирует команды и вотчер модуля."""
    load_db()
    bot_api.register_command("aradd", add_rule_command)
    bot_api.register_command("ardel", delete_rule_command)
    bot_api.register_command("arlist", list_rules_command)
    bot_api.register_watcher(responder_watcher)
