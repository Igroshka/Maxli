# 📚 Документация по созданию модулей для Maxli UserBot

Добро пожаловать в документацию по созданию модулей для Maxli UserBot! Здесь вы найдете все необходимое для создания собственных модулей.

## 📋 Содержание

1. [Быстрый старт](#быстрый-старт)
2. [Структура модуля](#структура-модуля)
3. [Основные методы API](#основные-методы-api)
4. [Работа с файлами](#работа-с-файлами)
5. [Работа с фотографиями](#работа-с-фотографиями)
6. [Продвинутые возможности](#продвинутые-возможности)
7. [Примеры модулей](#примеры-модулей)

---

## 🚀 Быстрый старт

### Минимальный модуль

Создайте файл `modules/my_module.py`:

```python
# Модуль: Мой первый модуль
# Версия: 1.0.0
# Разработчик: Ваше имя

async def hello_command(api, message, args):
    """Команда приветствия."""
    await api.edit(message, "Привет! Это мой первый модуль! 👋")

async def register(api):
    """Регистрирует команды модуля."""
    api.register_command("hello", hello_command)
```

### Загрузка модуля

1. Поместите файл в папку `modules/`
2. Используйте команду `.load my_module`
3. Используйте команду `.hello`

---

## 📁 Структура модуля

### Заголовок модуля

```python
# Модуль: Название модуля
# Версия: 1.0.0
# Разработчик: Имя разработчика
# Зависимости: requests, aiohttp
# Минимальная версия Maxli: 0.2.6
```

### Обязательные элементы

- **Функция `register(api)`** - регистрирует команды модуля
- **Команды** - функции, которые выполняются при вызове команд

---

## 🔧 Основные методы API

### Отправка сообщений

```python
# Редактирование сообщения
await api.edit(message, "Новый текст")

# Отправка нового сообщения
await api.send(chat_id, "Текст сообщения")

# Ответ на сообщение
await api.reply(message, "Ответ")

# Отправка фотографии
await api.send_photo(chat_id, "path/to/photo.jpg", "Описание фото")

# Отправка файла
await api.send_file(chat_id, "path/to/file.txt", "Описание файла")
```

### Получение информации

```python
# Получение chat_id
chat_id = await api.await_chat_id(message)

# Получение ID отправителя
sender_id = api.get_sender_id(message)

# Получение текста сообщения
text = api.get_message_text(message)
```

### Работа с сообщениями

```python
# Удаление сообщения у всех
await api.delete(message)

# Удаление только для себя
await api.delete(message, for_me=True)

# Редактирование сообщения
await api.edit(message, "Новый текст")

# Отправка нового сообщения
await api.send(chat_id, "Текст сообщения")

# Ответ на сообщение
await api.reply(message, "Ответ")
```

### Удаление сообщений

```python
async def delete_message_example(api, message, args):
    """Пример удаления сообщений."""
    
    # Удаляем сообщение у всех пользователей
    await api.delete(message)
    
    # Удаляем только для себя (другие увидят сообщение)
    await api.delete(message, for_me=True)
    
    # Удаляем после успешной операции
    result = await some_operation()
    if result:
        await api.delete(message)  # Удаляем исходное сообщение
    else:
        await api.edit(message, "❌ Ошибка операции")
```

---

## 📎 Работа с файлами

### Отправка файлов

```python
async def send_file_command(api, message, args):
    """Отправляет файл."""
    if not args:
        await api.edit(message, "Укажите путь к файлу")
        return
    
    file_path = args[0]
    chat_id = await api.await_chat_id(message)
    
    # Отправка файла
    result = await api.send_file(
        chat_id=chat_id,
        file_path=file_path,
        text="Вот ваш файл! 📎"
    )
    
    if result:
        await api.edit(message, "✅ Файл отправлен!")
    else:
        await api.edit(message, "❌ Ошибка отправки файла")
```

### Получение файлов из сообщений

```python
async def process_file_command(api, message, args):
    """Обрабатывает файл из сообщения."""
    if not message.attaches:
        await api.edit(message, "В сообщении нет файлов")
        return
    
    attach = message.attaches[0]
    file_name = getattr(attach, 'name', 'unknown')
    file_url = getattr(attach, 'url', None)
    
    if file_url:
        await api.edit(message, f"📎 Файл: {file_name}\n🔗 URL: {file_url}")
    else:
        await api.edit(message, f"📎 Файл: {file_name}\n❌ URL недоступен")
```

---

## 📸 Работа с фотографиями

### Отправка фотографий

```python
import aiohttp
import aiofiles
import os

async def send_photo_command(api, message, args):
    """Отправляет фотографию."""
    if not args:
        await api.edit(message, "Укажите URL изображения")
        return
    
    image_url = args[0]
    
    # Получаем chat_id
    chat_id = getattr(message, 'chat_id', None)
    if not chat_id:
        chat_id = await api.await_chat_id(message)
    
    if not chat_id:
        await api.edit(message, "❌ Не удалось определить chat_id")
        return
    
    try:
        # Скачиваем изображение
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    
                    # Сохраняем временно
                    temp_path = f"temp_photo_{message.id}.jpg"
                    async with aiofiles.open(temp_path, 'wb') as f:
                        await f.write(image_data)
                    
                    # Отправляем как фотографию (с превью)
                    result = await api.send_photo(
                        chat_id=chat_id,
                        file_path=temp_path,
                        text="📸 Фотография"
                    )
                    
                    # Удаляем временный файл
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                    
                    if result:
                        # Удаляем исходное сообщение
                        await api.delete(message)
                    else:
                        await api.edit(message, "❌ Ошибка отправки фотографии")
                else:
                    await api.edit(message, f"❌ Ошибка скачивания: HTTP {response.status}")
    except Exception as e:
        await api.edit(message, f"❌ Ошибка: {str(e)}")
```

### Отправка локальных фотографий

```python
async def send_local_photo_command(api, message, args):
    """Отправляет локальную фотографию."""
    if not args:
        await api.edit(message, "Укажите путь к файлу")
        return
    
    file_path = args[0]
    
    # Получаем chat_id
    chat_id = getattr(message, 'chat_id', None)
    if not chat_id:
        chat_id = await api.await_chat_id(message)
    
    if not chat_id:
        await api.edit(message, "❌ Не удалось определить chat_id")
        return
    
    try:
        # Проверяем существование файла
        if not os.path.exists(file_path):
            await api.edit(message, f"❌ Файл не найден: {file_path}")
            return
        
        # Отправляем как фотографию
        result = await api.send_photo(
            chat_id=chat_id,
            file_path=file_path,
            text="📸 Локальная фотография"
        )
        
        if result:
            # Удаляем исходное сообщение
            await api.delete(message)
        else:
            await api.edit(message, "❌ Ошибка отправки фотографии")
            
    except Exception as e:
        await api.edit(message, f"❌ Ошибка: {str(e)}")
```

### Разница между send_photo и send_file

```python
# send_photo - отправляет как фотографию с превью
await api.send_photo(chat_id, "photo.jpg", "Описание")

# send_file - отправляет как файл-вложение
await api.send_file(chat_id, "document.pdf", "Описание")
```

---

## 🎯 Продвинутые возможности

### Вотчеры (обработка всех сообщений)

```python
async def message_watcher(api, message):
    """Обрабатывает все сообщения."""
    text = api.get_message_text(message)
    
    # Реагируем на определенные слова
    if "бот" in text.lower():
        await api.reply(message, "Да, я здесь! 🤖")

async def register(api):
    """Регистрирует команды и вотчеры."""
    api.register_command("mycommand", my_command)
    api.register_watcher(message_watcher)  # Регистрируем вотчер
```

### Работа с аргументами команд

```python
async def complex_command(api, message, args):
    """Сложная команда с аргументами."""
    if not args:
        await api.edit(message, "Использование: .command <аргумент1> <аргумент2>")
        return
    
    arg1 = args[0]
    arg2 = args[1] if len(args) > 1 else "по умолчанию"
    
    await api.edit(message, f"Аргумент 1: {arg1}\nАргумент 2: {arg2}")
```

### Обработка ошибок

```python
async def safe_command(api, message, args):
    """Команда с обработкой ошибок."""
    try:
        # Ваш код здесь
        result = some_risky_operation()
        await api.edit(message, f"Результат: {result}")
    except Exception as e:
        await api.edit(message, f"❌ Ошибка: {str(e)}")
        print(f"Ошибка в команде: {e}")  # Логирование
```

---

## 📝 Примеры модулей

### 1. Модуль погоды

```python
# Модуль: Погода
# Версия: 1.0.0
# Разработчик: YouRooni

import aiohttp

async def weather_command(api, message, args):
    """Получает погоду для города."""
    if not args:
        await api.edit(message, "Укажите город: .weather Москва")
        return
    
    city = " ".join(args)
    
    try:
        # Здесь был бы реальный API погоды
        await api.edit(message, f"🌤️ Погода в {city}: +20°C, солнечно")
    except Exception as e:
        await api.edit(message, f"❌ Ошибка получения погоды: {str(e)}")

async def register(api):
    api.register_command("weather", weather_command)
```

### 2. Модуль калькулятора

```python
# Модуль: Калькулятор
# Версия: 1.0.0
# Разработчик: YouRooni

async def calc_command(api, message, args):
    """Выполняет математические вычисления."""
    if not args:
        await api.edit(message, "Укажите выражение: .calc 2+2")
        return
    
    expression = " ".join(args)
    
    try:
        # Безопасное вычисление
        result = eval(expression)
        await api.edit(message, f"🧮 {expression} = {result}")
    except Exception as e:
        await api.edit(message, f"❌ Ошибка вычисления: {str(e)}")

async def register(api):
    api.register_command("calc", calc_command)
```

### 3. Модуль генерации изображений

```python
# Модуль: Генератор изображений
# Версия: 1.0.0
# Разработчик: YouRooni

import aiohttp
import aiofiles
import os

async def genimg_command(api, message, args):
    """Генерирует изображение по промпту."""
    if not args:
        await api.edit(message, "Укажите промпт: .genimg красивая природа")
        return
    
    prompt = " ".join(args)
    chat_id = await api.await_chat_id(message)
    
    await api.edit(message, "🎨 Генерирую изображение...")
    
    try:
        # URL для генерации изображения
        image_url = f"https://pollinations.ai/p/{prompt}?width=1024&height=1024&nologo=true"
        
        # Скачиваем изображение
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    
                    # Сохраняем временно
                    temp_path = f"temp_gen_{message.id}.jpg"
                    async with aiofiles.open(temp_path, 'wb') as f:
                        await f.write(image_data)
                    
                    # Отправляем файл
                    result = await api.send_file(
                        chat_id=chat_id,
                        file_path=temp_path,
                        text=f"🎨 Изображение: {prompt}"
                    )
                    
                    # Удаляем временный файл
                    os.remove(temp_path)
                    
                    if result:
                        await api.edit(message, "✅ Изображение сгенерировано!")
                    else:
                        await api.edit(message, "❌ Ошибка отправки изображения")
                else:
                    await api.edit(message, f"❌ Ошибка генерации: HTTP {response.status}")
    except Exception as e:
        await api.edit(message, f"❌ Ошибка: {str(e)}")

async def register(api):
    api.register_command("genimg", genimg_command)
```

---

## 🛠️ Полезные советы

### 1. Именование команд
- Используйте понятные имена: `weather`, `calc`, `genimg`
- Избегайте конфликтов с системными командами

### 2. Обработка ошибок
- Всегда оборачивайте код в `try-except`
- Показывайте пользователю понятные сообщения об ошибках

### 3. Производительность
- Используйте `async/await` для асинхронных операций
- Очищайте временные файлы

### 4. Документация
- Добавляйте комментарии к функциям
- Указывайте версию и автора в заголовке

---

## 📞 Поддержка

Если у вас есть вопросы по созданию модулей, обратитесь ко мне в тг (линк на главной, сюда лень вставлять).

**Удачного программирования! 🚀**