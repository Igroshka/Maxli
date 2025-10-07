<p align="center">
  <img src="https://github.com/Igroshka/Maxli/blob/main/logo.png?raw=true" alt="Maxli Logo" width="150" style="border-radius:50% !important;" />
</p>

<h1 align="center">Maxli — UserBot для мессенджера "Max"</h1>

<p align="center">
  <a href="https://github.com/Igroshka/Maxli/stargazers"><img src="https://img.shields.io/github/stars/Igroshka/Maxli?style=for-the-badge&logo=github&color=FFC107" alt="Stars"></a>
  <a href="https://github.com/Igroshka/Maxli/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Igroshka/Maxli?style=for-the-badge&color=8BC34A" alt="License"></a>
  <a href="https://UserbotMax.t.me"><img src="https://img.shields.io/badge/Telegram-Новости-blue?style=for-the-badge&logo=telegram" alt="Telegram Channel"></a>
</p>

<p align="center">
  ⚡️ Первый и лучший UserBot для мессенджера <b>Max</b> с удобной и гибкой системой модулей.  
  <br>
  Создан <a href="https://t.me/YouRooni">YouRooni</a> с ❤️
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/Igroshka/Maxli/refs/heads/main/banner1.png" alt="Maxli Banner" width="100%" style="border-radius:5% !important;" />
</p>

---

## 🚀 О проекте

Maxli — это новаторский UserBot для мессенджера Max, разработанный для автоматизации рутинных действий и расширения стандартного функционала. Это первый в своем роде юзербот для данной платформы, предлагающий пользователям непревзойденные возможности.

Проект работает на Python и основан на доработанной и постоянно улучшаемой версии библиотеки "pymax". Благодаря своей архитектуре, Maxli легко запускается как на VDS/VPS, так и на локальной машине, а его система плагинов обеспечивает простую кастомизацию и расширение. Принцип работы схож с облачными платформами вроде Heroku, что делает его мощным и удобным инструментом.

---

## ✨ Ключевые возможности

- Автоматизация: Настраивайте автоматические ответы, команды и сценарии.
- Гибкая система модулей: Расширяйте функционал с помощью готовых плагинов или создавайте свои.
- Поддержка чатов: Стабильная работа в личных сообщениях и групповых чатах.
- Простая установка: Готовые скрипты для быстрой установки на Windows и Linux.
- Удобная настройка: Конфигурация через простые и понятные файлы.

---

## 📢 Новости и поддержка

Все актуальные новости, обновления и полезную информацию о проекте вы найдете в нашем официальном Telegram-канале.

➡️ Подписаться на канал: [UserbotMax.t.me](https://UserbotMax.t.me)

---

## 🛠️ Установка

Для начала работы убедитесь, что у вас установлены Python 3.12+ и Git.

<details>
<summary><b>🖥️ Установка на Windows</b></summary>

### Автоматическая установка

1.  Скачайте и запустите файл `install_windows.bat` из репозитория.
2.  Следуйте инструкциям в консоли.
3.  Введите ваш номер телефона и код подтверждения для авторизации.
4.  Настройте автозапуск с помощью `autostart.bat` через Планировщик задач.

### Ручная установка (PowerShell)

```bash
git clone https://github.com/Igroshka/Maxli.git
cd Maxli
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

</details>

<details>
<summary><b>🐧 Установка на Linux</b></summary>

### Автоматическая установка

```bash
# Даем права на исполнение
chmod +x install_linux.sh

# Запускаем скрипт
./install_linux.sh
```

### Ручная установка

```bash
git clone https://github.com/Igroshka/Maxli.git && cd Maxli && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && python3 main.py
```

</details>

<br>

> Важно: После установки рекомендуется настроить автозапуск для стабильной работы юзербота. Инструкции находятся в разделе `🔄 Автозапуск`.

---

## 🔄 Автозапуск

<details>
<summary><b>Настройка автозапуска на Windows</b></summary>

1.  Откройте Планировщик задач (`taskschd.msc`).
2.  Нажмите "Создать задачу...".
3.  На вкладке "Триггеры" создайте новый триггер с параметром "При входе в систему".
4.  На вкладке "Действия" выберите "Запуск программы" и укажите путь к файлу `autostart.bat` в папке проекта.
5.  Сохраните задачу.

</details>

<details>
<summary><b>Настройка автозапуска на Linux (через systemd)</b></summary>

1.  Скопируйте сервис-файл в системную директорию:
    ```bash
    sudo cp maxli.service /etc/systemd/system/
    ```
2.  Включите автозапуск сервиса:
    ```bash
    sudo systemctl enable maxli
    ```
3.  Запустите сервис:
    ```bash
    sudo systemctl start maxli
    ```

</details>

---

## 📁 Структура проекта

```
Maxli/
├── main.py              # ▶️ Основной файл для запуска
├── core/                # ⚙️ Ядро и ключевые компоненты
├── modules/             # 🧩 Папка с вашими модулями и плагинами
├── pymax/               # 📚 Доработанная библиотека PyMax
├── requirements.txt     # 📦 Список зависимостей
├── install_windows.bat  #  automatisierte Installation für Windows
├── install_linux.sh     # 🐧 Скрипт установки для Linux
└── README.md            # 📄 Эта документация
```

---

## 📜 Лицензия

Этот проект распространяется под лицензией Apache License 2.0. Подробнее см. в файле [LICENSE](LICENSE).
