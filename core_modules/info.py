import platform
import psutil

from core.loader import LOADED_MODULES, COMMANDS
from core.config import PREFIX

async def info_command(api, message, args):
    python_version = platform.python_version()
    try: cpu_display = f"{psutil.cpu_percent()}%"
    except: cpu_display = "Недоступно"
    try: ram_display = f"{psutil.virtual_memory().percent}%"
    except: ram_display = "Недоступно"
    # Безопасное получение имени владельца
    owner_name = "Неизвестно"
    if api.me and api.me.names:
        owner_name = api.me.names[0].name
    
    info_text = (
        f"🤖 {api.BOT_NAME}\n\n"
        f"🔩 Версия: {api.BOT_VERSION} (#{api.BOT_VERSION_CODE})\n"
        f"👤 Владелец: {owner_name}\n\n"
        f"🖥 Информация о хосте:\n"
        f"    🐍 Python: {python_version}\n"
        f"    🧠 CPU: {cpu_display}\n"
        f"    💾 RAM: {ram_display}\n\n"
        f"📝 Префикс: {PREFIX if PREFIX else 'Нет'}"
    )
    await api.edit(message, info_text)

async def help_command(api, message, args):
    if not args:
        response = "📖 Справка по командам\n\n"
        response += "⚙️ Системные команды:\n"
        response += f"{', '.join(COMMANDS.keys())}\n\n"
        if LOADED_MODULES:
            response += "🧩 Модули:\n"
            for i, (name, data) in enumerate(LOADED_MODULES.items(), 1):
                response += f"{i}. {data['header'].get('name', name)}\n"
        response += f"\nИнфо о модуле: {PREFIX}help [имя/название/номер]"
    else:
        arg = ' '.join(args)
        found_module = None
        for i, (name, data) in enumerate(LOADED_MODULES.items(), 1):
            if arg == str(i) or arg.lower() == name.lower() or arg.lower() == data['header'].get('name', '').lower():
                found_module = data; break
        if not found_module:
            response = f"❌ Модуль '{arg}' не найден."
        else:
            response = f"📖 Справка по модулю \"{found_module['header'].get('name')}\"\n"
            ver = found_module['header'].get('version', 'N/A'); dev = found_module['header'].get('developer', 'N/A')
            response += f"Версия: {ver} | Автор: {dev}\n\n"
            for cmd, desc in found_module['commands'].items():
                response += f"▫️ {PREFIX}{cmd} - {desc}\n"
    await api.edit(message, response)

async def register(commands):
    commands["info"] = info_command
    commands["help"] = help_command
