# ©️ Maxli, 2026
# This file is a part of Maxli Userbot
# 🌐 https://github.com/Igroshka/Maxli
# Аналога в Heroku нет — модуль построен на возможностях MAX

# meta developer: @Igroshka
# scope: maxli_only

import time

from pymax import Message
from pymax.types import Chat

from .. import loader, utils


@loader.tds
class ChatsMod(loader.Module):
    """Чаты, группы и каналы MAX: поиск, создание, участники, ссылки"""

    strings = {"name": "Chats"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "list_limit",
                30,
                lambda: "Сколько чатов показывать в .chats",
                validator=loader.validators.Integer(minimum=5, maximum=200),
            ),
            loader.ConfigValue(
                "clean_period",
                0,
                lambda: "Сколько секунд сообщений удалять при кике (0 — не удалять)",
                validator=loader.validators.Integer(minimum=0, maximum=604800),
            ),
        )

    # ------------------------------------------------------------------ #
    #                                helpers                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _kind(chat: Chat) -> str:
        # ChatType — обычный Enum, поэтому str() даёт "ChatType.CHAT"
        key = str(getattr(chat, "type", "")).upper().rsplit(".", 1)[-1]

        return {
            "DIALOG": "💬 диалог",
            "CHAT": "👥 группа",
            "CHANNEL": "📢 канал",
        }.get(key, "❔ чат")

    @staticmethod
    def _title(chat: Chat) -> str:
        return chat.title or f"Без названия ({chat.id})"

    async def _all_chats(self) -> list[Chat]:
        """Чаты из sync-состояния, при необходимости догруженные с сервера."""
        chats = list(self._client.chats or [])

        if not chats:
            try:
                chats = await self._client.fetch_chats()
            except Exception:
                chats = []

        return chats

    async def _resolve_chat(self, message: Message, args: str) -> Chat | None:
        """Чат из аргумента (ID или часть названия) либо текущий."""
        args = (args or "").strip()

        if not args:
            return await utils.get_chat(message)

        if args.lstrip("-").isdigit():
            try:
                return await self._client.get_chat(int(args))
            except Exception:
                return None

        needle = args.lower()
        for chat in await self._all_chats():
            if needle in (chat.title or "").lower():
                return chat

        return None

    # ------------------------------------------------------------------ #
    #                             list & search                           #
    # ------------------------------------------------------------------ #

    @loader.command(alias="dialogs")
    async def chatscmd(self, message: Message):
        """[запрос] — список чатов или поиск по названию"""
        query = utils.get_args_raw(message).strip().lower()
        chats = await self._all_chats()

        if query:
            chats = [chat for chat in chats if query in (chat.title or "").lower()]

        if not chats:
            await utils.answer(
                message,
                f"🔍 Ничего не нашёл по запросу {utils.mono(query)}" if query else "🔍 Чатов нет",
            )
            return

        chats.sort(key=lambda c: getattr(c, "last_event_time", 0) or 0, reverse=True)
        shown = chats[: self.config["list_limit"]]

        blocks = [
            utils.heading(f"💬 Чаты — {len(shown)} из {len(chats)}"),
        ]

        if query:
            blocks.append(f"_по запросу_ {utils.mono(query)}")

        for chat in shown:
            unread = f" · 🔴 {chat.new_messages}" if getattr(chat, "new_messages", 0) else ""
            blocks.append(
                f"{self._kind(chat)} **{utils.unmark(self._title(chat))}**\n"
                + utils.quote(f"{chat.id}{unread}")
            )

        await utils.answer(message, utils.smart_truncate("\n".join(blocks)))

    @loader.command(alias="chat")
    async def chatinfocmd(self, message: Message):
        """[id | название] — информация о чате"""
        chat = await self._resolve_chat(message, utils.get_args_raw(message))

        if chat is None:
            await utils.answer(message, "❌ Чат не найден")
            return

        lines = [
            f"🆔 {chat.id}",
            f"👥 участников: {getattr(chat, 'participants_count', 0)}",
        ]

        if getattr(chat, "owner", None):
            lines.append(f"👑 владелец: {chat.owner}")

        if getattr(chat, "access", None):
            lines.append(f"🔐 доступ: {str(chat.access).rsplit('.', 1)[-1]}")

        if getattr(chat, "created", None):
            created = time.strftime("%d.%m.%Y", time.localtime(chat.created / 1000))
            lines.append(f"📅 создан: {created}")

        if getattr(chat, "link", None):
            lines.append(f"🔗 {chat.link}")

        text = (
            f"{self._kind(chat)} **{utils.unmark(self._title(chat))}**\n"
            + utils.quote("\n".join(lines))
        )

        if getattr(chat, "description", None):
            text += "\n📝 **Описание**\n" + utils.quote(utils.unmark(chat.description))

        await utils.answer(message, text)

    # ------------------------------------------------------------------ #
    #                                creation                             #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def newgroupcmd(self, message: Message):
        """<название> [| id участников] — создать группу

        ID участников отделяются вертикальной чертой, иначе цифры в названии
        были бы приняты за ID: `.newgroup Отчёт 2026 | 123456 789012`
        """
        raw = utils.get_args_raw(message).strip()

        if not raw:
            await utils.answer(message, "❌ Укажи название группы")
            return

        title, _, tail = raw.partition("|")
        title = title.strip()

        participants = [
            int(token) for token in tail.split() if token.lstrip("-").isdigit()
        ]

        if not title:
            await utils.answer(message, "❌ Название не может быть пустым")
            return

        try:
            result = await self._client.create_group(title, participants or None)
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось создать группу: {utils.mono(e)}")
            return

        if not result:
            await utils.answer(message, "❌ Сервер не вернул созданный чат")
            return

        chat, _ = result
        await utils.answer(
            message,
            f"✅ Группа **{title}** создана\n🆔 {utils.mono(chat.id)}"
            + (f"\n👥 Добавлено участников: {len(participants)}" if participants else ""),
        )

    @loader.command()
    async def joinchatcmd(self, message: Message):
        """<ссылка> — вступить в группу по приглашению"""
        link = utils.get_args_raw(message).strip()

        if not link:
            await utils.answer(message, "❌ Укажи ссылку-приглашение")
            return

        try:
            chat = await self._client.join_group(link)
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось вступить: {utils.mono(e)}")
            return

        await utils.answer(
            message,
            f"✅ Вступил в **{self._title(chat)}**\n🆔 {utils.mono(chat.id)}",
        )

    @loader.command()
    async def previewchatcmd(self, message: Message):
        """<ссылка> — посмотреть группу по ссылке, не вступая"""
        link = utils.get_args_raw(message).strip()

        try:
            chat = await self._client.resolve_group_by_link(link)
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        if chat is None:
            await utils.answer(message, "❌ Сервер не вернул данные чата")
            return

        await utils.answer(
            message,
            f"{self._kind(chat)} **{self._title(chat)}**\n"
            f"🆔 {utils.mono(chat.id)}\n"
            f"👥 Участников: {getattr(chat, 'participants_count', 0)}\n"
            + (f"\n📝 {chat.description}" if getattr(chat, "description", None) else ""),
        )

    @loader.command()
    async def leavechatcmd(self, message: Message):
        """[id | название] — выйти из группы или канала"""
        chat = await self._resolve_chat(message, utils.get_args_raw(message))

        if chat is None:
            await utils.answer(message, "❌ Чат не найден")
            return

        title = self._title(chat)

        try:
            if utils.is_channel(chat):
                await self._client.leave_channel(chat.id)
            else:
                await self._client.leave_group(chat.id)
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось выйти: {utils.mono(e)}")
            return

        utils.drop_chat_cache(chat.id)
        await utils.answer(message, f"👋 Вышел из **{title}**")

    @loader.command()
    async def delchatcmd(self, message: Message):
        """[id | название] — удалить чат у себя"""
        chat = await self._resolve_chat(message, utils.get_args_raw(message))

        if chat is None:
            await utils.answer(message, "❌ Чат не найден")
            return

        title = self._title(chat)

        try:
            await self._client.delete_chat(
                chat.id,
                last_event_time=getattr(chat, "last_event_time", None),
                for_all=False,
            )
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось удалить: {utils.mono(e)}")
            return

        utils.drop_chat_cache(chat.id)
        await utils.answer(message, f"🗑 Чат **{title}** удалён")

    # ------------------------------------------------------------------ #
    #                               members                               #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def invitecmd(self, message: Message):
        """<id пользователя...> — пригласить людей в текущий чат"""
        args = utils.get_args(message)
        user_ids = [int(token) for token in args if token.lstrip("-").isdigit()]

        if not user_ids:
            target = await utils.get_target_id(message)
            if target is None:
                await utils.answer(message, "❌ Укажи ID или ответь на сообщение")
                return
            user_ids = [target]

        chat_id = utils.get_chat_id(message)
        chat = await utils.get_chat(message)

        try:
            if chat is not None and utils.is_channel(chat):
                await self._client.invite_users_to_channel(chat_id, user_ids)
            else:
                await self._client.invite_users_to_group(chat_id, user_ids)
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось пригласить: {utils.mono(e)}")
            return

        await utils.answer(
            message,
            f"✅ Приглашено: {utils.mono(', '.join(map(str, user_ids)))}",
        )

    @loader.command()
    async def kickcmd(self, message: Message):
        """<id | ответом> — убрать пользователя из текущего чата"""
        args = utils.get_args(message)
        user_ids = [int(token) for token in args if token.lstrip("-").isdigit()]

        if not user_ids:
            target = await utils.get_target_id(message)
            if target is None:
                await utils.answer(message, "❌ Укажи ID или ответь на сообщение")
                return
            user_ids = [target]

        try:
            await self._client.remove_users_from_group(
                utils.get_chat_id(message),
                user_ids,
                self.config["clean_period"],
            )
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        await utils.answer(
            message,
            f"👋 Удалено: {utils.mono(', '.join(map(str, user_ids)))}",
        )

    @loader.command()
    async def memberscmd(self, message: Message):
        """[id | название] — участники чата"""
        chat = await self._resolve_chat(message, utils.get_args_raw(message))

        if chat is None:
            await utils.answer(message, "❌ Чат не найден")
            return

        participants = getattr(chat, "participants", None) or {}

        if not participants:
            await utils.answer(message, "👥 Список участников недоступен")
            return

        ids = list(participants)[:100]

        try:
            users = await self._client.get_users(ids)
        except Exception:
            users = []

        names = {user.id: utils.get_display_name(user) for user in users}

        text = utils.heading(
            f"👥 {utils.unmark(self._title(chat))} — {len(participants)} участников"
        ) + "\n" + utils.quote(
            "\n".join(
                f"{utils.unmark(names.get(uid, 'Неизвестный'))} — {uid}" for uid in ids
            )
        )

        await utils.answer(message, utils.smart_truncate(text))

    # ------------------------------------------------------------------ #
    #                             join requests                           #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def joinreqscmd(self, message: Message):
        """[id | название] — заявки на вступление"""
        chat = await self._resolve_chat(message, utils.get_args_raw(message))

        if chat is None:
            await utils.answer(message, "❌ Чат не найден")
            return

        try:
            requests = await self._client.get_join_requests(chat.id)
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось получить заявки: {utils.mono(e)}")
            return

        if not requests:
            await utils.answer(message, "📥 Заявок нет")
            return

        text = utils.heading(
            f"📥 Заявки в {utils.unmark(self._title(chat))} — {len(requests)}"
        ) + "\n" + utils.quote(
            "\n".join(
                f"{utils.unmark(utils.get_display_name(member.contact))} "
                f"— {member.contact.id}"
                for member in requests
            )
        )

        await utils.answer(message, text)

    async def _pending_ids(self, chat_id: int) -> list[int]:
        """ID всех, кто ждёт подтверждения заявки."""
        requests = await self._client.get_join_requests(chat_id)
        return [member.contact.id for member in requests]

    @loader.command()
    async def approvecmd(self, message: Message):
        """<id | all> — принять заявку на вступление в текущий чат"""
        args = utils.get_args_raw(message).strip().lower()
        chat_id = utils.get_chat_id(message)

        if not args or (args not in {"all", "всех", "*"} and not args.isdigit()):
            await utils.answer(message, "❌ Укажи ID пользователя или all")
            return

        try:
            if args in {"all", "всех", "*"}:
                ids = await self._pending_ids(chat_id)

                if not ids:
                    await utils.answer(message, "📥 Заявок нет")
                    return

                await self._client.confirm_join_requests(chat_id, ids)
                await utils.answer(message, f"✅ Принято заявок: {len(ids)}")
                return

            await self._client.confirm_join_request(chat_id, int(args))
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        await utils.answer(message, f"✅ Заявка {utils.mono(args)} принята")

    @loader.command()
    async def declinecmd(self, message: Message):
        """<id | all> — отклонить заявку на вступление в текущий чат"""
        args = utils.get_args_raw(message).strip().lower()
        chat_id = utils.get_chat_id(message)

        if not args or (args not in {"all", "всех", "*"} and not args.isdigit()):
            await utils.answer(message, "❌ Укажи ID пользователя или all")
            return

        try:
            if args in {"all", "всех", "*"}:
                ids = await self._pending_ids(chat_id)

                if not ids:
                    await utils.answer(message, "📥 Заявок нет")
                    return

                await self._client.decline_join_requests(chat_id, ids)
                await utils.answer(message, f"🚫 Отклонено заявок: {len(ids)}")
                return

            await self._client.decline_join_request(chat_id, int(args))
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        await utils.answer(message, f"🚫 Заявка {utils.mono(args)} отклонена")

    # ------------------------------------------------------------------ #
    #                              group setup                            #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def setgrnamecmd(self, message: Message):
        """<название> — переименовать текущую группу"""
        title = utils.get_args_raw(message).strip()

        if not title:
            await utils.answer(message, "❌ Укажи новое название")
            return

        try:
            await self._client.change_group_profile(utils.get_chat_id(message), title)
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        utils.drop_chat_cache(utils.get_chat_id(message))
        await utils.answer(message, f"✏️ Название изменено на **{title}**")

    @loader.command()
    async def setgrdesccmd(self, message: Message):
        """<описание> — изменить описание текущей группы"""
        description = utils.get_args_raw(message).strip()
        chat = await utils.get_chat(message)

        if chat is None:
            await utils.answer(message, "❌ Не удалось получить текущий чат")
            return

        try:
            await self._client.change_group_profile(
                utils.get_chat_id(message),
                chat.title,
                description,
            )
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        utils.drop_chat_cache(utils.get_chat_id(message))
        await utils.answer(message, "✏️ Описание обновлено")

    @loader.command()
    async def grsettingscmd(self, message: Message):
        """<настройка> <on|off> — настройки текущей группы

        Настройки: pin, icon, add, call, link
        """
        args = utils.get_args(message)

        mapping = {
            "pin": "all_can_pin_message",
            "icon": "only_owner_can_change_icon_title",
            "add": "only_admin_can_add_member",
            "call": "only_admin_can_call",
            "link": "members_can_see_private_link",
        }

        if len(args) < 2 or args[0].lower() not in mapping:
            await utils.answer(
                message,
                utils.heading("⚙️ Настройки группы")
                + "\n"
                + utils.quote(
                    "\n".join(f"{key} — {value}" for key, value in mapping.items())
                )
                + f"\nПример: {utils.mono(self.get_prefix() + 'grsettings pin on')}",
            )
            return

        value = args[1].lower() in {"on", "1", "true", "да", "вкл"}

        try:
            await self._client.change_group_settings(
                utils.get_chat_id(message),
                **{mapping[args[0].lower()]: value},
            )
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        await utils.answer(
            message,
            f"⚙️ {utils.mono(args[0].lower())} → {'вкл' if value else 'выкл'}",
        )

    @loader.command()
    async def linkcmd(self, message: Message):
        """[id | название] — пригласительная ссылка чата"""
        chat = await self._resolve_chat(message, utils.get_args_raw(message))

        if chat is None:
            await utils.answer(message, "❌ Чат не найден")
            return

        if not getattr(chat, "link", None):
            await utils.answer(message, "🔗 У чата нет пригласительной ссылки")
            return

        await utils.answer(message, f"🔗 **{self._title(chat)}**\n{chat.link}")

    @loader.command()
    async def relinkcmd(self, message: Message):
        """[id | название] — перевыпустить пригласительную ссылку"""
        chat = await self._resolve_chat(message, utils.get_args_raw(message))

        if chat is None:
            await utils.answer(message, "❌ Чат не найден")
            return

        try:
            updated = await self._client.rework_invite_link(chat.id)
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        utils.drop_chat_cache(chat.id)
        await utils.answer(
            message,
            f"🔗 Новая ссылка для **{self._title(updated)}**\n{updated.link}",
        )
