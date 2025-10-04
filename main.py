# Файл: main.py

import asyncio
import json
import websockets
from pymax import MaxClient, Message

from core.config import config, PREFIX, ALIASES, PHONE
from core.loader import load_all_modules, COMMANDS, MODULE_COMMANDS
from core.api import API, log_critical_error

# --- ИНИЦИАЛИЗАЦИЯ ---
if not PHONE:
    print("!!! Номер телефона не найден в 'maxli_config.json'. Завершение работы.")
    exit()
    
client = MaxClient(phone=PHONE, work_dir="pymax_session")
api = API(client, config)

# --- СТАНДАРТНЫЙ ОБРАБОТЧИК СООБЩЕНИЙ ---
@client.on_message()
async def message_handler(message: Message):
    # chat_id уже добавлен в сообщение модифицированной библиотекой PyMax
    if not hasattr(message, 'chat_id') or not message.chat_id:
        print(f"⚠️ Сообщение {message.id} не имеет chat_id, пропускаем")
        return
    
    print(f"✅ Обрабатываем сообщение {message.id} в чате {message.chat_id}")
    
    # Обновляем last_known_chat_id для ответов на "Прр"
    api.update_last_known_chat_id(message)

    # --- Обработка загрузки модуля из файла теперь в самой команде load ---

    # --- Обработка "Прр" (только от других) ---
    if not api.me or message.sender != api.me.id:
        if message.text and message.text.lower() == "прр":
            if api.last_known_chat_id:
                await client.send_message(chat_id=api.last_known_chat_id, text="Ку", notify=True)
        return # Завершаем, если сообщение не от нас

    # --- ЕСЛИ МЫ ЗДЕСЬ, ЗНАЧИТ СООБЩЕНИЕ ОТ НАС И ЭТО КОМАНДА ---
    if not message.text or (PREFIX and not message.text.startswith(PREFIX)):
        return

    command_body = message.text[len(PREFIX):]; parts = command_body.split()
    command_name = parts[0].lower(); args = parts[1:]
    resolved_command = ALIASES.get(command_name, command_name)
    handler_info = COMMANDS.get(resolved_command) or MODULE_COMMANDS.get(resolved_command)

    if handler_info:
        handler = handler_info if callable(handler_info) else handler_info['function']
        # Просто вызываем команду. API само разберется с chat_id и ошибками.
        try:
            await handler(api, message, args)
        except Exception as e:
            await log_critical_error(e, message, client)


@client.on_start
async def startup():
    api.set_me(client.me)
    
    # Проверяем информацию о перезапуске
    from core_modules.restart import check_restart_info
    await check_restart_info(api)
    
    await load_all_modules(api)
    
    # Обновляем сообщение о завершении загрузки модулей
    from core_modules.restart import update_restart_complete
    await update_restart_complete(api)
    
    print(f"Юзербот {api.BOT_NAME} v{api.BOT_VERSION} запущен!")
    
    # Проверяем, что client.me не None перед обращением к его атрибутам
    if client.me and client.me.names:
        print(f"Вошел как: {client.me.names[0].name} ({client.phone})")
    else:
        print(f"Вошел как: {client.phone} (профиль не загружен)")
    
    print("🔧 Используется модифицированная библиотека PyMax с извлечением chat_id")

if __name__ == "__main__":
    print("Запускаю юзербота...")
    asyncio.run(client.start())
