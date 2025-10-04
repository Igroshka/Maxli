# Файл: core_modules/restart.py
import asyncio
import json
import time
from pathlib import Path

from core.api import BOT_NAME, BOT_VERSION

RESTART_INFO_FILE = "restart_info.json"

async def restart_command(api, message, args):
    """Команда перезапуска юзербота."""
    await api.edit(message, "🔄 **Перезапуск юзербота...**\n\n⏳ Сохраняю информацию о перезапуске...")
    
    # Сохраняем информацию о перезапуске
    restart_info = {
        "chat_id": message.chat_id,
        "message_id": message.id,
        "restart_time": time.time(),
        "restart_reason": " ".join(args) if args else "Ручной перезапуск"
    }
    
    with open(RESTART_INFO_FILE, 'w', encoding='utf-8') as f:
        json.dump(restart_info, f, indent=2)
    
    # Красивое сообщение о перезапуске
    response = "🔄 Юзербот перезапускается...\n\n"
    response += f"⏰ Время: {time.strftime('%H:%M:%S', time.localtime())}\n"
    response += f"💬 Чат: {message.chat_id}\n"
    response += f"📝 Причина: {restart_info['restart_reason']}\n\n"
    response += "⏳ Ожидайте завершения перезапуска..."
    
    await api.edit(message, response)
    
    # Небольшая задержка для красоты
    await asyncio.sleep(1)
    
    # Завершаем процесс
    print("🔄 Перезапуск инициирован пользователем")
    import os
    import sys
    os.execv(sys.executable, [sys.executable] + sys.argv)

async def check_restart_info(api):
    """Проверяет информацию о перезапуске и обновляет сообщение."""
    restart_file = Path(RESTART_INFO_FILE)
    if not restart_file.exists():
        return
    
    try:
        with open(restart_file, 'r', encoding='utf-8') as f:
            restart_info = json.load(f)
        
        chat_id = restart_info.get('chat_id')
        message_id = restart_info.get('message_id')
        restart_time = restart_info.get('restart_time', time.time())
        restart_reason = restart_info.get('restart_reason', 'Перезапуск')
        
        if not chat_id or not message_id:
            return
        
        # Вычисляем время перезапуска
        current_time = time.time()
        restart_duration = current_time - restart_time
        
        # Обновляем сообщение
        response = "✅ Юзербот запущен!\n\n"
        response += f"⏰ Время запуска: {time.strftime('%H:%M:%S', time.localtime(restart_time))}\n"
        response += f"🕐 Время перезапуска: {restart_duration:.1f} сек\n"
        response += f"💬 Чат: {chat_id}\n"
        response += f"📝 Причина: {restart_reason}\n\n"
        response += "⏳ Загружаю модули..."
        
        await api.client.edit_message(
            chat_id=chat_id,
            message_id=message_id,
            text=response
        )
        
        print(f"✅ Обновлено сообщение о перезапуске в чате {chat_id}")
        
        # НЕ удаляем файл здесь - он нужен для update_restart_complete
        
    except Exception as e:
        print(f"❌ Ошибка при обновлении сообщения о перезапуске: {e}")

async def update_restart_complete(api):
    """Обновляет сообщение о завершении загрузки модулей."""
    restart_file = Path(RESTART_INFO_FILE)
    if not restart_file.exists():
        return
    
    try:
        with open(restart_file, 'r', encoding='utf-8') as f:
            restart_info = json.load(f)
        
        chat_id = restart_info.get('chat_id')
        message_id = restart_info.get('message_id')
        restart_time = restart_info.get('restart_time', time.time())
        restart_reason = restart_info.get('restart_reason', 'Перезапуск')
        
        if not chat_id or not message_id:
            return
        
        # Вычисляем общее время
        current_time = time.time()
        total_duration = current_time - restart_time
        
        # Финальное сообщение
        response = "✅ Юзербот полностью запущен!\n\n"
        response += f"⏰ Время запуска: {time.strftime('%H:%M:%S', time.localtime(restart_time))}\n"
        response += f"🕐 Общее время: {total_duration:.1f} сек\n"
        response += f"💬 Чат: {chat_id}\n"
        response += f"📝 Причина: {restart_reason}\n\n"
        response += f"🤖 {BOT_NAME} v{BOT_VERSION} готов к работе!"
        
        await api.client.edit_message(
            chat_id=chat_id,
            message_id=message_id,
            text=response
        )
        
        # Удаляем файл информации о перезапуске
        restart_file.unlink()
        
        print(f"✅ Завершено обновление сообщения о перезапуске в чате {chat_id}")
        
    except Exception as e:
        print(f"❌ Ошибка при завершении обновления сообщения: {e}")

async def register(commands):
    commands["restart"] = restart_command
