# name: Maxli Store
# version: 1.4.1
# developer: Kerdik
# id: maxli_store
# dependencies: aiohttp
# min-maxli: 26

import aiohttp
import re
import os

# Только один репозиторий
REPOSITORY_URLS = [
    "https://github.com/zyphralex/MaxliStore"
]

def extract_repo_info(url):
    """Извлекает владельца и название репозитория из URL"""
    match = re.search(r'github\.com/([^/]+)/([^/]+)', url)
    if match:
        owner = match.group(1)
        repo_name = match.group(2)
        # Убираем .git если есть
        repo_name = repo_name.replace('.git', '')
        return {
            "name": f"{owner}/{repo_name}",
            "path": f"{owner}/{repo_name}",
            "url": url
        }
    return None

# Автоматически создаем список репозиториев
REPOSITORIES = []
for url in REPOSITORY_URLS:
    repo_info = extract_repo_info(url)
    if repo_info:
        REPOSITORIES.append(repo_info)

# Если не удалось распарсить, используем fallback
if not REPOSITORIES:
    REPOSITORIES = [{
        "name": "zyphralex/MaxliStore",
        "path": "zyphralex/MaxliStore", 
        "url": "https://github.com/zyphralex/MaxliStore"
    }]

current_repo_index = 0

def get_current_repo():
    return REPOSITORIES[current_repo_index]

async def maxlistore_command(api, message, args):
    """Ищет модули в GitHub репозитории по названию файлов."""
    if not args:
        await show_help(api, message)
        return
    
    search_query = " ".join(args).lower()
    await api.edit(message, "🔍 Ищу модули в репозитории...")
    
    try:
        current_repo = get_current_repo()
        all_modules = await get_repo_modules(current_repo["path"])
        
        if not all_modules:
            await api.edit(message, f"❌ Не удалось загрузить модули из репозитория\n📂 {current_repo['name']}")
            return
        
        # Фильтруем модули по поисковому запросу
        matched_modules = []
        for module in all_modules:
            module_name = module['name'].lower().replace('.py', '')
            if search_query in module_name:
                matched_modules.append(module)
        
        if not matched_modules:
            available_modules = "\n".join([f"• {m['name'].replace('.py', '')}" for m in all_modules[:10]])
            more_text = f"\n... и еще {len(all_modules) - 10} модулей" if len(all_modules) > 10 else ""
            
            await api.edit(message, f"❌ Не найдено модулей по запросу: '{search_query}'\n\n📂 Репозиторий: {current_repo['name']}\n\n📋 Доступные модули:\n{available_modules}{more_text}\n\n💡 Используйте: .maxlistore_list чтобы увидеть все модули")
            return
        
        if len(matched_modules) == 1:
            # Если найден только один модуль - сразу скачиваем
            await download_module(api, message, matched_modules[0], current_repo)
        else:
            # Показываем список
            await show_modules_list(api, message, matched_modules, search_query, current_repo)
            
    except Exception as e:
        await api.edit(message, f"❌ Ошибка поиска: {str(e)}")

async def maxlistore_s_command(api, message, args):
    """Поиск модулей по части названия (до 20 результатов)."""
    if not args:
        await api.edit(message, "❌ Укажите часть названия модуля: .maxlistore_s weather")
        return
    
    search_query = " ".join(args).lower()
    await api.edit(message, f"🔍 Ищу модули по запросу '{search_query}'...")
    
    try:
        current_repo = get_current_repo()
        all_modules = await get_repo_modules(current_repo["path"])
        
        if not all_modules:
            await api.edit(message, f"❌ Не удалось загрузить модули из репозитория\n📂 {current_repo['name']}")
            return
        
        # Фильтруем модули по части названия
        matched_modules = []
        for module in all_modules:
            module_name = module['name'].lower().replace('.py', '')
            if search_query in module_name:
                matched_modules.append(module)
        
        # Ограничиваем 20 результатами
        matched_modules = matched_modules[:20]
        
        if not matched_modules:
            await api.edit(message, f"❌ Не найдено модулей по запросу: '{search_query}'\n\n💡 Попробуйте другой запрос или используйте .maxlistore_list для просмотра всех модулей")
            return
        
        # Показываем результаты поиска
        await show_search_results(api, message, matched_modules, search_query, current_repo)
            
    except Exception as e:
        await api.edit(message, f"❌ Ошибка поиска: {str(e)}")

