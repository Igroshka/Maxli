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
    
    # Простейшие команды по алиасам/префиксам остаются

    # Новая единая команда конфигурации
    async def config_command(api, message, args):
        # Без аргументов — показать выбор разделов
        if not args:
            await api.edit(message, "⚙️ Конфиг:\n\n1) system — системные модули\n2) external — внешние модули\n\nИспользование:\nconfig 1 — список системных модулей с переменными\nconfig 2 — список внешних модулей с переменными\nconfig 1 <имя|номер> — показать переменные системного модуля\nconfig 2 <имя|номер> — показать переменные внешнего модуля")
            return
        section = args[0].lower()
        # numeric shortcuts: "1" -> system, "2" -> external
        if section == "1": section = "system"
        if section == "2": section = "external"

        # helper: truncate long values
        def _truncate(val, limit=80):
            s = str(val)
            return s if len(s) <= limit else s[:limit-3] + "..."

        # system modules
        if section == "system":
            # Зарезервированные системные имена
            system_modules = ["info", "management", "ping", "settings", "modules", "restart"]
            # Список только тех системных модулей, у которых есть зарегистрированные переменные
            available = []
            for m in system_modules:
                norm = f"{m}_maxli"
                ext = config.get("external_modules", {}).get(norm, {})
                if ext.get("settings"):
                    available.append((m, ext))

            if len(args) == 1:
                if not available:
                    await api.edit(message, "📭 Нет системных модулей с переменными")
                    return
                lines = ["� Системные модули с переменными:"] + [f"{i+1}) {m}" for i, (m, _) in enumerate(available)]
                await api.edit(message, "\n".join(lines))
                return

            query = args[1]
            chosen = None
            try:
                idx = int(query) - 1
                if 0 <= idx < len(available):
                    chosen, ext = available[idx]
            except Exception:
                chosen = None
            if not chosen:
                for m, e in available:
                    if m == query:
                        chosen, ext = m, e
                        break
            if not chosen:
                await api.edit(message, "❌ Системный модуль не найден или у него нет переменных.")
                return

            settings = ext.get("settings", {})
            descriptions = ext.get("descriptions", {})
            lines = [f"⚙️ Переменные {chosen}:"]
            for k, v in settings.items():
                desc = descriptions.get(k, "")
                lines.append(f"• {k} = {_truncate(v)} {'— ' + desc if desc else ''}")
            await api.edit(message, "\n".join(lines))
            return

        # external modules
        if section == "external":
            ext_all = config.get("external_modules", {})
            # Только внешние модули, у которых есть переменные
            external_keys = [k for k, v in ext_all.items() if not k.endswith("_maxli") and v.get("settings")]
            if len(args) == 1:
                if not external_keys:
                    await api.edit(message, "📭 Нет внешних модулей с переменными")
                    return
                lines = ["🧩 Внешние модули с переменными:"] + [f"{i+1}) {k}" for i, k in enumerate(external_keys)]
                await api.edit(message, "\n".join(lines))
                return

            query = args[1]
            chosen = None
            try:
                idx = int(query) - 1
                if 0 <= idx < len(external_keys):
                    chosen = external_keys[idx]
            except Exception:
                chosen = None
            if not chosen:
                if query in external_keys:
                    chosen = query
                else:
                    await api.edit(message, "❌ Внешний модуль не найден или у него нет переменных.")
                    return
            ext = ext_all.get(chosen, {})
            settings = ext.get("settings", {})
            descriptions = ext.get("descriptions", {})
            lines = [f"⚙️ Переменные {chosen}:"]
            for k, v in settings.items():
                desc = descriptions.get(k, "")
                lines.append(f"• {k} = {_truncate(v)} {'— ' + desc if desc else ''}")
            await api.edit(message, "\n".join(lines))
            return

        await api.edit(message, "Неизвестный раздел. Доступны: 1(system), 2(external)")

    commands["config"] = config_command