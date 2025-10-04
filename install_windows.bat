@echo off
echo ========================================
echo    Maxli UserBot - Установка для Windows
echo ========================================
echo.

REM Проверяем наличие Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не найден! Установите Python 3.8+ с https://python.org
    pause
    exit /b 1
)

echo ✅ Python найден
echo.

REM Создаем папку для бота
if not exist "Maxli" (
    echo 📁 Создаем папку Maxli...
    mkdir Maxli
)

cd Maxli

REM Клонируем репозиторий
echo 📥 Скачиваем Maxli UserBot...
git clone https://github.com/Igroshka/Maxli.git .
if errorlevel 1 (
    echo ❌ Ошибка скачивания! Проверьте интернет-соединение
    pause
    exit /b 1
)

echo ✅ Код скачан
echo.

REM Создаем виртуальное окружение
echo 🐍 Создаем виртуальное окружение...
python -m venv venv
if errorlevel 1 (
    echo ❌ Ошибка создания venv
    pause
    exit /b 1
)

echo ✅ Виртуальное окружение создано
echo.

REM Активируем venv и устанавливаем зависимости
echo 📦 Устанавливаем зависимости...
call venv\Scripts\activate.bat && pip install --upgrade pip && pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ Ошибка установки зависимостей
    pause
    exit /b 1
)

echo ✅ Зависимости установлены
echo.

REM Запускаем для авторизации
echo 🔐 Запускаем бота для авторизации...
echo Введите номер телефона и код подтверждения
echo После успешной авторизации закройте бота (Ctrl+C)
echo.
pause

call venv\Scripts\activate.bat && python main.py

echo.
echo ✅ Авторизация завершена!
echo.

REM Создаем скрипт запуска
echo 📝 Создаем скрипт запуска...
echo @echo off > start_bot.bat
echo cd /d "%~dp0" >> start_bot.bat
echo call venv\Scripts\activate.bat >> start_bot.bat
echo python main.py >> start_bot.bat
echo pause >> start_bot.bat

echo ✅ Скрипт start_bot.bat создан
echo.

REM Создаем скрипт для автозапуска
echo 📋 Создаем скрипт для автозапуска...
echo @echo off > autostart.bat
echo cd /d "%~dp0" >> autostart.bat
echo call venv\Scripts\activate.bat >> autostart.bat
echo python main.py >> autostart.bat

echo ✅ Скрипт autostart.bat создан
echo.

echo ========================================
echo           Установка завершена!
echo ========================================
echo.
echo 📁 Папка бота: %cd%
echo 🚀 Запуск: start_bot.bat
echo 🔄 Автозапуск: autostart.bat
echo.
echo Для настройки автозапуска:
echo 1. Откройте Планировщик задач Windows
echo 2. Создайте задачу
echo 3. Укажите путь к autostart.bat
echo 4. Настройте запуск при старте системы
echo.
pause