async def maxlistore_download_command(api, message, args):
    """Скачивает модуль по номеру из предыдущего поиска."""
    if not args or not args[0].isdigit():
        await api.edit(message, "❌ Укажите номер модуля: .maxlistore_download 1")
        return
    
    module_number = int(args[0])
    search_query = " ".join(args[1:]) if len(args) > 1 else ""
    
    await api.edit(message, "🔄 Получаю информацию о модуле...")
    
    try:
        # Используем текущий выбранный репозиторий
        current_repo = get_current_repo()
        all_modules = await get_repo_modules(current_repo["path"])
        
        if not all_modules:
            await api.edit(message, f"❌ Не удалось загрузить модули из репозитория: {current_repo['name']}")
            return
        
        if search_query:
            # Фильтруем по новому запросу
            matched_modules = []
            for module in all_modules:
                module_name = module['name'].lower().replace('.py', '')
                if search_query in module_name:
                    matched_modules.append(module)
        else:
            matched_modules = all_modules
        
        if not matched_modules or module_number < 1 or module_number > len(matched_modules):
            await api.edit(message, f"❌ Неверный номер модуля. Доступно: 1-{len(matched_modules) if matched_modules else 0}")
            return
        
        module = matched_modules[module_number - 1]
        await download_module(api, message, module, current_repo)
        
    except Exception as e:
        await api.edit(message, f"❌ Ошибка загрузки: {str(e)}")

async def maxlistore_list_command(api, message, args):
    """Показывает все доступные модули в репозитории."""
    await api.edit(message, "📋 Загружаю список модулей...")
    
    try:
        current_repo = get_current_repo()
        all_modules = await get_repo_modules(current_repo["path"])
        
        if not all_modules:
            await api.edit(message, f"❌ Не удалось загрузить модули из репозитория: {current_repo['name']}")
            return
        
        await show_all_modules(api, message, all_modules, current_repo)
        
    except Exception as e:
        await api.edit(message, f"❌ Ошибка: {str(e)}")

async def maxlistore_repo_command(api, message, args):
    """Показывает информацию о репозитории."""
    current_repo = get_current_repo()
    
    repo_info = f"""📂 Информация о репозитории

🔗 Ссылка: {current_repo['url']}
📁 Путь: {current_repo['path']}

⚡ Команды:
`.maxlistore <название>` - поиск модулей
`.maxlistore_s <часть_названия>` - поиск по части названия (до 20)
`.maxlistore_list` - все модули
`.maxlistore_download <номер>` - скачать модуль

💡 Пример:
`.maxlistore_s weat` - найти модули с "weat" в названии
`.maxlistore_download 1` - скачать первый модуль"""
    
    await api.edit(message, repo_info)

async def show_help(api, message):
    """Показывает справку по командам."""
    current_repo = get_current_repo()
    
    help_text = f"""📦 Maxli Store - Менеджер модулей

📂 Репозиторий: {current_repo['name']}

Команды:
`.maxlistore <название>` - точный поиск модулей
`.maxlistore_s <часть_названия>` - поиск по части названия (до 20)
`.maxlistore_list` - все модули
`.maxlistore_download <номер>` - скачать модуль
`.maxlistore_repo` - информация о репозитории

Примеры:
`.maxlistore weather` - поиск модуля "weather"
`.maxlistore_s weat` - поиск модулей с "weat" в названии
`.maxlistore_s tik` - поиск TikTok модулей
`.maxlistore_list` - список всех модулей
`.maxlistore_download 1` - скачать модуль №1"""

    await api.edit(message, help_text)

async def show_modules_list(api, message, modules, search_query, repo):
    """Показывает список найденных модулей."""
    response = [f"📦 Найдено модулей по запросу '{search_query}':\n"]
    response.append(f"📂 Репозиторий: {repo['name']}")
    response.append(f"📊 Найдено: {len(modules)} модулей\n")
    
    for i, module in enumerate(modules, 1):
        name = module['name'].replace('.py', '')
        size_kb = module.get('size', 0) / 1024
        
        response.append(f"{i}. {name}")
        response.append(f"   📏 {size_kb:.1f} KB")
        response.append(f"   💾 `.maxlistore_download {i}`")
        response.append("")
    
    await api.edit(message, "\n".join(response))

