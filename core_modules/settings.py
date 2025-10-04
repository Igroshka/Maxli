from core.config import ALIASES, config, save_config
from core.loader import COMMANDS, MODULE_COMMANDS

async def addalias_command(api, message, args):
    if len(args) != 2: await api.edit(message, f"⚠️ Ошибка: Используй: {config['prefix']}addalias [алиас] [команда]"); return
    alias, command_name = args[0].lower(), args[1].lower()
    if command_name not in COMMANDS and command_name not in MODULE_COMMANDS: await api.edit(message, f"❌ Ошибка: Команда {command_name} не существует."); return
    ALIASES[alias] = command_name; config['aliases'] = ALIASES; save_config(config)
    await api.edit(message, f"✅ Успешно! Алиас {config['prefix']}{alias} теперь указывает на {config['prefix']}{command_name}.")

async def remalias_command(api, message, args):
    if not args: await api.edit(message, "⚠️ Ошибка: Укажи алиас для удаления."); return
    alias_to_remove = args[0].lower()
    if alias_to_remove not in ALIASES: await api.edit(message, f"❌ Ошибка: Алиас {alias_to_remove} не найден."); return
    del ALIASES[alias_to_remove]; config['aliases'] = ALIASES; save_config(config)
    await api.edit(message, f"✅ Успешно! Алиас {config['prefix']}{alias_to_remove} удален.")

async def setprefix_command(api, message, args):
    new_prefix = args[0] if args else ""
    config['prefix'] = new_prefix
    save_config(config)
    # ВАЖНО: нужно импортировать и изменить глобальную переменную в основном модуле
    from core import config as core_config
    core_config.PREFIX = new_prefix
    response_text = f"✅ Успешно! Новый префикс: {new_prefix}" if new_prefix else "✅ Успешно! Префикс убран."
    await api.edit(message, response_text)

async def register(commands):
    commands["addalias"] = addalias_command
    commands["remalias"] = remalias_command
    commands["setprefix"] = setprefix_command