# ©️ Maxli, 2026
# This file is a part of Maxli Userbot
# 🌐 https://github.com/Igroshka/Maxli
# Аналога в Heroku нет — модуль построен на возможностях MAX

# meta developer: @Igroshka
# scope: maxli_only

import time

from pymax import Message

from .. import loader, utils


@loader.tds
class MessagesMod(loader.Module):
    """Работа с сообщениями: история, пересылка, реакции, закрепления"""

    strings = {"name": "Messages"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "history_limit",
                20,
                lambda: "Сколько сообщений показывать в .history",
                validator=loader.validators.Integer(minimum=1, maximum=100),
            ),
            loader.ConfigValue(
                "default_reaction",
                "❤",
                lambda: "Реакция по умолчанию для .react",
                validator=loader.validators.String(),
            ),
        )

    # ------------------------------------------------------------------ #
    #                                history                              #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def historycmd(self, message: Message):
        """[количество] — последние сообщения текущего чата"""
        args = utils.get_args_raw(message).strip()
        limit = int(args) if args.isdigit() else self.config["history_limit"]
        limit = max(1, min(limit, 100))

        chat_id = utils.get_chat_id(message)

        try:
            history = await self._client.fetch_history(chat_id, backward=limit)
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        if not history:
            await utils.answer(message, "📜 История пуста")
            return

        senders = {msg.sender for msg in history if msg.sender}

        try:
            users = await self._client.get_users(list(senders))
            names = {user.id: utils.get_display_name(user) for user in users}
        except Exception:
            names = {}

        lines = []

        for msg in history:
            stamp = time.strftime("%H:%M", time.localtime((msg.time or 0) / 1000))
            author = utils.unmark(names.get(msg.sender, str(msg.sender)))
            text = utils.unmark((msg.text or "").replace("\n", " ")) or "[вложение]"
            lines.append(f"{stamp} {author}: {utils.smart_truncate(text, 200)}")

        await utils.answer(
            message,
            utils.smart_truncate(
                utils.heading(f"📜 Последние {len(history)} сообщений")
                + "\n"
                + utils.quote("\n".join(lines))
            ),
        )

    @loader.command()
    async def idcmd(self, message: Message):
        """ID текущего чата и сообщения, на которое отвечаешь"""
        reply = await utils.get_reply(message)

        lines = [
            f"💬 чат: {utils.get_chat_id(message)}",
            f"👤 ты: {utils.get_me_id()}",
        ]

        if reply is not None:
            lines += [
                f"✉️ сообщение: {reply.id}",
                f"👤 отправитель: {reply.sender}",
            ]

        await utils.answer(message, utils.quote("\n".join(lines)))

    # ------------------------------------------------------------------ #
    #                            message actions                          #
    # ------------------------------------------------------------------ #

    @loader.command(alias="fwd")
    async def forwardcmd(self, message: Message):
        """<id чата> — переслать сообщение, на которое отвечаешь"""
        args = utils.get_args_raw(message).strip()
        reply = await utils.get_reply(message)

        if reply is None:
            await utils.answer(message, "❌ Ответь на сообщение, которое нужно переслать")
            return

        if not args.lstrip("-").isdigit():
            await utils.answer(message, "❌ Укажи ID целевого чата")
            return

        try:
            await reply.forward(int(args))
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        await utils.answer(message, f"📨 Переслано в {utils.mono(args)}")

    @loader.command()
    async def copycmd(self, message: Message):
        """<id чата> — отправить копию текста сообщения в другой чат"""
        args = utils.get_args_raw(message).strip()
        reply = await utils.get_reply(message)

        if reply is None or not reply.text:
            await utils.answer(message, "❌ Ответь на текстовое сообщение")
            return

        if not args.lstrip("-").isdigit():
            await utils.answer(message, "❌ Укажи ID целевого чата")
            return

        try:
            await self._client.send_message(int(args), reply.text)
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        await utils.answer(message, f"📋 Скопировано в {utils.mono(args)}")

    @loader.command()
    async def pincmd(self, message: Message):
        """[silent] — закрепить сообщение, на которое отвечаешь"""
        reply = await utils.get_reply(message)

        if reply is None:
            await utils.answer(message, "❌ Ответь на сообщение, которое нужно закрепить")
            return

        notify = utils.get_args_raw(message).strip().lower() not in {"silent", "тихо"}

        try:
            await reply.pin(notify)
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        await utils.answer(message, "📌 Закреплено")

    @loader.command()
    async def delmsgcmd(self, message: Message):
        """[me] — удалить сообщение, на которое отвечаешь"""
        reply = await utils.get_reply(message)

        if reply is None:
            await utils.answer(message, "❌ Ответь на сообщение, которое нужно удалить")
            return

        for_me = utils.get_args_raw(message).strip().lower() in {"me", "себя"}

        try:
            await reply.delete(for_me=for_me)
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        await utils.delete(message)

    @loader.command()
    async def readcmd(self, message: Message):
        """Отметить чат прочитанным"""
        try:
            state = await message.read()
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        await utils.answer(
            message,
            f"👁 Прочитано, непрочитанных осталось: {getattr(state, 'unread', 0)}",
        )

    # ------------------------------------------------------------------ #
    #                               reactions                             #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def reactcmd(self, message: Message):
        """[эмодзи] — поставить реакцию на сообщение, на которое отвечаешь"""
        reply = await utils.get_reply(message)

        if reply is None:
            await utils.answer(message, "❌ Ответь на сообщение")
            return

        reaction = utils.get_args_raw(message).strip() or self.config["default_reaction"]

        try:
            await reply.react(reaction)
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        await utils.delete(message)

    @loader.command()
    async def unreactcmd(self, message: Message):
        """Снять свою реакцию с сообщения, на которое отвечаешь"""
        reply = await utils.get_reply(message)

        if reply is None:
            await utils.answer(message, "❌ Ответь на сообщение")
            return

        try:
            await reply.unreact()
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        await utils.delete(message)

    @loader.command()
    async def reactionscmd(self, message: Message):
        """Показать реакции на сообщение, на которое отвечаешь"""
        reply = await utils.get_reply(message)

        if reply is None:
            await utils.answer(message, "❌ Ответь на сообщение")
            return

        try:
            info = await reply.get_reactions()
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось: {utils.mono(e)}")
            return

        entry = (info or {}).get(str(reply.id))

        if entry is None or not entry.counters:
            await utils.answer(message, "🫥 Реакций нет")
            return

        counters = utils.quote(
            "\n".join(
                f"{counter.reaction} — {counter.count}" for counter in entry.counters
            )
        )
        await utils.answer(
            message,
            f"😀 **Реакции** — всего {entry.total_count}\n{counters}",
        )
