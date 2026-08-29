# ©️ Maxli, 2026
# This file is a part of Maxli Userbot
# 🌐 https://github.com/Igroshka/Maxli
# Портировано с heroku/modules/heroku_settings.py (AGPLv3)

# meta developer: @Igroshka
# scope: maxli_only

from pymax import Message

from .. import loader, main, utils


@loader.tds
class MaxliSettingsMod(loader.Module):
    """Тонкая настройка ядра: вотчеры, белые списки, поведение диспетчера"""

    strings = {"name": "MaxliSettings"}

    # ------------------------------------------------------------------ #
    #                                watchers                             #
    # ------------------------------------------------------------------ #

    def _watcher_name(self, watcher) -> str:
        return watcher.__self__.__class__.__name__

    @loader.command()
    async def watcherscmd(self, message: Message):
        """Список активных вотчеров"""
        disabled = set(self._db.get(main.__name__, "disabled_watchers", []))
        watchers = self.allmodules.watchers

        if not watchers:
            await utils.answer(message, "👁 Вотчеров нет")
            return

        body = "\n".join(
            f"{'🚫' if (name := self._watcher_name(watcher)) in disabled else '✅'} {name}"
            for watcher in watchers
        )

        await utils.answer(
            message,
            utils.heading(f"👁 Вотчеры — {len(watchers)}") + "\n" + utils.quote(body),
        )

    @loader.command()
    async def watchercmd(self, message: Message):
        """<модуль> — включить или отключить вотчер модуля"""
        args = utils.get_args_raw(message).strip()

        if not args:
            await utils.answer(message, "❌ Укажи модуль")
            return

        name = self.allmodules.get_classname(args)
        disabled = set(self._db.get(main.__name__, "disabled_watchers", []))

        if name in disabled:
            disabled.discard(name)
            verdict = f"✅ Вотчер **{name}** включён"
        else:
            disabled.add(name)
            verdict = f"🚫 Вотчер **{name}** отключён"

        self._db.set(main.__name__, "disabled_watchers", list(disabled))
        await utils.answer(message, verdict)

    @loader.command()
    async def watcherblcmd(self, message: Message):
        """<модуль> [id чата] — не запускать вотчер модуля в этом чате"""
        args = utils.get_args(message)

        if not args:
            await utils.answer(message, "❌ Укажи модуль")
            return

        name = self.allmodules.get_classname(args[0])
        chat_id = (
            int(args[1])
            if len(args) > 1 and args[1].lstrip("-").isdigit()
            else utils.get_chat_id(message)
        )

        blacklist = self._db.get(main.__name__, "watcher_blacklist", {})
        chats = set(blacklist.get(name, []))

        if chat_id in chats:
            chats.discard(chat_id)
            verdict = f"✅ Вотчер **{name}** снова работает в {utils.mono(chat_id)}"
        else:
            chats.add(chat_id)
            verdict = f"🚫 Вотчер **{name}** отключён в {utils.mono(chat_id)}"

        blacklist[name] = list(chats)
        self._db.set(main.__name__, "watcher_blacklist", blacklist)
        await utils.answer(message, verdict)

    # ------------------------------------------------------------------ #
    #                               whitelist                             #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def whitelistcmd(self, message: Message):
        """[id чата] — реагировать только в этом чате (и других из белого списка)"""
        args = utils.get_args_raw(message).strip()
        chat_id = int(args) if args.lstrip("-").isdigit() else utils.get_chat_id(message)

        chats = set(self._db.get(main.__name__, "whitelist_chats", []))
        chats.add(chat_id)
        self._db.set(main.__name__, "whitelist_chats", list(chats))

        await utils.answer(message, f"✅ Чат {utils.mono(chat_id)} в белом списке")

    @loader.command()
    async def unwhitelistcmd(self, message: Message):
        """[id чата] — убрать чат из белого списка"""
        args = utils.get_args_raw(message).strip()
        chat_id = int(args) if args.lstrip("-").isdigit() else utils.get_chat_id(message)

        chats = set(self._db.get(main.__name__, "whitelist_chats", []))
        chats.discard(chat_id)
        self._db.set(main.__name__, "whitelist_chats", list(chats))

        await utils.answer(message, f"🚫 Чат {utils.mono(chat_id)} убран из белого списка")

    # ------------------------------------------------------------------ #
    #                                overview                             #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def settingscmd(self, message: Message):
        """Сводка настроек ядра"""
        get = lambda key, default: self._db.get(main.__name__, key, default)  # noqa: E731

        body = "\n".join(
            [
                f"⌨️ префикс: {self.get_prefix()}",
                f"🌐 язык: {self.tr.language}",
                f"🔗 алиасов: {len(self.allmodules.aliases)}",
                f"🧩 модулей: {len(self.allmodules.modules)} "
                f"(отключено {len(get('disabled_modules', []))})",
                f"👁 вотчеров: {len(self.allmodules.watchers)} "
                f"(отключено {len(get('disabled_watchers', []))})",
                f"🚫 чатов в чёрном списке: {len(get('blacklist_chats', []))}",
                f"🚫 пользователей в чёрном списке: {len(get('blacklist_users', []))}",
                f"✅ чатов в белом списке: {len(get('whitelist_chats', []))}",
                f"🛡 защита ядра: "
                f"{'выключена' if get('remove_core_protection', False) else 'включена'}",
            ]
        )

        await utils.answer(
            message,
            utils.heading("⚙️ Настройки ядра") + "\n" + utils.quote(body),
        )

    @loader.owner
    @loader.command()
    async def coreprotectioncmd(self, message: Message):
        """Включить или выключить защиту системных модулей от перезаписи"""
        current = self._db.get(main.__name__, "remove_core_protection", False)
        self._db.set(main.__name__, "remove_core_protection", not current)

        await utils.answer(
            message,
            "🛡 Защита ядра включена" if current else "⚠️ Защита ядра отключена",
        )

    # ------------------------------------------------------------------ #
    #                            service chats                           #
    # ------------------------------------------------------------------ #

    @loader.owner
    @loader.command()
    async def setlogchatcmd(self, message: Message):
        """[chat_id] — назначить текущий или указанный чат лог-чатом Maxli"""
        args = utils.get_args_raw(message).strip()
        chat_id = int(args) if args.lstrip("-").isdigit() else utils.get_chat_id(message)

        if not chat_id:
            await utils.answer(message, "❌ Не удалось определить ID чата")
            return

        self._db.set("main", "log_chat", chat_id)
        self._db.save()

        await utils.answer(message, f"🪵 Лог-чат назначен: {utils.mono(chat_id)}")
        with contextlib.suppress(Exception):
            await self._client.send_message(
                chat_id,
                f"🪐 **Этот чат назначен лог-чатом Maxli!**\n> ⏱ Время: {utils.get_uptime()}",
            )

    @loader.owner
    @loader.command()
    async def setbackupchatcmd(self, message: Message):
        """[chat_id] — назначить текущий или указанный чат чатом бэкапов Maxli"""
        args = utils.get_args_raw(message).strip()
        chat_id = int(args) if args.lstrip("-").isdigit() else utils.get_chat_id(message)

        if not chat_id:
            await utils.answer(message, "❌ Не удалось определить ID чата")
            return

        self._db.set("main", "backup_chat", chat_id)
        self._db.save()

        await utils.answer(message, f"🗃 Чат бэкапов назначен: {utils.mono(chat_id)}")
        with contextlib.suppress(Exception):
            await self._client.send_message(
                chat_id,
                f"🗃 **Этот чат назначен чатом бэкапов Maxli!**",
            )

    @loader.command()
    async def chatslistcmd(self, message: Message):
        """Список доступных чатов с их названиями и ID"""
        try:
            chats = await self._client.fetch_chats()
        except Exception:
            chats = getattr(self._client, "chats", []) or []

        if not chats:
            await utils.answer(message, "❌ Список чатов пуст")
            return

        lines = []
        for chat in chats:
            title = getattr(chat, "title", None) or getattr(chat, "name", "Без названия")
            lines.append(f"▫️ **{title}** — {utils.mono(chat.id)}")

        text = f"📋 **Список чатов ({len(chats)}):**\n" + utils.quote("\n".join(lines))
        await utils.answer(message, text)

    @loader.owner
    @loader.command()
    async def creategroupscmd(self, message: Message):
        """Принудительно создать сервисные группы Maxli Logs и Maxli Backups"""
        status_msg = await utils.answer(message, "🛠 **Создаю сервисные группы...**") or message

        log_id = await utils.create_service_group(self._client, "Maxli Logs")
        if log_id:
            self._db.set("main", "log_chat", log_id)

        backup_id = await utils.create_service_group(self._client, "Maxli Backups")
        if backup_id:
            self._db.set("main", "backup_chat", backup_id)

        self._db.save()

        res_text = (
            "🪐 **Результат создания групп:**\n"
            f"> 🪵 **Maxli Logs:** {utils.mono(log_id) if log_id else '❌ Ошибка'}\n"
            f"> 🗃 **Maxli Backups:** {utils.mono(backup_id) if backup_id else '❌ Ошибка'}"
        )
        await utils.answer(status_msg, res_text)
