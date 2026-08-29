# Maxli

Модульный юзербот для мессенджера **MAX**.

Архитектура повторяет [Heroku Userbot](https://github.com/coddrago/Heroku),
транспорт — [PyMax 2.3.1](https://github.com/MaxApiTeam/PyMax) (`maxapi-python`).

## Установка

```bash
git clone https://github.com/YouRooni/Maxli
cd Maxli
pip install -r requirements.txt
python -m maxli
```

При первом запуске Maxli спросит номер телефона и код из SMS. Сессия ляжет в
`sessions/maxli.db`, конфиг — в `config.json`, база — в `maxli-db.json`.

QR-логин через web-клиент:

```bash
python -m maxli --web
```

## Аргументы

| Аргумент | Описание |
|---|---|
| `--phone`, `-p` | Номер телефона |
| `--session` | Имя файла сессии (по умолчанию `maxli.db`) |
| `--proxy` | Прокси для подключения |
| `--web` | WebClient + QR-авторизация вместо SMS |
| `--log-level` | Уровень логов (`DEBUG`/`INFO`/`WARNING`) |
| `--no-modules` | Не загружать пользовательские модули |
| `--root` | Разрешить запуск от root |

## Системные модули и команды

### Ядро

| Модуль | Команды |
|---|---|
| **Help** | `.help [модуль]`, `.modinfo <модуль>` |
| **MaxliInfo** | `.info`, `.ping` |
| **Config** | `.config [модуль] [опция] [значение]`, `.resetcfg` |
| **Settings** | `.maxli`, `.installation`, `.setprefix`, `.aliases`, `.addalias`, `.delalias`, `.blacklist`, `.unblacklist`, `.blacklistuser`, `.unblacklistuser`, `.blacklists`, `.getuser`, `.togglemod`, `.togglecmd`, `.disabled`, `.clearmodule`, `.cleardb` |
| **MaxliSettings** | `.settings`, `.watchers`, `.watcher`, `.watcherbl`, `.whitelist`, `.unwhitelist`, `.coreprotection` |
| **MaxliSecurity** | `.security`, `.owneradd`, `.ownerrm`, `.ownerlist`, `.sudoadd`, `.sudorm`, `.supportadd`, `.supportrm`, `.newsgroup`, `.sgroups`, `.sgroup`, `.sgroupadd`, `.sgroupdel`, `.delsgroup`, `.tsec`, `.tsecrm`, `.tsecclr` |
| **Loader** | `.loadmod`, `.dlmod`, `.unloadmod`, `.reloadmod`, `.modsource`, `.ml`, `.mods`, `.repos`, `.addrepo`, `.delrepo`, `.clearmodules` |
| **Updater** | `.update`, `.restart`, `.ubstop`, `.source`, `.changelog` |
| **MaxliBackup** | `.backupdb`, `.restoredb`, `.backupmods`, `.backupall` |
| **Translations** | `.setlang`, `.dllangpack`, `.langpacks`, `.reloadlang` |
| **Presets** | `.presets`, `.loadpreset`, `.savepreset`, `.mypresets` |
| **Tester** | `.logs`, `.clearlogs`, `.loglevel`, `.debugmods`, `.suspend`, `.dump` |
| **Quickstart** | `.quickstart` |
| **Terminal** | `.terminal` (`.sh`), `.kill` |
| **Eval** | `.e`, `.db` |

### Возможности MAX

| Модуль | Команды |
|---|---|
| **Chats** | `.chats [запрос]` — список и поиск, `.chatinfo`, `.newgroup <название> [id...]`, `.joinchat <ссылка>`, `.previewchat <ссылка>`, `.leavechat`, `.delchat`, `.invite`, `.kick`, `.members`, `.joinreqs`, `.approve`, `.decline`, `.setgrname`, `.setgrdesc`, `.grsettings`, `.link`, `.relink` |
| **Users** | `.user` (`.whois`), `.searchphone <+7...>`, `.contacts [запрос]`, `.addcontact`, `.delcontact`, `.sessions`, `.killsessions` |
| **Account** | `.setname`, `.setbio`, `.setpfp`, `.folders`, `.newfolder`, `.delfolder`, `.check2fa`, `.set2fa`, `.del2fa` |
| **Messages** | `.history [n]`, `.id`, `.forward` (`.fwd`), `.copy`, `.pin`, `.delmsg`, `.read`, `.react`, `.unreact`, `.reactions` |

### Чего в MAX нет

Inline-ботов, inline-кнопок, форм и галерей в MAX не существует, поэтому
`inline_stuff`, `heroku_web` и весь inline-слой Heroku не портированы. Вместо
`@loader.inline_handler` и `@loader.callback_handler` используй обычные команды
и вотчеры.

## Написание модулей

```python
# meta developer: @username
# meta pic: https://example.com/pic.png
# requires: aiohttp
# min-maxli: 100

from maxli import loader, utils


@loader.tds
class ExampleMod(loader.Module):
    """Пример модуля"""

    strings = {"name": "Example"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "greeting",
                "Привет",
                lambda: "Текст приветствия",
                validator=loader.validators.String(),
            ),
        )

    async def client_ready(self):
        self.counter = self.pointer("counter", 0)

    @loader.command(alias="ex")
    async def examplecmd(self, message):
        """— поздороваться"""
        await utils.answer(message, self.config["greeting"])

    @loader.watcher("no_commands", "in")
    async def watcher(self, message):
        if "maxli" in (message.text or "").lower():
            await message.react("❤️")
```

### Разметка MAX

MAX понимает markdown, а не HTML. Кроме `**жирного**`, `_курсива_`,
`` `моно` `` и блоков ``` ``` ``` есть **заголовки** и **цитаты** —
в `utils` для них готовые хелперы:

```python
utils.heading("Заголовок")   # → # Заголовок
utils.quote("строка\nещё")   # → > строка\n> ещё
utils.mono("значение")       # → `значение`
utils.code_block(output)     # → блок кода с обрезкой по лимиту
utils.unmark(text)           # снимает маркеры разметки
```

⚠️ **Внутри цитаты и заголовка MAX не разбирает разметку.** `**жирный**`
в цитате останется звёздочками, поэтому содержимое цитаты прогоняй через
`utils.unmark()`, а акценты ставь в строке-заголовке над цитатой:

```python
await utils.answer(
    message,
    f"🧩 **{name}**\n" + utils.quote("команд: 5\nвотчеров: 1"),
)
```

Так устроен весь системный вывод: `.help` кладёт каждый модуль в свою цитату,
`.config` — каждую настройку, `.chats` — каждый чат.

### Что даёт базовый класс

- `self.client` — клиент PyMax
- `self.db` — база данных, `self.get()` / `self.set()` / `self.pointer()`
- `self.allmodules` — реестр модулей, `self.lookup("Имя")`
- `self.strings["key"]` — строки из langpack-а
- `self.config` — настройки модуля
- `self.get_prefix()` — текущий префикс
- `self.invoke("cmd", "args", message)` — вызов другой команды

### Хуки жизненного цикла

| Метод | Когда вызывается |
|---|---|
| `config_complete()` | Конфиг заполнен из БД |
| `client_ready()` | Клиент MAX готов |
| `on_dlmod()` | Первая загрузка через `.dlmod` |
| `on_unload()` | Выгрузка или перезагрузка |

### Декораторы

`@loader.command()`, `@loader.watcher()`, `@loader.raw_handler()`,
`@loader.loop(interval=...)`, `@loader.tag(...)`, `@loader.ratelimit`,
`@loader.owner`, `@loader.sudo`, `@loader.support`, `@loader.chat_admin`,
`@loader.pm`, `@loader.unrestricted`.

## Структура

```
maxli/
├── main.py          — сборка и запуск
├── loader.py        — реестр модулей, декораторы
├── types.py         — Module, ModuleConfig, ConfigValue
├── dispatcher.py    — разбор команд, вотчеры, ratelimit
├── security.py      — права доступа
├── database.py      — JSON-хранилище
├── translations.py  — Translator, Strings
├── validators.py    — валидаторы конфига
├── pointers.py      — самосохраняющиеся list/dict/set
├── utils.py         — утилиты
├── log.py           — логирование
├── _internal.py     — restart / update
├── langpacks/       — en.yml, ru.yml
└── modules/         — системные модули
```

## Лицензия

AGPLv3.