async def show_search_results(api, message, modules, search_query, repo):
    """Показывает результаты поиска по части названия."""
    response = [f"🔍 Результаты поиска по '{search_query}':\n"]
    response.append(f"📂 Репозиторий: {repo['name']}")
    response.append(f"📊 Найдено: {len(modules)} модулей\n")
    
    for i, module in enumerate(modules, 1):
        name = module['name'].replace('.py', '')
        size_kb = module.get('size', 0) / 1024
        
        # Подсвечиваем найденную часть в названии
        highlighted_name = name
        if search_query in name.lower():
            start_idx = name.lower().find(search_query)
            end_idx = start_idx + len(search_query)
            highlighted_name = (
                name[:start_idx] + 
                f"{name[start_idx:end_idx]}" + 
                name[end_idx:]
            )
        
        response.append(f"{i}. {highlighted_name}")
        response.append(f"   📏 {size_kb:.1f} KB")
        response.append(f"   💾 `.maxlistore_download {i}`")
        response.append("")
    
    if len(modules) == 20:
        response.append("💡 Показано первые 20 результатов")
        response.append("🔍 Для более точного поиска уточните запрос")
    
    await api.edit(message, "\n".join(response))

async def show_all_modules(api, message, modules, repo):
    """Показывает все модули в репозитории."""
    modules_per_page = 15
    
    response = [f"📦 Все модули в репозитории:\n"]
    response.append(f"📂 Репозиторий: {repo['name']}")
    response.append(f"🔗 Ссылка: {repo['url']}")
    response.append(f"📊 Всего модулей: {len(modules)}\n")
    
    for i, module in enumerate(modules[:modules_per_page], 1):
        name = module['name'].replace('.py', '')
        size_kb = module.get('size', 0) / 1024
        response.append(f"{i}. {name} ({size_kb:.1f} KB)")
    
    if len(modules) > modules_per_page:
        response.append(f"\n... и еще {len(modules) - modules_per_page} модулей")
    
    response.append(f"\n💡 Для скачивания: `.maxlistore_download <номер>`")
    response.append(f"🔍 Для поиска: `.maxlistore_s <часть_названия>`")
    
    await api.edit(message, "\n".join(response))

async def download_module(api, message, module, repo):
    """Скачивает и отправляет модуль."""
    module_name = module['name'].replace('.py', '')
    await api.edit(message, f"⬇️ Скачиваю модуль '{module_name}'...")
    
    try:
        # Получаем raw ссылку на файл
        download_url = module.get('download_url')
        if not download_url:
            download_url = await get_raw_download_url(module, repo["path"])
        
        if not download_url:
            await api.edit(message, "❌ Не удалось получить ссылку для скачивания")
            return
        
        # Скачиваем файл
        file_content = await download_file(download_url)
        
        if not file_content:
            await api.edit(message, "❌ Не удалось скачать файл модуля")
            return
        
        # Сохраняем временно
        temp_filename = f"{module['name']}"
        with open(temp_filename, 'w', encoding='utf-8') as f:
            f.write(file_content)
        
        # Получаем chat_id из исходного сообщения (исправлено!)
        chat_id = message.chat_id
        
        # Отправляем файл в ТОТ ЖЕ чат
        result = await api.send_file(
            chat_id=chat_id,
            file_path=temp_filename,
            text=f"📦 Модуль: {module_name}\n📂 Репозиторий: {repo['name']}\n⚡ Скачан через Maxli Store"
        )
        
        # Очистка
        os.remove(temp_filename)
        
        if result:
            await api.delete(message)
        else:
            await api.edit(message, "✅ Модуль скачан, но не удалось отправить файл")
            
    except Exception as e:
        await api.edit(message, f"❌ Ошибка загрузки модуля: {str(e)}")

async def get_repo_modules(repo_path):
    """Получает все .py файлы из репозитория."""
    try:
        api_url = f"https://api.github.com/repos/{repo_path}/contents/"
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "User-Agent": "Maxli-Bot/1.0",
                "Accept": "application/vnd.github.v3+json"
            }
            
            async with session.get(api_url, headers=headers) as response:
                if response.status == 200:
                    contents = await response.json()
                    # Фильтруем только .py файлы
                    py_files = [item for item in contents if item['type'] == 'file' and item['name'].endswith('.py')]
                    return py_files
                else:
                    return []
                    
    except Exception:
        return []

async def get_raw_download_url(module, repo_path):
    """Генерирует raw ссылку для скачивания."""
    file_path = module['path']
    return f"https://raw.githubusercontent.com/{repo_path}/main/{file_path}"

async def download_file(url):
    """Скачивает содержимое файла."""
    async with aiohttp.ClientSession() as session:
        headers = {"User-Agent": "Maxli-Bot/1.0"}
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.text()
    return None

async def register(api):
    """Регистрирует команды модуля."""
    api.register_command("maxlistore", maxlistore_command)
    api.register_command("maxlistore_s", maxlistore_s_command)
    api.register_command("maxlistore_download", maxlistore_download_command)
    api.register_command("maxlistore_list", maxlistore_list_command)
    api.register_command("maxlistore_repo", maxlistore_repo_command)