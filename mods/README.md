# 📚 Документация по созданию модулей для Maxli UserBot

## 📋 Содержание

1. [Основы создания модулей](#основы-создания-модулей)
2. [Структура модуля](#структура-модуля)
3. [API для работы с сообщениями](#api-для-работы-с-сообщениями)
4. [Работа с файлами и медиа](#работа-с-файлами-и-медиа)
5. [Конфигурация модулей](#конфигурация-модулей)
6. [Продвинутые возможности](#продвинутые-возможности)

## Основы создания модулей

### Минимальный модуль

```python
# name: Мой модуль
# version: 1.0.0
# developer: Ваше имя
# id: my_module
# min-maxli: 34

async def hello_command(api, message, args):
    """Простое приветствие."""
    await api.edit(message, "👋 Привет!", markdown=True)

async def register(api):
    api.register_command("hello", hello_command)
```

### Загрузка модуля

1. Создайте файл в папке `modules/`
2. Отправьте файл боту с командой `.load`
3. Используйте команду с префиксом (например `.hello`)

## Структура модуля

### Обязательные метаданные

```python
# name: Название модуля
# version: 1.0.0
# developer: Имя разработчика
# id: unique_module_id
# min-maxli: 34
```

- `id`: 2-32 символа, только латиница, цифры, дефисы и подчеркивания
- `min-maxli`: Минимальная версия бота для работы модуля
- Файл будет автоматически переименован по ID

### Функции модуля

- `register(api)`: Регистрация команд и вотчеров
- Команды: Асинхронные функции с параметрами `api, message, args`
- Вотчеры: Функции для обработки всех сообщений

## API для работы с сообщениями
### Анимированные эмодзи (ANIMOJI)

Для вставки анимированных эмодзи используйте синтаксис:

```markdown
!(1)  # стандартный анимированый эмодзи по entityId
!(https://st.max.ru/lottie/picker_thumbsup.json)  # кастомная ссылка на lottie (попробовать, но вряд ли это работает)
```

Внутри markdown строки можно комбинировать обычный текст и анимированные эмодзи:

```python
await api.send(chat_id, "Анимированные эмодзи: !(1) !(https://st.max.ru/lottie/picker_heart.json)", markdown=True)
```

#### Пример кастомных:
```python
await api.send(chat_id, "Мой эмодзи !(3) и !(https://my.site/lottie.json)", markdown=True)
```

---
### Обновление профиля

```python
await api.update_profile(
    first_name="Имя",
    last_name="Фамилия",
    description="Описание профиля"
)
```

---
### Создание приватной группы/чата

```python
result = await api.create_group(
    title="Название группы",
    user_ids=[123456, 789012],  # список ID пользователей, не обязателен (если не указать, то будет группа ток где ты)
    description="Описание группы"
)
```

### Основные методы

```python
# Редактирование сообщения
await api.edit(message, "Текст", markdown=True)

# Отправка нового сообщения
await api.send(chat_id, "Текст", markdown=True)

# Ответ на сообщение
await api.reply(message, "Текст", markdown=True)

# Удаление сообщения
await api.delete(message)  # У всех
await api.delete(message, for_me=True)  # Только у себя, хз зач, он врд делетает у себя буквально, у вас в максе останется тоже
```

### Работа с chat_id

```python
# Получение chat_id
chat_id = await api.await_chat_id(message)

# Из сообщения (если доступно)
chat_id = getattr(message, 'chat_id', None)
```

### Markdown форматирование

```python
await api.edit(message, 
    "**Жирный текст**\n"
    "*Курсив*\n"
    "__Подчеркнутый__\n"
    "~~Зачеркнутый~~\n"
    "[Ссылка](https://example.com)",
    "![👍](1) - Анимированый эмодзи",
    markdown=True
)
```

## Работа с файлами и медиа

### Отправка файлов

```python
await api.send_file(
    chat_id=chat_id,
    file_path="path/to/file.txt",
    text="Описание файла",
    markdown=True
)
```

### Отправка фото

```python
await api.send_photo(
    chat_id=chat_id,
    file_path="path/to/image.jpg",
    text="Описание фото",
    markdown=True
)
```

### Получение файлов из сообщений

```python
if message.attaches:
    attach = message.attaches[0]
    file_name = getattr(attach, 'name', 'unknown')
    file_url = getattr(attach, 'url', None)
```

## Конфигурация модулей

### Регистрация настроек

```python
from core.config import register_module_settings, get_module_setting

async def register(api):
    register_module_settings("my_module", {
        "enabled": {
            "default": True,
            "description": "Включить модуль"
        },
        "message": {
            "default": "Привет!",
            "description": "Текст приветствия"
        }
    })
```

### Использование настроек

```python
# Получение значения с fallback
enabled = get_module_setting("my_module", "enabled", True)
message = get_module_setting("my_module", "message", "Привет!")
```

## Продвинутые возможности

### Вотчеры

```python
async def message_watcher(api, message):
    """Обрабатывает все сообщения."""
    text = getattr(message, 'text', '')
    if text.lower() == "привет":
        await api.reply(message, "👋", markdown=True)

async def register(api):
    api.register_command("cmd", command_handler)
    api.register_watcher(message_watcher)
```

### Обработка ошибок

```python
async def safe_command(api, message, args):
    """Пример безопасной обработки ошибок."""
    try:
        result = await some_operation()
        await api.edit(message, f"✅ Готово: {result}", markdown=True)
    except Exception as e:
        await api.edit(message, f"❌ Ошибка: {str(e)}", markdown=True)
        # Логирование в буфер бота
        api.LOG_BUFFER.append(f"[error] {str(e)}")
```

### Реакции на сообщения

```python
# Установка реакции
await api.set_reaction(message, "❤️")
```

## Полезные советы

1. Всегда используйте markdown=True для форматированного текста
2. Обрабатывайте ошибки в try/except блоках
3. Используйте документацию команд (docstring)
4. Очищайте временные файлы
5. Следите за уникальностью ID модуля

## Примеры модулей

### Модуль с настройками

```python
# name: Приветствие
# version: 1.0.0
# developer: Example
# id: greeter
# min-maxli: 34

from core.config import register_module_settings, get_module_setting

async def greet_command(api, message, args):
    """Приветствует пользователя с настраиваемым текстом."""
    text = get_module_setting("greeter", "message", "Привет!")
    await api.edit(message, text, markdown=True)

async def register(api):
    register_module_settings("greeter", {
        "message": {
            "default": "👋 Привет!",
            "description": "Текст приветствия"
        }
    })
    api.register_command("greet", greet_command)
```

### Модуль с файлами

```python
# name: Файловый менеджер
# version: 1.0.0
# developer: Example
# id: file_manager
# min-maxli: 34

import os

async def upload_command(api, message, args):
    """Загружает файл в чат."""
    if not args:
        await api.edit(message, "⚠️ Укажите путь к файлу", markdown=True)
        return
        
    file_path = args[0]
    chat_id = await api.await_chat_id(message)
    
    if not os.path.exists(file_path):
        await api.edit(message, "❌ Файл не найден", markdown=True)
        return
        
    await api.send_file(
        chat_id=chat_id,
        file_path=file_path,
        text=f"📁 Файл: **{os.path.basename(file_path)}**",
        markdown=True
    )

async def register(api):
    api.register_command("upload", upload_command)
```