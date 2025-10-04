<p align="center">
  <img src="https://github.com/Igroshka/Maxli/blob/main/logo.png?raw=true" alt="Maxli Logo" width="150" style="border-radius:50%;" />
</p>

<h1 align="center">Maxli — UserBot for Messenger "Max"</h1>

<p align="center">
  ⚡ Удобный и гибкий UserBot для мессенджера Max  
  <br>
  Сделан <a href="https://t.me/YouRooni">YouRooni</a>
</p>

---

## 🚀 О проекте
**Maxli** — это UserBot для мессенджера **Max**, который позволяет автоматизировать рутинные действия, расширять функционал клиента и настраивать удобные команды.  
Работает на Python, легко запускается на VDS или локально.

---

## ✨ Возможности
- 📩 Автоматизация чатов и команд
- 🔒 Поддержка личных и групповых чатов
- ⚙️ Простая настройка
- 🛠 Система модулей для кастомизации

---

## 📋 Требования

- Python 3.12 или выше
- Git
- Интернет-соединение

## 🖥️ Windows

### Автоматическая установка

1. Скачайте и запустите `install_windows.bat`
2. Следуйте инструкциям на экране
3. Введите номер телефона и код подтверждения
4. Настройте автозапуск через Планировщик задач

### Ручная установка (PowerShell)

```bash
git clone https://github.com/Igroshka/Maxli.git && cd Maxli && python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt && python main.py
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
git clone https://github.com/Igroshka/Maxli.git && cd Maxli && python3.12 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && python3.12 main.py
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

---

## 📁 Структура проекта

Maxli/
├── main.py              # Основной файл
├── core/                # Ядро бота
├── modules/             # Модули
├── pymax/              # Библиотека PyMax
├── requirements.txt     # Зависимости
├── install_windows.bat  # Установка для Windows
├── install_linux.sh     # Установка для Linux
└── README.md           # Документация

---

## 📜 Лицензия

Этот проект распространяется под лицензией **Apache License 2.0**.
Подробнее см. в [LICENSE](LICENSE).

---

<p align="center">
  Made with ❤️ by <a href="https://t.me/YouRooni">YouRooni</a>
</p>
