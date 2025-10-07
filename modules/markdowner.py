# name: Markdowner
# version: 1.0.0
# developer: @YouRooni
# id: markdowner
# min-maxli: 34

async def markdown_command(api, message, args):
    """Редактирует сообщение, применяя к нему Markdown форматирование."""
    
    # Если аргументы не переданы, выводим ошибку
    if not args:
        await api.edit(message, "⚠️ **Ошибка:** Вы не ввели текст для форматирования.", markdown=True)
        return

    # Собираем все аргументы обратно в одну строку
    text_to_format = " ".join(args)

    try:
        # Редактируем исходное сообщение с включенным markdown
        await api.edit(message, text_to_format, markdown=True)
    except Exception as e:
        # Если возникла ошибка при форматировании, сообщаем об этом
        # Это может случиться, если в разметке есть ошибки
        error_text = f"❌ **Ошибка форматирования Markdown:**\n`{str(e)}`"
        await api.edit(message, error_text, markdown=True)
        # Также можно вывести ошибку в лог для отладки
        api.LOG_BUFFER.append(f"[markdowner_error] {str(e)}")


async def register(api):
    """Регистрирует команду в боте."""
    api.register_command("md", markdown_command)