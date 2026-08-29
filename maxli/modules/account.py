# ©️ Maxli, 2026
# This file is a part of Maxli Userbot
# 🌐 https://github.com/Igroshka/Maxli
# Аналога в Heroku нет — модуль построен на возможностях MAX

# meta developer: @Igroshka
# scope: maxli_only

from pymax import Message, Photo

from .. import loader, utils


@loader.tds
class AccountMod(loader.Module):
    """Свой профиль MAX: имя, описание, аватар, папки чатов, 2FA"""

    strings = {"name": "Account"}

    def _names(self) -> tuple[str, str | None]:
        """Текущие имя и фамилия из профиля."""
        me = self._client.me

        if me is None or not me.contact.names:
            return "", None

        name = me.contact.names[0]
        return (
            getattr(name, "first_name", None) or getattr(name, "name", "") or "",
            getattr(name, "last_name", None),
        )

    # ------------------------------------------------------------------ #
    #                                profile                              #
    # ------------------------------------------------------------------ #

    @loader.owner
    @loader.command()
    async def setnamecmd(self, message: Message):
        """<имя> [фамилия] — изменить имя профиля"""
        args = utils.get_args(message)

        if not args:
            first, last = self._names()
            await utils.answer(
                message,
                f"👤 Текущее имя: {utils.mono(' '.join(filter(None, (first, last))))}",
            )
            return

        first = args[0]
        last = " ".join(args[1:]) if len(args) > 1 else None

        try:
            await self._client.change_profile(first, last)
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        await utils.answer(
            message,
            f"✏️ Имя изменено на **{' '.join(filter(None, (first, last)))}**",
        )

    @loader.owner
    @loader.command(alias="setdesc")
    async def setbiocmd(self, message: Message):
        """<текст> — изменить описание профиля"""
        description = utils.get_args_raw(message).strip()
        first, last = self._names()

        if not first:
            await utils.answer(message, "❌ Профиль ещё не загружен")
            return

        try:
            await self._client.change_profile(first, last, description)
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        await utils.answer(
            message,
            "✏️ Описание обновлено" if description else "🧹 Описание очищено",
        )

    @loader.owner
    @loader.command(alias="setavatar")
    async def setpfpcmd(self, message: Message):
        """<путь или ссылка> — сменить аватар профиля"""
        source = utils.get_args_raw(message).strip()

        if not source:
            await utils.answer(message, "❌ Укажи путь к файлу или ссылку")
            return

        first, last = self._names()

        if not first:
            await utils.answer(message, "❌ Профиль ещё не загружен")
            return

        photo = (
            Photo(url=source)
            if source.startswith(("http://", "https://"))
            else Photo(path=source)
        )

        try:
            await self._client.change_profile(first, last, photo=photo)
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        await utils.answer(message, "🖼 Аватар обновлён")

    # ------------------------------------------------------------------ #
    #                                folders                              #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def folderscmd(self, message: Message):
        """Папки чатов"""
        try:
            folders = await self._client.get_folders()
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        items = getattr(folders, "folders", None) or []

        if not items:
            await utils.answer(message, "📂 Папок нет")
            return

        body = "\n".join(
            f"{utils.unmark(str(getattr(folder, 'title', '?')))} "
            f"({getattr(folder, 'id', '?')}) — чатов: "
            f"{len(getattr(folder, 'include', None) or [])}"
            for folder in items
        )

        await utils.answer(
            message,
            utils.heading(f"📂 Папки чатов — {len(items)}") + "\n" + utils.quote(body),
        )

    @loader.command()
    async def newfoldercmd(self, message: Message):
        """<название> [id чатов через пробел] — создать папку чатов"""
        args = utils.get_args(message)

        if not args:
            await utils.answer(message, "❌ Укажи название папки")
            return

        chat_ids = [int(token) for token in args if token.lstrip("-").isdigit()]
        title = " ".join(token for token in args if not token.lstrip("-").isdigit()).strip()

        if not title:
            await utils.answer(message, "❌ Название не может состоять из одних ID")
            return

        if not chat_ids:
            chat_ids = [utils.get_chat_id(message)]

        try:
            await self._client.create_folder(title, chat_ids)
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        await utils.answer(
            message,
            f"📂 Папка **{title}** создана, чатов: {len(chat_ids)}",
        )

    @loader.command()
    async def delfoldercmd(self, message: Message):
        """<id папки> — удалить папку чатов"""
        folder_id = utils.get_args_raw(message).strip()

        if not folder_id:
            await utils.answer(message, "❌ Укажи ID папки")
            return

        try:
            await self._client.delete_folder(folder_id)
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        await utils.answer(message, f"🗑 Папка {utils.mono(folder_id)} удалена")

    # ------------------------------------------------------------------ #
    #                                  2FA                                #
    # ------------------------------------------------------------------ #

    @loader.owner
    @loader.command()
    async def check2facmd(self, message: Message):
        """Проверить, включена ли двухфакторная аутентификация"""
        try:
            enabled = await self._client.check_2fa()
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        await utils.answer(message, "🔐 2FA включена" if enabled else "🔓 2FA выключена")

    @loader.owner
    @loader.command()
    async def set2facmd(self, message: Message):
        """<пароль> [подсказка] — включить двухфакторную аутентификацию

        Привязать email через юзербота нельзя: MAX подтверждает его кодом,
        который PyMax спрашивает через консольный `input()` — это намертво
        повесило бы юзербота. Привязывай почту в официальном клиенте.
        """
        args = utils.get_args(message)

        if not args:
            await utils.answer(message, "❌ Укажи пароль")
            return

        kwargs = {"hint": " ".join(args[1:])} if len(args) > 1 else {}

        try:
            await self._client.set_2fa(args[0], **kwargs)
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        await utils.answer(message, "🔐 2FA включена")

    @loader.owner
    @loader.command()
    async def del2facmd(self, message: Message):
        """<пароль> — отключить двухфакторную аутентификацию"""
        password = utils.get_args_raw(message).strip()

        if not password:
            await utils.answer(message, "❌ Укажи текущий пароль")
            return

        try:
            await self._client.remove_2fa(password)
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        await utils.answer(message, "🔓 2FA отключена")
