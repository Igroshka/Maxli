# ©️ Maxli, 2026
# This file is a part of Maxli Userbot
# 🌐 https://github.com/Igroshka/Maxli
# Аналога в Heroku нет — модуль построен на возможностях MAX

# meta developer: @Igroshka
# scope: maxli_only

import time

from pymax import Message
from pymax.types import User

from .. import loader, utils


@loader.tds
class UsersMod(loader.Module):
    """Пользователи MAX: профили, контакты, поиск по телефону, сессии"""

    strings = {"name": "Users"}

    @staticmethod
    def _render_user(user: User) -> str:
        lines = [f"🆔 {user.id}"]

        if user.link:
            lines.append(f"🔗 {user.link}")

        if user.phone:
            lines.append(f"📱 {user.phone}")

        if user.country:
            lines.append(f"🌍 {user.country}")

        if user.registration_time:
            registered = time.strftime(
                "%d.%m.%Y",
                time.localtime(user.registration_time / 1000),
            )
            lines.append(f"📅 регистрация: {registered}")

        text = (
            f"👤 **{utils.unmark(utils.get_display_name(user))}**\n"
            + utils.quote("\n".join(lines))
        )

        if user.description:
            text += "\n📝 **О себе**\n" + utils.quote(utils.unmark(user.description))

        return text

    @loader.command(alias="whois")
    async def usercmd(self, message: Message):
        """[id | ответом] — информация о пользователе"""
        args = utils.get_args_raw(message)
        user = await utils.get_target_user(message, args)

        if user is None and not args:
            me = self._client.me
            user = me.contact if me else None

        if user is None:
            await utils.answer(message, "❌ Пользователь не найден")
            return

        await utils.answer(message, self._render_user(user))

    @loader.command()
    async def searchphonecmd(self, message: Message):
        """<+79991234567> — найти пользователя по номеру телефона"""
        phone = utils.get_args_raw(message).strip()

        if not phone:
            await utils.answer(message, "❌ Укажи номер телефона")
            return

        try:
            user = await self._client.search_by_phone(phone)
        except Exception as e:
            await utils.answer(message, f"❌ Не найден: {utils.mono(e)}")
            return

        await utils.answer(message, self._render_user(user))

    # ------------------------------------------------------------------ #
    #                               contacts                              #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def contactscmd(self, message: Message):
        """[запрос] — список контактов или поиск по имени"""
        query = utils.get_args_raw(message).strip().lower()
        contacts = [user for user in (self._client.contacts or []) if user is not None]

        if query:
            contacts = [
                user
                for user in contacts
                if query in utils.get_display_name(user).lower()
            ]

        if not contacts:
            await utils.answer(message, "📇 Контактов не найдено")
            return

        text = utils.heading(f"📇 Контакты — {len(contacts)}") + "\n" + utils.quote(
            "\n".join(
                f"{utils.unmark(utils.get_display_name(user))} — {user.id}"
                for user in contacts[:100]
            )
        )

        await utils.answer(message, utils.smart_truncate(text))

    @loader.command()
    async def addcontactcmd(self, message: Message):
        """<id | ответом> — добавить пользователя в контакты"""
        user_id = await utils.get_target_id(message, utils.get_args_raw(message))

        if user_id is None:
            await utils.answer(message, "❌ Не понял, кого добавлять")
            return

        try:
            user = await self._client.add_contact(user_id)
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        await utils.answer(
            message,
            f"📇 **{utils.get_display_name(user)}** добавлен в контакты",
        )

    @loader.command()
    async def delcontactcmd(self, message: Message):
        """<id | ответом> — убрать пользователя из контактов"""
        user_id = await utils.get_target_id(message, utils.get_args_raw(message))

        if user_id is None:
            await utils.answer(message, "❌ Не понял, кого убирать")
            return

        try:
            await self._client.remove_contact(user_id)
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        await utils.answer(message, f"📇 {utils.mono(user_id)} убран из контактов")

    # ------------------------------------------------------------------ #
    #                                sessions                             #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def sessionscmd(self, message: Message):
        """Активные сессии аккаунта"""
        try:
            sessions = await self._client.get_sessions()
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось получить сессии: {utils.mono(e)}")
            return

        if not sessions:
            await utils.answer(message, "🔐 Активных сессий не найдено")
            return

        blocks = [utils.heading(f"🔐 Активные сессии — {len(sessions)}")]

        for session in sessions:
            title = (
                getattr(session, "device_name", None)
                or getattr(session, "platform", None)
                or "Неизвестное устройство"
            )
            current = " · 📍 текущая" if getattr(session, "current", False) else ""

            details = [
                f"{field}: {value}"
                for field in ("platform", "device_type", "app_version", "ip", "location")
                if (value := getattr(session, field, None))
            ]

            blocks.append(
                f"▫️ **{utils.unmark(str(title))}**{current}\n"
                + utils.quote("\n".join(details) or "нет данных")
            )

        await utils.answer(message, utils.smart_truncate("\n".join(blocks)))

    @loader.owner
    @loader.command()
    async def killsessionscmd(self, message: Message):
        """Закрыть все сессии, кроме текущей"""
        try:
            await self._client.close_all_sessions()
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        await utils.answer(message, "🔐 Все остальные сессии закрыты")
