# name: SpeedTest
# version: 1.0.0
# developer: @gemeguardian
# dependencies: speedtest-cli
# min-maxli: 26

import datetime
import time
import asyncio
import sys

STRINGS = {
    "ru": {
        "no_speedtest": (
            "❌ Библиотека speedtest-cli не найдена!\n\n"
            "Установка:\n"
            "pip install speedtest-cli\n\n"
            "После установки перезапустите бота командой:\n"
            ".restart"
        ),
        "starting_test": "💬 Запуск теста скорости...\nПоиск лучшего сервера...",
        "selecting_server": "💬 Запуск теста скорости...\nВыбор оптимального сервера...",
        "testing_download": "💬 Запуск теста скорости...\n⬇️ Тестирование скорости загрузки...",
        "testing_upload": "💬 Запуск теста скорости...\n⬆️ Тестирование скорости отдачи...",
        "finalizing_results": "💬 Запуск теста скорости...\nОбработка результатов...",
        "error": "❌ Не удалось выполнить тест скорости:\n{}",
        "results": (
            "📈 Тест скорости интернета:\n\n"
            "⬇️ Загрузка: {download} Мбит/с\n"
            "⬆️ Отдача: {upload} Мбит/с\n"
            "⏲ Пинг: {ping:.1f} мс\n\n"
            "📍 Сервер: {server_name}, {server_country}\n"
            "⚙ Провайдер: {server_sponsor}\n\n"
            "🕔 Примерное время загрузки:\n"
            "🖼 Фото (5 МБ): {est_5mb}\n"
            "📦 Приложение (100 МБ): {est_100mb}\n"
            "📼 HD Фильм (2 ГБ): {est_2gb}\n"
            "🎮 Игра (50 ГБ): {est_50gb}\n\n"
            "⏲ Тест занял: {duration:.1f} сек\n"
            "🗓 Время (МСК): {time_msk}"
        )
    },
    "en": {
        "no_speedtest": (
            "❌ speedtest-cli library not found!\n\n"
            "Install:\n"
            "pip install speedtest-cli\n\n"
            "After installation, restart the bot:\n"
            ".restart"
        ),
        "starting_test": "💬 Running speed test...\nFinding best server...",
        "selecting_server": "💬 Running speed test...\nSelecting optimal server...",
        "testing_download": "💬 Running speed test...\n⬇️ Testing download speed...",
        "testing_upload": "💬 Running speed test...\n⬆️ Testing upload speed...",
        "finalizing_results": "💬 Running speed test...\nProcessing results...",
        "error": "❌ Speed test failed:\n{}",
        "results": (
            "📈 Internet Speed Test:\n\n"
            "⬇️ Download: {download} Mbps\n"
            "⬆️ Upload: {upload} Mbps\n"
            "⏲ Ping: {ping:.1f} ms\n\n"
            "📍 Server: {server_name}, {server_country}\n"
            "⚙ Provider: {server_sponsor}\n\n"
            "🕔 Estimated download time:\n"
            "🖼 Photo (5 MB): {est_5mb}\n"
            "📦 App (100 MB): {est_100mb}\n"
            "📼 HD Movie (2 GB): {est_2gb}\n"
            "🎮 Game (50 GB): {est_50gb}\n\n"
            "⏲ Test took: {duration:.1f} sec\n"
            "🗓 Time (MSK): {time_msk}"
        )
    }
}

def get_string(key, lang="ru"):
    """Получает строку локализации."""
    return STRINGS.get(lang, STRINGS["en"]).get(key, STRINGS["en"].get(key, ""))

def bits_to_mbps(bits):
    """Конвертирует биты в секунду в Мбит/с."""
    return round(bits / 1_000_000, 1)

def estimate_download_time(file_size_mb, download_speed_mbps):
    """Рассчитывает примерное время загрузки."""
    if download_speed_mbps <= 0:
        return "N/A"
    
    download_speed_mbs = download_speed_mbps / 8
    if download_speed_mbs <= 0:
        return "N/A"
    
    time_seconds = file_size_mb / download_speed_mbs
    
    if time_seconds < 1:
        return "< 1 сек"
    elif time_seconds < 60:
        return f"{int(time_seconds)} сек"
    elif time_seconds < 3600:
        minutes = int(time_seconds / 60)
        seconds = int(time_seconds % 60)
        if minutes > 0 and seconds > 0:
            return f"{minutes} мин {seconds} сек"
        elif minutes > 0:
            return f"{minutes} мин"
        else:
            return f"{seconds} сек"
    else:
        hours = int(time_seconds / 3600)
        minutes = int((time_seconds % 3600) / 60)
        return f"{hours}ч {minutes}м"

def get_moscow_time():
    """Получает текущее время по Москве (UTC+3)."""
    utc_now = datetime.datetime.utcnow()
    moscow_offset = datetime.timedelta(hours=3)
    moscow_time = utc_now + moscow_offset
    return moscow_time.strftime("%d.%m.%Y %H:%M:%S")

async def speedtest_command(api, message, args):
    """Выполняет тест скорости интернета."""
    try:
        if 'speedtest' in sys.modules:
            del sys.modules['speedtest']
        
        import speedtest
        
        if not hasattr(speedtest, 'Speedtest'):
            await api.edit(message, get_string("no_speedtest"))
            return
            
    except ImportError:
        await api.edit(message, get_string("no_speedtest"))
        return
    
    await api.edit(message, get_string("starting_test"))
    start_time = time.monotonic()
    
    try:
        st = await asyncio.to_thread(speedtest.Speedtest)
        
        await api.edit(message, get_string("selecting_server"))
        await asyncio.to_thread(st.get_best_server)
        
        await api.edit(message, get_string("testing_download"))
        await asyncio.to_thread(st.download)
        
        await api.edit(message, get_string("testing_upload"))
        await asyncio.to_thread(st.upload)
        
        await api.edit(message, get_string("finalizing_results"))
        
        end_time = time.monotonic()
        test_duration = end_time - start_time
        
        results = st.results.dict()
        
        download_speed = bits_to_mbps(results["download"])
        upload_speed = bits_to_mbps(results["upload"])
        ping = results["ping"]
        
        server = results["server"]
        server_name = server["name"]
        server_country = server["country"]
        server_sponsor = server["sponsor"]
        
        est_5mb = estimate_download_time(5, download_speed)
        est_100mb = estimate_download_time(100, download_speed)
        est_2gb = estimate_download_time(2 * 1024, download_speed)
        est_50gb = estimate_download_time(50 * 1024, download_speed)
        
        current_time_msk = get_moscow_time()
        
        result_text = get_string("results").format(
            download=download_speed,
            upload=upload_speed,
            ping=ping,
            server_name=server_name,
            server_country=server_country,
            server_sponsor=server_sponsor,
            est_5mb=est_5mb,
            est_100mb=est_100mb,
            est_2gb=est_2gb,
            est_50gb=est_50gb,
            duration=test_duration,
            time_msk=current_time_msk
        )
        
        await api.edit(message, result_text)
        
    except Exception as e:
        error_text = get_string("error").format(str(e))
        await api.edit(message, error_text)

async def register(api):
    """Регистрирует команды модуля."""
    api.register_command("speedtest", speedtest_command)
