# Файл: core_modules/modules.py
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from urllib.parse import urlparse
import re

from core.loader import load_module, MODULES_DIR, LOADED_MODULES
from core.api import BOT_NAME, BOT_VERSION
import difflib

def fuzzy_find_module(query):
    """Нечеткий поиск модуля по названию, ID или нумерации."""
    if not query:
        return None, "Пустой запрос"
    
    # Список доступных модулей
    available_modules = []
    
    # Добавляем загруженные модули
    for name, data in LOADED_MODULES.items():
        display_name = data.get('header', {}).get('name', name)
        available_modules.append({
            'name': name,
            'display_name': display_name,
            'file_path': MODULES_DIR / f"{name}.py",
            'loaded': True
        })
    
    # Добавляем файлы из папки modules
    for file_path in MODULES_DIR.glob("*.py"):
        if file_path.stem != "__init__":
            name = file_path.stem
            if not any(m['name'] == name for m in available_modules):
                available_modules.append({
                    'name': name,
                    'display_name': name,
                    'file_path': file_path,
                    'loaded': False
                })
    
    if not available_modules:
        return None, "Нет доступных модулей"
    
    # Проверяем точное совпадение по имени файла
    for module in available_modules:
        if module['name'].lower() == query.lower():
            return module, None
    
    # Проверяем точное совпадение по отображаемому имени
    for module in available_modules:
        if module['display_name'].lower() == query.lower():
            return module, None
    
    # Проверяем, является ли запрос числом (нумерация)
    try:
        number = int(query)
        if 1 <= number <= len(available_modules):
            return available_modules[number - 1], None
    except ValueError:
        pass
    
    # Нечеткий поиск по названию
    names = [m['name'] for m in available_modules]
    display_names = [m['display_name'] for m in available_modules]
    
    # Ищем в именах файлов
    matches = difflib.get_close_matches(query.lower(), [name.lower() for name in names], n=1, cutoff=0.6)
    if matches:
        for module in available_modules:
            if module['name'].lower() == matches[0]:
                return module, None
    
    # Ищем в отображаемых именах
    matches = difflib.get_close_matches(query.lower(), [name.lower() for name in display_names], n=1, cutoff=0.6)
    if matches:
        for module in available_modules:
            if module['display_name'].lower() == matches[0]:
                return module, None
    
    # Если ничего не найдено, возвращаем самые близкие варианты
    all_names = names + display_names
    close_matches = difflib.get_close_matches(query.lower(), [name.lower() for name in all_names], n=3, cutoff=0.3)
    
    if close_matches:
        suggestions = []
        for match in close_matches:
            for module in available_modules:
                if module['name'].lower() == match or module['display_name'].lower() == match:
                    suggestions.append(f"• {module['display_name']} ({module['name']})")
                    break
        return None, f"Модуль не найден. Возможно, вы имели в виду:\n" + "\n".join(suggestions)
    
    return None, "Модуль не найден"

