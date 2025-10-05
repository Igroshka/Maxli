import time
from core.config import get_banner_url

async def ping_command(api, message, args):
    snippet = getattr(message, 'text', '')
    api.LOG_BUFFER.append(f"[ping] {snippet[:80]}")
    start_time = time.time()
    await api.edit(message, "Вычисляю...")
    end_time = time.time()
    ping_ms = round((end_time - start_time) * 1000, 2)
    text = f"🏓 Понг!\n⏱ Задержка: {ping_ms} мс"
    banner = get_banner_url("ping")
    if banner:
        chat_id = getattr(message, 'chat_id', None) or await api.await_chat_id(message)
        if chat_id:
            await api.send_photo(chat_id, banner, text)
            return
    await api.edit(message, text)

async def register(commands):
    commands["ping"] = ping_command