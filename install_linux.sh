#!/bin/bash

echo "========================================"
echo "   Maxli UserBot - Установка для Linux"
echo "========================================"
echo

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден! Установите Python 3.8+"
    exit 1
fi

echo "✅ Python3 найден"
echo

# Создаем папку для бота
if [ ! -d "Maxli" ]; then
    echo "📁 Создаем папку Maxli..."
    mkdir Maxli
fi

cd Maxli

# Клонируем репозиторий
echo "📥 Скачиваем Maxli UserBot..."
git clone https://github.com/Igroshka/Maxli.git .
if [ $? -ne 0 ]; then
    echo "❌ Ошибка скачивания! Проверьте интернет-соединение"
    exit 1
fi

echo "✅ Код скачан"
echo

# Создаем виртуальное окружение
echo "🐍 Создаем виртуальное окружение..."
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "❌ Ошибка создания venv"
    exit 1
fi

echo "✅ Виртуальное окружение создано"
echo

# Активируем venv и устанавливаем зависимости
echo "📦 Устанавливаем зависимости..."
source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "❌ Ошибка установки зависимостей"
    exit 1
fi

echo "✅ Зависимости установлены"
echo

# Запускаем для авторизации
echo "🔐 Запускаем бота для авторизации..."
echo "Введите номер телефона и код подтверждения"
echo "После успешной авторизации закройте бота (Ctrl+C)"
echo
read -p "Нажмите Enter для продолжения..."

source venv/bin/activate && python3 main.py

echo
echo "✅ Авторизация завершена!"
echo

# Создаем скрипт запуска
echo "📝 Создаем скрипт запуска..."
cat > start_bot.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python3 main.py
EOF

chmod +x start_bot.sh

echo "✅ Скрипт start_bot.sh создан"
echo

# Создаем systemd сервис
echo "📋 Создаем systemd сервис..."
cat > maxli.service << EOF
[Unit]
Description=Maxli UserBot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Сервис maxli.service создан"
echo

echo "========================================"
echo "          Установка завершена!"
echo "========================================"
echo
echo "📁 Папка бота: $(pwd)"
echo "🚀 Запуск: ./start_bot.sh"
echo "🔄 Автозапуск: sudo systemctl enable maxli && sudo systemctl start maxli"
echo
echo "Для настройки автозапуска:"
echo "1. sudo cp maxli.service /etc/systemd/system/"
echo "2. sudo systemctl enable maxli"
echo "3. sudo systemctl start maxli"
echo
