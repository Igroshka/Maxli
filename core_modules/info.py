import platform
import psutil
from core.loader import LOADED_MODULES, COMMANDS
from core.config import PREFIX, config, get_banner_url, save_config
import aiohttp
import tempfile
import os
from pymax.files import Photo

class InfoModule:

    async def configset_command(self, api, message, args):
        """Установить значение переменной в модуле: configset [1|2] [модуль] [переменная] [значение]"""
        if len(args) < 4:
            await api.edit(message, "⚠️ Использование: configset [1|2] [модуль] [переменная] [значение]")
            return
        mod_type = args[0]
        mod_id = args[1]
        var_name = args[2]
        value = ' '.join(args[3:])

        # Определяем модуль по типу и имени/номеру
        module_name = None
        if mod_type == '1':
            # Глобальные модули (core_modules)
            modules_list = list(LOADED_MODULES.items())
            if mod_id.isdigit():
                idx = int(mod_id) - 1
                if 0 <= idx < len(modules_list):
                    module_name = modules_list[idx][0]
            else:
                for name, data in modules_list:
                    if mod_id.lower() == name.lower() or mod_id.lower() == data['header'].get('name', '').lower():
                        module_name = name
                        break
            if not module_name:
                await api.edit(message, f"❌ Глобальный модуль '{mod_id}' не найден.")
                return
            # Если секции для модуля нет — создаём
            if module_name not in config:
                config[module_name] = {}
            # Баннер — это просто переменная banner
            if var_name.lower() == 'banner':
                config[module_name]['banner'] = value
                save_config(config)
                await api.edit(message, f"✅ Баннер для '{module_name}' обновлён!")
                return
            # Любая другая переменная
            config[module_name][var_name] = value
            save_config(config)
            await api.edit(message, f"✅ Значение {var_name} для '{module_name}' обновлено!")
            return
        elif mod_type == '2':
            # Внешние модули (external_modules)
            ext_mods = config.get('external_modules', {})
            modules_list = list(ext_mods.items())
            if mod_id.isdigit():
                idx = int(mod_id) - 1
                if 0 <= idx < len(modules_list):
                    module_name = modules_list[idx][0]
            else:
                for name, data in modules_list:
                    if mod_id.lower() == name.lower():
                        module_name = name
                        break
            if not module_name:
                await api.edit(message, f"❌ Внешний модуль '{mod_id}' не найден.")
                return
            # Сохраняем в settings
            if 'settings' not in config['external_modules'][module_name]:
                config['external_modules'][module_name]['settings'] = {}
            config['external_modules'][module_name]['settings'][var_name] = value
            save_config(config)
            await api.edit(message, f"✅ Значение {var_name} для внешнего модуля '{module_name}' обновлено!")
            return
        else:
            await api.edit(message, "❌ Первый аргумент должен быть 1 (глобальный) или 2 (внешний) модуль.")
            return
    # Кеш для баннера info: url -> (путь к файлу, file_id/attach)
    _banner_cache = {
        'url': None,
        'file_path': None,
        'photo_token': None
    }
    """Модуль информации о боте и системе (по образцу HerokuInfoMod)"""
    def __init__(self):
        # Конфиг для info-модуля (можно расширять)
        self.config = config.get('info', {
            'custom_message': None,
            'banner_url': get_banner_url('info') or '',
        })
        # Сохраняем в config, если не было
        config['info'] = self.config
        save_config(config)

    async def info_command(self, api, message, args):
        snippet = getattr(message, 'text', '')
        api.LOG_BUFFER.append(f"[info] {snippet[:80]}")
        # Удаляем исходное сообщение сразу
        try:
            await api.delete(message)
        except Exception as e:
            api.LOG_BUFFER.append(f"[info] Не удалось удалить сообщение: {e}")
        python_version = platform.python_version()
        try:
            cpu_display = f"{psutil.cpu_percent()}%"
        except Exception:
            cpu_display = "Недоступно"
        try:
            ram_display = f"{psutil.virtual_memory().percent}%"
        except Exception:
            ram_display = "Недоступно"
        owner_name = "Неизвестно"
        if api.me and api.me.names:
            owner_name = api.me.names[0].name

        # Формируем текст инфо с markdown форматированием
        info_text = self.config.get('custom_message') or (
            f"🤖 **{api.BOT_NAME}** *{api.BOT_VERSION} (#{api.BOT_VERSION_CODE})*\n\n"
            f"👤 **Владелец:** {owner_name}\n\n"
            f"🖥 **Информация о хосте:**\n"
            f"    🐍 **Python:** {python_version}\n"
            f"    🧠 **CPU:** {cpu_display}\n"
            f"    💾 **RAM:** {ram_display}\n\n"
            f"📝 **Префикс:** '{PREFIX if PREFIX else '.'}'"
        )
        banner = self.config.get('banner_url')
        if banner:
            # Гарантируем прямые слэши для URL
            banner_url = banner.replace('\\', '/')
            
            # --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
            chat_id = getattr(message, 'chat_id', None)
            if not chat_id:
                chat_id = await api.await_chat_id(message)

            if chat_id:
                # Проверяем кеш: если url совпадает и файл существует, используем кеш
                file_path = self._banner_cache.get('file_path')
                need_download = (
                    self._banner_cache.get('url') != banner_url or
                    not file_path or not os.path.exists(file_path)
                )
                if need_download:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(banner_url) as resp:
                            if resp.status != 200:
                                # Если скачать не удалось, отправляем просто текст
                                await api.send(chat_id, info_text, markdown=True, notify=True) 
                                return
                            suffix = os.path.splitext(banner_url)[-1] or '.jpg'
                            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                                file_path = tmp.name
                                content = await resp.read()
                                tmp.write(content)
                    self._banner_cache['url'] = banner_url
                    self._banner_cache['file_path'] = file_path
                # Отправляем фото через объект Photo (кешированный файл)
                photo = Photo(path=file_path)
                photo_data = photo.validate_photo()
                if not photo_data:
                    # Если фото невалидно, отправляем просто текст
                    await api.send(chat_id, info_text, markdown=True, notify=True)
                    return
                await api.send_photo(
                    chat_id=chat_id,
                    text=info_text,
                    photo=photo,
                    markdown=True,
                    notify=True
                )
                return
        
        # Если баннера нет или не удалось отправить, отправляем как обычное сообщение
        chat_id = getattr(message, 'chat_id', None)
        if not chat_id:
            chat_id = await api.await_chat_id(message)
        await api.send(chat_id, info_text, markdown=True, notify=True)


    async def setinfo_command(self, api, message, args):
        """Установить кастомный info-текст через config info setinfo <текст>"""
        if not args:
            await api.edit(message, "⚠️ Укажи текст для info.")
            return
        self.config['custom_message'] = ' '.join(args)
        config['info'] = self.config
        save_config(config)
        await api.edit(message, "✅ Кастомный info-текст установлен!")

    async def setbanner_command(self, api, message, args):
        """Установить кастомный info-баннер через config info setbanner <url>"""
        if not args:
            await api.edit(message, "⚠️ Укажи URL баннера.")
            return
        # Гарантируем прямые слэши для URL
        self.config['banner_url'] = args[0].replace('\\', '/').replace('\\', '/')
        config['info'] = self.config
        save_config(config)
        await api.edit(message, "✅ Баннер для info обновлен!")


# Регистрация команд через функцию register (ожидается loader'ом)
info_module = InfoModule()

async def register(commands):
    commands['info'] = info_module.info_command
    commands['setinfo'] = info_module.setinfo_command
    commands['setbanner'] = info_module.setbanner_command
    commands['help'] = help_command
    commands['configset'] = info_module.configset_command

async def help_command(api, message, args):
    snippet = getattr(message, 'text', '')
    api.LOG_BUFFER.append(f"[help] {snippet[:80]}")
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
    
    banner = get_banner_url("help")
    if banner:
        # --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
        chat_id = getattr(message, 'chat_id', None)
        if not chat_id:
            chat_id = await api.await_chat_id(message)

        if chat_id:
            try:
                await api.delete(message)
            except Exception:
                pass
            await api.send_photo(chat_id, banner, response)
            return

    await api.edit(message, response)