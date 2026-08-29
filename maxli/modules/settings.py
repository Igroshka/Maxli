# ©️ Maxli, 2026
# This file is a part of Maxli Userbot
# 🌐 https://github.com/Igroshka/Maxli
# Портировано с heroku/modules/settings.py (AGPLv3)

# meta developer: @Igroshka
# scope: maxli_only

import contextlib
import platform
import sys

from pymax import Message

from .. import loader, main, utils, version


@loader.tds
class CoreMod(loader.Module):
    """Базовые настройки: префикс, алиасы, чёрный список, управление модулями"""

    strings = {"name": "Settings"}

    # ------------------------------------------------------------------ #
    #                                 about                               #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def maxlicmd(self, message: Message):
        """О юзерботе и полезные ссылки"""
        await utils.answer(
            message,
            utils.heading(f"🌌 Maxli v{version.pretty()}")
            + "\n"
            + utils.quote(
                "\n".join(
                    [
                        "Модульный юзербот для MAX.",
                        "Архитектура — как у Heroku, транспорт — PyMax.",
                        "",
                        f"📦 {self.config['repo_url']}",
                        f"⌨️ префикс: {self.get_prefix()}",
                        f"🧩 модулей: {len(self.allmodules.modules)}",
                    ]
                )
            ),
        )

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "repo_url",
                "https://github.com/Igroshka/Maxli",
                lambda: "Ссылка на репозиторий в .maxli",
                validator=loader.validators.Link(),
            ),
        )

    @loader.command()
    async def installationcmd(self, message: Message):
        """Информация об окружении, в котором крутится юзербот"""
        import pymax

        await utils.answer(
            message,
            utils.heading("🖥 Установка")
            + "\n"
            + utils.quote(
                "\n".join(
                    [
                        f"путь: {utils.get_base_dir()}",
                        f"python: {platform.python_version()}",
                        f"интерпретатор: {sys.executable}",
                        f"pymax: {pymax.__version__}",
                        f"система: {platform.system()} {platform.release()}",
                        f"ветка: {version.branch}",
                    ]
                )
            ),
        )

    # ------------------------------------------------------------------ #
    #                                prefix                               #
    # ------------------------------------------------------------------ #

    @loader.command(alias="prefix")
    async def setprefixcmd(self, message: Message):
        """<префикс> — сменить префикс команд"""
        args = utils.get_args_raw(message).strip()

        if not args:
            await utils.answer(
                message,
                f"⌨️ Текущий префикс: {utils.mono(self.get_prefix())}",
            )
            return

        if len(args) > 5:
            await utils.answer(message, "❌ Префикс не может быть длиннее 5 символов")
            return

        old = self.get_prefix()
        self.allmodules.set_prefix(args)

        await utils.answer(
            message,
            f"⌨️ Префикс изменён на {utils.mono(args)}\n"
            f"Вернуть обратно: {utils.mono(f'{args}setprefix {old}')}",
        )

    # ------------------------------------------------------------------ #
    #                                aliases                              #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def aliasescmd(self, message: Message):
        """Список алиасов"""
        listing = "\n".join(
            f"{alias} → {cmd}"
            for alias, cmd in sorted(self.allmodules.aliases.items())
        )
        await utils.answer(
            message,
            "🔗 **Алиасы**\n" + utils.quote(listing or "пусто"),
        )

    @loader.command()
    async def addaliascmd(self, message: Message):
        """<алиас> <команда> — создать алиас"""
        args = utils.get_args(message)

        if len(args) < 2:
            await utils.answer(message, "❌ Нужно два аргумента: алиас и команда")
            return

        target = " ".join(args[1:])

        if not self.allmodules.add_alias(args[0], target):
            await utils.answer(message, f"❌ Команда {utils.mono(args[1])} не найдена")
            return

        await utils.answer(message, f"🔗 {utils.mono(args[0])} → {utils.mono(target)}")

    @loader.command()
    async def delaliascmd(self, message: Message):
        """<алиас> — удалить алиас"""
        args = utils.get_args_raw(message).strip()

        if not self.allmodules.remove_alias(args):
            await utils.answer(message, f"❌ Алиас {utils.mono(args)} не найден")
            return

        await utils.answer(message, f"🗑 Алиас {utils.mono(args)} удалён")

    # ------------------------------------------------------------------ #
    #                               blacklist                             #
    # ------------------------------------------------------------------ #

    def _toggle_list(self, key: str, value: int, add: bool) -> list:
        items = set(self._db.get(main.__name__, key, []))

        if add:
            items.add(value)
        else:
            items.discard(value)

        result = list(items)
        self._db.set(main.__name__, key, result)
        return result

    @loader.command()
    async def blacklistcmd(self, message: Message):
        """[id чата] — не реагировать на команды в этом чате"""
        args = utils.get_args_raw(message).strip()
        chat_id = int(args) if args.lstrip("-").isdigit() else utils.get_chat_id(message)

        self._toggle_list("blacklist_chats", chat_id, True)
        await utils.answer(message, f"🚫 Чат {utils.mono(chat_id)} в чёрном списке")

    @loader.command()
    async def unblacklistcmd(self, message: Message):
        """[id чата] — убрать чат из чёрного списка"""
        args = utils.get_args_raw(message).strip()
        chat_id = int(args) if args.lstrip("-").isdigit() else utils.get_chat_id(message)

        self._toggle_list("blacklist_chats", chat_id, False)
        await utils.answer(message, f"✅ Чат {utils.mono(chat_id)} убран из чёрного списка")

    @loader.command()
    async def blacklistusercmd(self, message: Message):
        """<id | ответом> — игнорировать команды пользователя"""
        user_id = await utils.get_target_id(message, utils.get_args_raw(message))

        if user_id is None:
            await utils.answer(message, "❌ Не понял, о ком речь")
            return

        self._toggle_list("blacklist_users", user_id, True)
        await utils.answer(message, f"🚫 Пользователь {utils.mono(user_id)} в чёрном списке")

    @loader.command()
    async def unblacklistusercmd(self, message: Message):
        """<id | ответом> — убрать пользователя из чёрного списка"""
        user_id = await utils.get_target_id(message, utils.get_args_raw(message))

        if user_id is None:
            await utils.answer(message, "❌ Не понял, о ком речь")
            return

        self._toggle_list("blacklist_users", user_id, False)
        await utils.answer(message, f"✅ Пользователь {utils.mono(user_id)} разблокирован")

    @loader.command()
    async def blacklistscmd(self, message: Message):
        """Показать чёрные списки"""
        chats = self._db.get(main.__name__, "blacklist_chats", [])
        users = self._db.get(main.__name__, "blacklist_users", [])
        whitelist = self._db.get(main.__name__, "whitelist_chats", [])

        def block(title: str, items: list) -> str:
            body = "\n".join(str(item) for item in items) or "пусто"
            return f"{title}\n{utils.quote(body)}"

        await utils.answer(
            message,
            "\n".join(
                [
                    block("🚫 **Чаты**", chats),
                    block("🚫 **Пользователи**", users),
                    block("✅ **Белый список чатов**", whitelist),
                ]
            ),
        )

    @loader.command()
    async def getusercmd(self, message: Message):
        """Показать ID автора сообщения, на которое отвечаешь"""
        reply = await utils.get_reply(message)

        if reply is None:
            await utils.answer(
                message,
                utils.quote(
                    f"👤 твой ID: {utils.get_me_id()}\n"
                    f"💬 ID чата: {utils.get_chat_id(message)}"
                ),
            )
            return

        user = None
        if reply.sender is not None:
            with contextlib.suppress(Exception):
                user = await self._client.get_user(reply.sender)

        await utils.answer(
            message,
            utils.quote(
                f"👤 {utils.unmark(utils.get_display_name(user))}\n🆔 {reply.sender}"
            ),
        )

    # ------------------------------------------------------------------ #
    #                          modules & commands                         #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def togglemodcmd(self, message: Message):
        """<модуль> — включить или отключить модуль"""
        args = utils.get_args_raw(message)
        module = self.lookup(args) if args else None

        if not module:
            await utils.answer(message, f"❌ Модуль {utils.mono(args)} не найден")
            return

        name = module.__class__.__name__
        disabled = set(self._db.get(main.__name__, "disabled_modules", []))

        if name in disabled:
            disabled.discard(name)
            verdict = f"✅ Модуль **{name}** включён"
        else:
            disabled.add(name)
            verdict = f"🚫 Модуль **{name}** отключён"

        self._db.set(main.__name__, "disabled_modules", list(disabled))
        await utils.answer(message, verdict)

    @loader.command()
    async def togglecmdcmd(self, message: Message):
        """<модуль> <команда> — включить или отключить одну команду"""
        args = utils.get_args(message)

        if len(args) < 2:
            await utils.answer(message, "❌ Нужны модуль и команда")
            return

        module = self.lookup(args[0])

        if not module:
            await utils.answer(message, f"❌ Модуль {utils.mono(args[0])} не найден")
            return

        name = module.__class__.__name__
        command = args[1].lower()

        if command not in module.commands:
            await utils.answer(message, f"❌ У модуля нет команды {utils.mono(command)}")
            return

        disabled = self._db.get(main.__name__, "disabled_commands", {})
        bucket = {item.lower() for item in disabled.get(name, [])}

        if command in bucket:
            bucket.discard(command)
            verdict = f"✅ Команда {utils.mono(command)} включена"
        else:
            bucket.add(command)
            verdict = f"🚫 Команда {utils.mono(command)} отключена"

        disabled[name] = list(bucket)
        self._db.set(main.__name__, "disabled_commands", disabled)
        await utils.answer(message, verdict)

    @loader.command()
    async def disabledcmd(self, message: Message):
        """Список отключённых модулей и команд"""
        modules = self._db.get(main.__name__, "disabled_modules", [])
        commands = self._db.get(main.__name__, "disabled_commands", {})

        pairs = [f"{mod}.{cmd}" for mod, cmds in commands.items() for cmd in cmds]

        text = (
            "🚫 **Отключённые модули**\n"
            + utils.quote("\n".join(modules) or "пусто")
            + "\n🚫 **Отключённые команды**\n"
            + utils.quote("\n".join(pairs) or "пусто")
        )

        await utils.answer(message, text)

    # ------------------------------------------------------------------ #
    #                                database                             #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def clearmodulecmd(self, message: Message):
        """<модуль> — стереть данные модуля из базы"""
        args = utils.get_args_raw(message)
        name = self.allmodules.get_classname(args)

        if name not in self._db:
            await utils.answer(message, f"❌ У модуля {utils.mono(name)} нет данных в БД")
            return

        del self._db[name]
        await utils.answer(message, f"🧹 Данные модуля **{name}** удалены")

    @loader.command()
    async def cleardbcmd(self, message: Message):
        """Полностью очистить базу данных (необратимо)"""
        self._db.clear()
        self._db.save()
        await utils.answer(
            message,
            "🧹 База очищена. Перезапусти юзербота: " + utils.mono(f"{self.get_prefix()}restart"),
        )