async def load_command(api, message, args):
    """Улучшенная команда загрузки модулей."""
    # Отладочный вывод JSON сообщения
    print("🔍 DEBUG: JSON сообщения для команды load:")
    print(f"   ID: {message.id}")
    print(f"   Sender: {message.sender}")
    print(f"   Chat ID: {getattr(message, 'chat_id', 'НЕТ')}")
    print(f"   Text: {message.text}")
    print(f"   Reply to: {getattr(message, 'reply_to_message', 'НЕТ')}")
    if hasattr(message, 'reply_to_message') and message.reply_to_message:
        if isinstance(message.reply_to_message, dict):
            print(f"     Reply message ID: {message.reply_to_message.get('id', 'НЕТ')}")
            print(f"     Reply message text: {message.reply_to_message.get('text', 'НЕТ')}")
            print(f"     Reply message attaches: {len(message.reply_to_message.get('attaches', []))}")
            if message.reply_to_message.get('attaches'):
                for i, attach in enumerate(message.reply_to_message['attaches']):
                    print(f"       Вложение {i+1}: {attach.get('name', 'БЕЗ_ИМЕНИ')} - {attach.get('token', 'БЕЗ_TOKEN')}")
        else:
            print(f"     Reply message ID: {getattr(message.reply_to_message, 'id', 'НЕТ')}")
            print(f"     Reply message text: {getattr(message.reply_to_message, 'text', 'НЕТ')}")
            print(f"     Reply message attaches: {len(getattr(message.reply_to_message, 'attaches', []))}")
    print(f"   Attaches: {len(message.attaches) if message.attaches else 0}")
    if message.attaches:
        for i, attach in enumerate(message.attaches):
            print(f"     Вложение {i+1}: {getattr(attach, 'name', 'БЕЗ_ИМЕНИ')} - {getattr(attach, 'url', 'БЕЗ_URL')}")
    
    # Дополнительно выводим полный объект сообщения
    print("🔍 DEBUG: Полный объект сообщения:")
    import json as json_module
    try:
        # Преобразуем объект в словарь для вывода
        msg_dict = {
            'id': message.id,
            'sender': message.sender,
            'text': message.text,
            'chat_id': getattr(message, 'chat_id', None),
            'reply_to_message': getattr(message, 'reply_to_message', None),
            'attaches': [{'name': getattr(attach, 'name', 'БЕЗ_ИМЕНИ'), 'url': getattr(attach, 'url', 'БЕЗ_URL')} for attach in (message.attaches or [])]
        }
        print(json_module.dumps(msg_dict, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"   Ошибка при выводе JSON: {e}")
    
    if not args:
        # Проверяем, является ли это ответом на сообщение с файлом
        if hasattr(message, 'reply_to_message') and message.reply_to_message:
            print("🔍 DEBUG: Обнаружен ответ на сообщение, проверяем вложения...")
            reply_msg = message.reply_to_message
            if isinstance(reply_msg, dict):
                # reply_to_message это словарь
                reply_attaches = reply_msg.get('attaches', [])
                if reply_attaches:
                    print("🔍 DEBUG: В исходном сообщении есть вложения, загружаем...")
                    await load_from_file(api, message)
                    return
                else:
                    print("🔍 DEBUG: В исходном сообщении нет вложений")
            else:
                # reply_to_message это объект
                if hasattr(reply_msg, 'attaches') and reply_msg.attaches:
                    print("🔍 DEBUG: В исходном сообщении есть вложения, загружаем...")
                    await load_from_file(api, message)
                    return
                else:
                    print("🔍 DEBUG: В исходном сообщении нет вложений")
        
        response = "📦 Загрузка модулей\n\n"
        response += "📥 Способы загрузки:\n"
        response += f"• {api.config.get('prefix', '.')}load [ссылка] - загрузить по ссылке\n"
        response += f"• {api.config.get('prefix', '.')}load - ответить на сообщение с файлом .py\n"
        response += f"• {api.config.get('prefix', '.')}load [номер] - загрузить из списка\n\n"
        response += "📋 Доступные модули для загрузки:\n"
        response += "1. Пример модуля (example_module.py)\n"
        response += "2. Автоответчик (autoresponder.py)\n"
        response += "3. Zetta AI (zetta_ai.py)\n"
        await api.edit(message, response)
        return

    arg = args[0]
    
    # Проверяем, является ли аргумент ссылкой
    if is_url(arg):
        await load_from_url(api, message, arg)
    # Проверяем, является ли аргумент номером
    elif arg.isdigit():
        await load_by_number(api, message, int(arg))
    else:
        # Используем нечеткий поиск для поиска модуля
        module, error = fuzzy_find_module(arg)
        if module:
            await load_by_name(api, message, module)
        else:
            await api.edit(message, f"❌ {error}")

def is_url(text):
    """Проверяет, является ли текст URL."""
    try:
        result = urlparse(text)
        return all([result.scheme, result.netloc])
    except:
        return False

async def load_from_url(api, message, url):
    """Загружает модуль по URL."""
    await api.edit(message, "⏳ Загружаю модуль по ссылке...")
    
    try:
        # Получаем имя файла из URL
        parsed_url = urlparse(url)
        filename = Path(parsed_url.path).name
        
        # Если имя файла не .py, добавляем расширение
        if not filename.endswith('.py'):
            filename += '.py'
        
        # Скачиваем файл
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    
                    # Сохраняем файл
                    module_path = MODULES_DIR / filename
                    async with aiofiles.open(module_path, 'wb') as f:
                        await f.write(content)
                    
                    # Загружаем модуль
                    result = await load_module(module_path, api)
                    
                    # Красивое сообщение о результате
                    if "успешно загружен" in result:
                        response = f"✅ Модуль загружен!\n\n"
                        response += f"📁 Файл: {filename}\n"
                        response += f"🔗 Источник: {url}\n"
                        response += f"📊 Статус: {result}"
                    else:
                        response = f"❌ Ошибка загрузки\n\n"
                        response += f"📁 Файл: {filename}\n"
                        response += f"🔗 Источник: {url}\n"
                        response += f"⚠️ Ошибка: {result}"
                    
                    await api.edit(message, response)
                else:
                    await api.edit(message, f"❌ Ошибка скачивания: HTTP {response.status}")
                    
    except Exception as e:
        await api.edit(message, f"❌ Ошибка загрузки модуля: {str(e)}")

async def load_by_number(api, message, number):
    """Загружает модуль по номеру из списка."""
    modules_list = [
        ("example_module.py", "Пример модуля"),
        ("autoresponder.py", "Автоответчик"),
        ("zetta_ai.py", "Zetta AI")
    ]
    
    if 1 <= number <= len(modules_list):
        filename, description = modules_list[number - 1]
        module_path = MODULES_DIR / filename
        
        if module_path.exists():
            await api.edit(message, f"⏳ Загружаю {description}...")
            result = await load_module(module_path, api)
            
            if "успешно загружен" in result:
                response = f"✅ {description} загружен!\n\n"
                response += f"📁 Файл: {filename}\n"
                response += f"📊 Статус: {result}"
            else:
                response = f"❌ Ошибка загрузки {description}\n\n"
                response += f"⚠️ Ошибка: {result}"
            
            await api.edit(message, response)
        else:
            await api.edit(message, f"❌ Файл {filename} не найден в папке modules/")
    else:
        await api.edit(message, f"❌ Неверный номер. Доступны номера 1-{len(modules_list)}")

async def load_by_name(api, message, module):
    """Загружает модуль по найденному объекту модуля."""
    module_name = module['name']
    display_name = module['display_name']
    file_path = module['file_path']
    is_loaded = module['loaded']
    
    if is_loaded:
        await api.edit(message, f"⚠️ Модуль '{display_name}' уже загружен")
        return
    
    if not file_path.exists():
        await api.edit(message, f"❌ Файл {file_path.name} не найден")
        return
    
    await api.edit(message, f"⏳ Загружаю {display_name}...")
    result = await load_module(file_path, api)
    
    if "успешно загружен" in result:
        response = f"✅ {display_name} загружен!\n\n"
        response += f"📁 Файл: {file_path.name}\n"
        response += f"📊 Статус: {result}"
    else:
        response = f"❌ Ошибка загрузки {display_name}\n\n"
        response += f"⚠️ Ошибка: {result}"
    
    await api.edit(message, response)

async def load_from_file(api, message):
    """Загружает модуль из файла в сообщении."""
    file_name = None
    file_url = None
    
    # Проверяем, есть ли вложения в текущем сообщении
    if message.attaches:
        attach = message.attaches[0]
        file_name = getattr(attach, 'name', 'module.py')
        file_url = getattr(attach, 'url', None)
        print(f"🔍 DEBUG: Загружаем из вложений текущего сообщения: {file_name}")
    # Или проверяем, есть ли ответ на сообщение с вложениями
    elif hasattr(message, 'reply_to_message') and message.reply_to_message:
        reply_msg = message.reply_to_message
        if isinstance(reply_msg, dict):
            # reply_to_message это словарь
            reply_attaches = reply_msg.get('attaches', [])
            if reply_attaches:
                attach = reply_attaches[0]
                file_name = attach.get('name', 'module.py')
                # В новом формате используется token вместо url
                file_token = attach.get('token', None)
                file_id = attach.get('fileId', None)
                print(f"🔍 DEBUG: Загружаем из вложений исходного сообщения (dict): {file_name}")
                print(f"   Token: {file_token}")
                print(f"   File ID: {file_id}")
                
                # Для файлов нужно использовать API для получения URL
                if file_token and file_id:
                    await api.edit(message, f"⏳ Получаю URL файла {file_name}...")
                    
                    # Получаем message_id и chat_id из исходного сообщения
                    reply_message_id = reply_msg.get('id')
                    current_chat_id = getattr(message, 'chat_id', None)
                    
                    print(f"🔍 DEBUG: Передаем параметры для получения файла:")
                    print(f"   File ID: {file_id}")
                    print(f"   Token: {file_token}")
                    print(f"   Reply Message ID: {reply_message_id}")
                    print(f"   Current Chat ID: {current_chat_id}")
                    
                    # Получаем URL файла через API с параметрами
                    file_url = await api.get_file_url(file_id, file_token, reply_message_id, current_chat_id)
                    if not file_url:
                        await api.edit(message, f"❌ Не удалось получить URL файла {file_name}")
                        return
                    
                    print(f"✅ Получен URL файла: {file_url}")
                else:
                    await api.edit(message, "❌ Не удалось получить данные файла")
                    return
            else:
                await api.edit(message, "❌ В исходном сообщении нет файлов")
                return
        else:
            # reply_to_message это объект
            if hasattr(reply_msg, 'attaches') and reply_msg.attaches:
                attach = reply_msg.attaches[0]
                file_name = getattr(attach, 'name', 'module.py')
                file_url = getattr(attach, 'url', None)
                print(f"🔍 DEBUG: Загружаем из вложений исходного сообщения (obj): {file_name}")
            else:
                await api.edit(message, "❌ В исходном сообщении нет файлов")
                return
    else:
        await api.edit(message, "❌ В сообщении нет файлов")
        return
    
    if not file_url:
        await api.edit(message, "❌ Не удалось получить URL файла")
        return
    
    if not file_name.endswith('.py'):
        await api.edit(message, "❌ Файл должен иметь расширение .py")
        return
    
    await api.edit(message, f"⏳ Загружаю модуль `{file_name}`...")
    
    try:
        # Скачиваем файл с авторизованными заголовками
        import aiohttp
        
        # Используем те же заголовки, что и в PyMax
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
            'Origin': 'https://web.max.ru',
            'Referer': 'https://web.max.ru/',
        }
        
        print(f"🔍 DEBUG: Скачиваем файл с авторизованными заголовками...")
        print(f"   URL: {file_url}")
        
        # Добавляем таймаут и обработку ошибок сети
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(file_url, headers=headers) as response:
                    print(f"🔍 DEBUG: Ответ сервера: HTTP {response.status}")
                    
                    if response.status == 200:
                        content = await response.read()
                        print(f"✅ Файл скачан, размер: {len(content)} байт")
                        
                        # Проверяем, что файл не пустой
                        if len(content) == 0:
                            error_text = f"❌ Файл пустой\n\n"
                            error_text += f"📁 Файл: {file_name}\n"
                            error_text += f"🌐 URL: {file_url}\n"
                            await api.edit(message, error_text)
                            return
                        
                        # Сохраняем файл
                        module_path = MODULES_DIR / file_name
                        async with aiofiles.open(module_path, 'wb') as f:
                            await f.write(content)
                        
                        print(f"✅ Файл сохранен: {module_path}")
                        
                        # Загружаем модуль
                        result = await load_module(module_path, api)
                        
                        # Красивое сообщение о результате
                        if "успешно загружен" in result:
                            response_text = f"✅ Модуль загружен!\n\n"
                            response_text += f"📁 Файл: {file_name}\n"
                            response_text += f"📊 Статус: {result}"
                        else:
                            response_text = f"❌ Ошибка загрузки\n\n"
                            response_text += f"📁 Файл: {file_name}\n"
                            response_text += f"⚠️ Ошибка: {result}"
                        
                        await api.edit(message, response_text)
                    else:
                        error_text = f"❌ Ошибка скачивания файла\n\n"
                        error_text += f"📁 Файл: {file_name}\n"
                        error_text += f"🌐 URL: {file_url}\n"
                        error_text += f"📊 HTTP статус: {response.status}\n"
                        
                        try:
                            response_text = await response.text()
                            error_text += f"📝 Ответ: {response_text[:200]}..."
                        except:
                            error_text += f"📝 Ответ: Не удалось прочитать ответ"
                        
                        await api.edit(message, error_text)
                        
            except aiohttp.ClientConnectorError as e:
                error_text = f"❌ Ошибка подключения\n\n"
                error_text += f"📁 Файл: {file_name}\n"
                error_text += f"🌐 URL: {file_url}\n"
                error_text += f"⚠️ Ошибка: {str(e)}\n"
                error_text += f"💡 Возможно, домен недоступен или требует VPN"
                
                await api.edit(message, error_text)
                print(f"❌ Ошибка подключения: {e}")
                
            except aiohttp.ClientTimeout as e:
                error_text = f"❌ Таймаут подключения\n\n"
                error_text += f"📁 Файл: {file_name}\n"
                error_text += f"🌐 URL: {file_url}\n"
                error_text += f"⚠️ Ошибка: {str(e)}"
                
                await api.edit(message, error_text)
                print(f"❌ Таймаут: {e}")
                
            except Exception as e:
                error_text = f"❌ Неожиданная ошибка\n\n"
                error_text += f"📁 Файл: {file_name}\n"
                error_text += f"🌐 URL: {file_url}\n"
                error_text += f"⚠️ Ошибка: {str(e)}"
                
                await api.edit(message, error_text)
                print(f"❌ Неожиданная ошибка: {e}")
                    
    except Exception as e:
        error_text = f"❌ Ошибка загрузки модуля\n\n"
        error_text += f"📁 Файл: {file_name}\n"
        error_text += f"🌐 URL: {file_url}\n"
        error_text += f"⚠️ Ошибка: {str(e)}"
        
        await api.edit(message, error_text)
        print(f"❌ Исключение при загрузке файла: {e}")
        import traceback
        print(f"🔍 DEBUG: Traceback: {traceback.format_exc()}")

async def register(commands):
    commands["load"] = load_command
