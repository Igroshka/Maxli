# Модуль: Генератор изображений
# Версия: 1.0.0
# Разработчик: Maxli Team
# Зависимости: requests, aiohttp, aiofiles

import aiohttp
import aiofiles
import os
import asyncio

# Доступные модели
AVAILABLE_MODELS = {
    "1": "flux",
    "2": "turbo", 
    "3": "nanobanana",
    "4": "seedream",
    "flux": "flux",
    "turbo": "turbo",
    "nanobanana": "nanobanana",
    "seedream": "seedream"
}

# Текущая модель (по умолчанию flux)
current_model = "flux"

async def genimg_command(api, message, args):
    """Генерирует изображение по промпту."""
    if not args:
        await api.edit(message, "🎨 Генератор изображений\n\nИспользование: .genimg [промпт]\nПример: .genimg красивая природа\n\nТекущая модель: " + current_model)
        return
    
    prompt = " ".join(args)
    
    # Получаем chat_id из сообщения, если он есть
    chat_id = getattr(message, 'chat_id', None)
    if not chat_id:
        chat_id = await api.await_chat_id(message)
    
    if not chat_id:
        await api.edit(message, "❌ Не удалось определить chat_id")
        return
    
    await api.edit(message, f"🎨 Генерирую изображение...\nПромпт: {prompt}\nМодель: {current_model}")
    
    try:
        # URL для генерации изображения
        image_url = f"https://pollinations.ai/p/{prompt}?width=1024&height=1024&model={current_model}&nologo=true"
        
        print(f"🔍 DEBUG: Генерируем изображение по URL: {image_url}")
        
        # Скачиваем изображение
        timeout = aiohttp.ClientTimeout(total=60)  # 60 секунд на генерацию
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(image_url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    print(f"✅ Изображение скачано, размер: {len(image_data)} байт")
                    
                    # Сохраняем временно
                    temp_path = f"temp_gen_{message.id}.jpg"
                    async with aiofiles.open(temp_path, 'wb') as f:
                        await f.write(image_data)
                    
                    # Отправляем как фотографию
                    result = await api.send_photo(
                        chat_id=chat_id,
                        file_path=temp_path,
                        text=f"🎨 Изображение: {prompt}\n🤖 Модель: {current_model}"
                    )
                    
                    # Удаляем временный файл
                    try:
                        os.remove(temp_path)
                        print(f"🧹 Удален временный файл: {temp_path}")
                    except:
                        pass
                    
                    if result:
                        # Удаляем сообщение вместо показа текста
                        await api.delete(message)
                    else:
                        await api.edit(message, "❌ Ошибка отправки изображения")
                else:
                    await api.edit(message, f"❌ Ошибка генерации: HTTP {response.status}\nВозможно, сервис недоступен")
    except asyncio.TimeoutError:
        await api.edit(message, "⏰ Таймаут генерации изображения\nПопробуйте еще раз или измените промпт")
    except Exception as e:
        await api.edit(message, f"❌ Ошибка: {str(e)}")
        print(f"❌ Ошибка в genimg_command: {e}")

async def genimgmodel_command(api, message, args):
    """Устанавливает модель для генерации изображений."""
    global current_model
    
    if not args:
        # Показываем список доступных моделей
        models_text = "🤖 Доступные модели для генерации изображений:\n\n"
        for i, (key, model) in enumerate(AVAILABLE_MODELS.items(), 1):
            if key.isdigit():
                status = "✅" if model == current_model else "⚪"
                models_text += f"{status} {i}. {model}\n"
        
        models_text += f"\nТекущая модель: **{current_model}**\n"
        models_text += "\nИспользование: .genimgmodel [номер или название]\n"
        models_text += "Примеры: .genimgmodel 1 или .genimgmodel flux"
        
        await api.edit(message, models_text)
        return
    
    model_input = args[0].lower()
    
    if model_input in AVAILABLE_MODELS:
        old_model = current_model
        current_model = AVAILABLE_MODELS[model_input]
        await api.edit(message, f"✅ Модель изменена: {old_model} → **{current_model}**")
    else:
        await api.edit(message, f"❌ Неизвестная модель: {model_input}\nИспользуйте .genimgmodel для просмотра списка")

async def register(api):
    """Регистрирует команды модуля."""
    api.register_command("genimg", genimg_command)
    api.register_command("genimgmodel", genimgmodel_command)
