from pathlib import Path

from core.loader import load_module, unload_module, LOADED_MODULES
from core.api import MODULES_DIR
from core_modules.modules import fuzzy_find_module

async def load_command(api, message, args):
    await api.edit(message, "❌ Ошибка: эта команда работает только с файлами.\n\nОтправь .py файл и в подписи к нему напиши .load")

async def unload_command(api, message, args):
    if not args: await api.edit(message, "⚠️ Укажи имя модуля."); return
    response = await unload_module(args[0])
    await api.edit(message, f"Вывод:\n{response}")

async def modules_command(api, message, args):
    if not LOADED_MODULES: await api.edit(message, "📦 Нет загруженных модулей."); return
    response = "📦 Загруженные модули:\n\n"
    for name, data in LOADED_MODULES.items():
        ver = data['header'].get('version', 'N/A'); dev = data['header'].get('developer', 'N/A')
        response += f"• {data['header'].get('name', name)} (v{ver}) от {dev}\n"
    await api.edit(message, response)

async def sendmodule_command(api, message, args):
    if not args: await api.edit(message, "⚠️ Укажи имя модуля."); return
    
    # Используем нечеткий поиск для поиска модуля
    module, error = fuzzy_find_module(args[0])
    if not module:
        await api.edit(message, f"❌ {error}")
        return
    
    module_path = module['file_path']
    display_name = module['display_name']
    
    try:
        # Используем chat_id из сообщения
        chat_id = getattr(message, 'chat_id', None)
        if not chat_id:
            await api.edit(message, "❌ Не удалось определить chat_id")
            return
        
        # Отправляем файл модуля
        await api.edit(message, f"⏳ Отправляю файл модуля {display_name}...")
        result = await api.send_file(chat_id, str(module_path), f"Модуль {display_name}", notify=False)
        
        if result:
            await api.delete(message, for_me=False)
        else:
            await api.edit(message, f"❌ Ошибка отправки файла модуля {display_name}")
            
    except Exception as e:
        await api.edit(message, f"❌ Ошибка отправки файла: {e}")

async def register(commands):
    commands["load"] = load_command
    commands["unload"] = unload_command
    commands["modules"] = modules_command
    commands["sendmodule"] = sendmodule_command