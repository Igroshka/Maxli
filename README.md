# 🚀 Maxli UserBot - Установка и настройка

## 📋 Требования

- Python 3.8 или выше
- Git
- Интернет-соединение

## 🖥️ Windows

### Автоматическая установка

1. Скачайте и запустите `install_windows.bat`
2. Следуйте инструкциям на экране
3. Введите номер телефона и код подтверждения
4. Настройте автозапуск через Планировщик задач

### Ручная установка

```bash
# Клонируем репозиторий
git clone https://github.com/Igroshka/Maxli.git
cd Maxli

# Создаем виртуальное окружение
python -m venv venv

# Активируем venv
venv\Scripts\activate

# Устанавливаем зависимости
pip install -r requirements.txt

# Запускаем для авторизации
python main.py
```

## 🐧 Linux

### Автоматическая установка

```bash
# Делаем скрипт исполняемым
chmod +x install_linux.sh

# Запускаем установку
./install_linux.sh
```

### Ручная установка

```bash
# Клонируем репозиторий
git clone https://github.com/Igroshka/Maxli.git
cd Maxli

# Создаем виртуальное окружение
python3 -m venv venv

# Активируем venv
source venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt

# Запускаем для авторизации
python3 main.py
```

## 🔄 Автозапуск

### Windows

1. Откройте Планировщик задач
2. Создайте задачу
3. Укажите путь к `autostart.bat`
4. Настройте запуск при старте системы

### Linux

```bash
# Создаем systemd сервис
sudo cp maxli.service /etc/systemd/system/
sudo systemctl enable maxli
sudo systemctl start maxli
```

## 📁 Структура проекта
