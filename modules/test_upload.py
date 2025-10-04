# Модуль: Тестирование отправки файлов
# Версия: 1.0.0
# Разработчик: Maxli Team

import asyncio
from pathlib import Path

async def test_upload_command(api, message, args):
    """Команда для тестирования отправки файлов."""
    try:
        # Получаем chat_id
        chat_id = getattr(message, 'chat_id', None)
        if not chat_id:
            chat_id = await api.await_chat_id(message)
        
        if not chat_id:
            await api.edit(message, "❌ Не удалось определить chat_id")
            return
        
        await api.edit(message, "🧪 Тестирую отправку файлов...")
        
        # Создаем тестовый файл
        test_file_path = Path("test_upload.py")
        test_content = '''# Тестовый файл для проверки отправки
def test_function():
    return "Файл успешно отправлен!"

print("Тест пройден!")
'''
        
        # Записываем тестовый файл
        with open(test_file_path, 'w', encoding='utf-8') as f:
            f.write(test_content)
        
        print(f"✅ Создан тестовый файл: {test_file_path}")
        
        # Пытаемся отправить файл
        try:
            result = await api.send_file(
                chat_id=chat_id,
                file_path=test_file_path,
                text="🧪 Тестовый файл для проверки отправки"
            )
            
            if result:
                await api.edit(message, "✅ Тест отправки файла прошел успешно!")
            else:
                await api.edit(message, "❌ Тест отправки файла не удался")
        except Exception as send_error:
            print(f"❌ Ошибка при отправке файла: {send_error}")
            await api.edit(message, f"❌ Ошибка при отправке файла: {str(send_error)}")
        
        # Удаляем тестовый файл
        if test_file_path.exists():
            test_file_path.unlink()
            print(f"🧹 Удален тестовый файл: {test_file_path}")
            
    except Exception as e:
        await api.edit(message, f"❌ Ошибка при тестировании: {str(e)}")
        print(f"❌ Ошибка в test_upload_command: {e}")
        import traceback
        print(f"🔍 DEBUG: Traceback: {traceback.format_exc()}")

async def register(api):
    """Регистрирует команды модуля."""
    api.register_command("testupload", test_upload_command)
    api.register_command("testfile", test_upload_command)
