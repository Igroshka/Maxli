import time

async def ping_command(api, message, args):
    start_time = time.time()
    await api.edit(message, "Вычисляю...")
    end_time = time.time()
    ping_ms = round((end_time - start_time) * 1000, 2)
    await api.edit(message, f"🏓 Понг!\n⏱ Задержка: {ping_ms} мс")

async def register(commands):
    commands["ping"] = ping_command