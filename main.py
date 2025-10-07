# Файл: main.py

import asyncio
import json
import websockets
from pymax import MaxClient, Message

from core.config import config, ALIASES, PHONE
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
    from core.api import _append_log
    if not hasattr(message, 'chat_id') or message.chat_id is None:
        _append_log(f"⚠️ Сообщение {message.id} не имеет chat_id, пропускаем")
        return

    _append_log(f"✅ Обрабатываем сообщение {message.id} в чате {message.chat_id}")

    # Логируем команду или сообщение (обрезанный текст и полный текст)
    from core.api import _append_log
    snippet = (getattr(message, 'text', '') or '')[:80]
    full_text = getattr(message, 'text', '') or ''
    _append_log(f"[msg] {snippet}")
    _append_log(f"[msg-full] {full_text}")

    # Обновляем last_known_chat_id для ответов на "Прр"
    api.update_last_known_chat_id(message)

    # Проверяем, что команда от самого бота
    is_own = False
    if hasattr(client, 'me') and client.me and hasattr(message, 'sender'):
        is_own = (message.sender == client.me.id)

    # Обрабатываем команды только если сообщение от нас и начинается с префикса
    current_prefix = config.get('prefix', '.')
    if is_own and message.text and current_prefix and message.text.startswith(current_prefix):
        command_body = message.text[len(current_prefix):]; parts = command_body.split()
        command_name = parts[0].lower(); args = parts[1:]
        resolved_command = ALIASES.get(command_name, command_name)
        handler_info = COMMANDS.get(resolved_command) or MODULE_COMMANDS.get(resolved_command)

        if handler_info:
            handler = handler_info if callable(handler_info) else handler_info['function']
            # Логируем команду и полный текст перед выполнением
            _append_log(f"[command] {command_name} | {full_text}")
            try:
                await handler(api, message, args)
            except Exception as e:
                # Логируем ошибку в LOG_BUFFER
                err_text = f"❌ Ошибка выполнения команды {command_name}: {e} | Сообщение: {full_text}"
                _append_log(err_text)
                await log_critical_error(e, message, client)
                try:
                    await api.edit(message, err_text)
                except Exception:
                    pass
            return  # Выходим после обработки команды

    # Обрабатываем все сообщения через вотчеры модулей
    from core.loader import WATCHERS
    for watcher in WATCHERS:
        try:
            await watcher(api, message)
        except Exception as e:
            _append_log(f"❌ Ошибка в вотчере: {e}")
            print(f"❌ Ошибка в вотчере: {e}")


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
    import logging
    log = logging.getLogger("maxli.LOG_BUFFER")
    if not log.hasHandlers():
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s [LOG_BUFFER] %(message)s")
        handler.setFormatter(formatter)
        log.addHandler(handler)
        log.setLevel(logging.INFO)
    print("Запускаю юзербота...")

    import asyncio
    async def run_with_reconnect():
        while True:
            try:
                await client.start()
            except (asyncio.CancelledError, asyncio.TimeoutError) as e:
                import logging
                logging.getLogger("maxli.LOG_BUFFER").warning(f"[reconnect] [asyncio error] {type(e).__name__}: {e}. Повтор через 2 секунды...")
                await asyncio.sleep(2)
            except Exception as e:
                import logging
                logging.getLogger("maxli.LOG_BUFFER").warning(f"[reconnect] Ошибка запуска клиента: {e}. Повтор через 2 секунды...")
                await asyncio.sleep(2)
            except BaseException as e:
                import logging
                logging.getLogger("maxli.LOG_BUFFER").warning(f"[reconnect] [BaseException] {type(e).__name__}: {e}. Повтор через 2 секунды...")
                await asyncio.sleep(2)
    asyncio.run(run_with_reconnect())
