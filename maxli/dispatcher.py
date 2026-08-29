"""Диспетчер команд Maxli.

Аналог ``heroku/dispatcher.py``: разбирает входящие сообщения, находит команду,
проверяет права и ratelimit, вызывает обработчик и вотчеры.
"""

from __future__ import annotations

import asyncio
import collections
import contextlib
import inspect
import logging
import re
import time
import traceback
import typing

from pymax import Client, Message

from . import main, utils
from .security import SecurityManager
from .types import SelfSuspend, SelfUnload, StopLoop

logger = logging.getLogger(__name__)

Command = typing.Callable[..., typing.Awaitable[typing.Any]]

#: Раскладка «русский → английский» для команд, набранных не в той раскладке.
_LAYOUT_TRANSLATION = str.maketrans(
    "йцукенгшщзхъфывапролджэячсмитьбюЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ.,",
    "qwertyuiop[]asdfghjkl;'zxcvbnm,.QWERTYUIOP{}ASDFGHJKL:\"ZXCVBNM<>/?",
)

ALLOWED_RATELIMIT = 5
RATELIMIT_WINDOW = 30


class CommandDispatcher:
    """Обрабатывает входящие события MAX."""

    def __init__(self, modules, client: Client, db):
        self._modules = modules
        self._client = client
        self._db = db

        self.security = SecurityManager(client, db)
        # Модули обращаются к менеджеру прав через ``self.allmodules.security``
        modules.attach_security(self.security)

        self._ratelimit_storage: dict[int, collections.deque] = collections.defaultdict(
            lambda: collections.deque(maxlen=64)
        )
        self._ratelimited_until: dict[int, float] = {}

    # ------------------------------------------------------------------ #
    #                               ratelimit                             #
    # ------------------------------------------------------------------ #

    async def _handle_ratelimit(self, message: Message, func: Command) -> bool:
        """Возвращает ``False``, если пользователь превысил лимит вызовов."""
        user_id = utils.get_sender_id(message)
        if user_id is None or user_id == utils.get_me_id():
            return True

        now = time.time()

        if self._ratelimited_until.get(user_id, 0) > now:
            return False

        calls = self._ratelimit_storage[user_id]
        calls.append(now)

        window = [call for call in calls if now - call < RATELIMIT_WINDOW]
        limit = ALLOWED_RATELIMIT // 2 if getattr(func, "ratelimit", False) else ALLOWED_RATELIMIT

        if len(window) > limit:
            self._ratelimited_until[user_id] = now + RATELIMIT_WINDOW
            logger.debug("Ratelimited user %s", user_id)
            return False

        return True

    # ------------------------------------------------------------------ #
    #                                  tags                               #
    # ------------------------------------------------------------------ #

    async def _handle_tags(self, message: Message, func: Command) -> bool:
        """``True``, если сообщение НЕ подходит под теги обработчика."""
        return bool(await self._handle_tags_ext(message, func))

    async def _handle_tags_ext(self, message: Message, func: Command) -> str | None:
        """Возвращает имя тега, из-за которого событие отброшено."""
        text = message.text or ""
        outgoing = utils.is_outgoing(message)

        def get(tag_: str, default=None):
            return getattr(func, tag_, default)

        if get("out") and not outgoing:
            return "out"

        if get("in") and outgoing:
            return "in"

        if get("no_commands") and self._is_command(text):
            return "no_commands"

        if get("only_commands") and not self._is_command(text):
            return "only_commands"

        if get("no_media") and message.attaches:
            return "no_media"

        if get("only_media") and not message.attaches:
            return "only_media"

        for tag_, kind in (
            ("only_photos", "PHOTO"),
            ("only_videos", "VIDEO"),
            ("only_docs", "FILE"),
            ("only_stickers", "STICKER"),
            ("only_audios", "AUDIO"),
        ):
            if get(tag_) and not any(
                str(getattr(att, "type", "")).upper().endswith(kind)
                for att in message.attaches
            ):
                return tag_

        if get("no_reply") or get("only_reply"):
            is_reply = utils.get_reply_id(message) is not None

            if get("no_reply") and is_reply:
                return "no_reply"

            if get("only_reply") and not is_reply:
                return "only_reply"

        if (prefix := get("startswith")) and not text.startswith(prefix):
            return "startswith"

        if (suffix := get("endswith")) and not text.endswith(suffix):
            return "endswith"

        if (needle := get("contains")) and needle not in text:
            return "contains"

        if (pattern := get("regex")) and not re.search(pattern, text):
            return "regex"

        if (from_id := get("from_id")) and message.sender != from_id:
            return "from_id"

        if (chat_id := get("chat_id")) and message.chat_id != chat_id:
            return "chat_id"

        if (custom := get("filter")) and callable(custom):
            result = custom(message)
            if inspect.isawaitable(result):
                result = await result
            if not result:
                return "filter"

        if any(get(tag_) for tag_ in ("only_pm", "no_pm", "only_groups", "no_groups", "only_channels", "no_channels")):
            chat = await utils.get_chat(message)

            if get("only_pm") and not utils.is_private(chat):
                return "only_pm"
            if get("no_pm") and utils.is_private(chat):
                return "no_pm"
            if get("only_groups") and not utils.is_group(chat):
                return "only_groups"
            if get("no_groups") and utils.is_group(chat):
                return "no_groups"
            if get("only_channels") and not utils.is_channel(chat):
                return "only_channels"
            if get("no_channels") and utils.is_channel(chat):
                return "no_channels"

        return None

    def _is_command(self, text: str) -> bool:
        """``True``, если текст начинается с любого известного префикса."""
        return any(text.startswith(prefix) for prefix in self._modules.get_prefixes())

    # ------------------------------------------------------------------ #
    #                                parsing                              #
    # ------------------------------------------------------------------ #

    async def _handle_command(
        self,
        message: Message,
        watcher: bool = False,
    ) -> tuple[Message, str, str, Command] | typing.Literal[False]:
        """Разбирает сообщение и находит подходящую команду."""
        text = message.text or ""
        if not text:
            return False

        initiator = utils.get_sender_id(message)
        prefix = self._modules.get_prefix(
            None if initiator == utils.get_me_id() else initiator
        )

        # Экранирование: `..cmd` не выполняется, а превращается в `.cmd`
        if (
            utils.is_outgoing(message)
            and len(text) > len(prefix) * 2
            and text.startswith(prefix * 2)
        ):
            tail = text[len(prefix) * 2 :].strip().split(maxsplit=1)
            possible = tail[0] if tail else ""

            if possible and self._modules.dispatch(possible)[1]:
                if not watcher:
                    with contextlib.suppress(Exception):
                        await message.edit(text[len(prefix) :])
                return False

        # Команда, набранная в русской раскладке
        translated_prefix = str.translate(prefix, _LAYOUT_TRANSLATION)
        if translated_prefix != prefix and text.startswith(translated_prefix):
            text = str.translate(text, _LAYOUT_TRANSLATION)
        elif not text.startswith(prefix):
            return False

        if len(text.strip()) == len(prefix):
            return False

        if initiator in self._db.get(main.__name__, "blacklist_users", []):
            return False

        chat_id = utils.get_chat_id(message)
        blacklist_chats = self._db.get(main.__name__, "blacklist_chats", [])
        whitelist_chats = self._db.get(main.__name__, "whitelist_chats", [])

        if chat_id in blacklist_chats or (whitelist_chats and chat_id not in whitelist_chats):
            return False

        body = text[len(prefix) :]
        command_name = body.strip().split(maxsplit=1)[0]

        txt, func = self._modules.dispatch(command_name)

        if (
            func is None
            or not await self._handle_ratelimit(message, func)
            or not await self.security.check(message, func)
        ):
            return False

        if await self._handle_tags(message, func):
            return False

        return message, prefix, txt, func

    # ------------------------------------------------------------------ #
    #                                handlers                             #
    # ------------------------------------------------------------------ #

    async def handle_incoming(self, message: Message, client: Client) -> None:
        """Точка входа: вызывается PyMax на каждое новое сообщение."""
        try:
            await self._dispatch(message)
        except Exception:
            logger.exception("Unhandled error while dispatching message")

    async def handle_edit(self, message: Message, client: Client) -> None:
        """Обрабатывает редактирование сообщения.

        ``utils.answer`` редактирует наши же сообщения, поэтому ответ команды
        прилетает сюда как ``MESSAGE_EDIT``. Такие правки помечены и
        пропускаются, а вручную отредактированное сообщение по-прежнему может
        стать командой — как в Heroku.
        """
        if utils.is_own_edit(message.id):
            return

        try:
            await self._dispatch(message)
        except Exception:
            logger.exception("Unhandled error while dispatching edit")

    async def _dispatch(self, message: Message) -> None:
        parsed = await self._handle_command(message)

        if parsed is not False:
            _, _, txt, func = parsed
            asyncio.ensure_future(self.handle_command(message, func, txt))

        asyncio.ensure_future(self.handle_watchers(message))

    async def handle_command(self, message: Message, func: Command, txt: str) -> None:
        """Выполняет команду и сообщает об ошибке в чат."""
        logger.debug("Executing command %s", txt)

        try:
            await func(message)
        except SelfUnload:
            module = getattr(func, "__self__", None)
            if module is not None:
                await self._modules.unload_module(module.__class__.__name__)
        except SelfSuspend:
            return
        except StopLoop:
            return
        except Exception as e:
            await self.command_exc(e, message, txt)

    async def command_exc(self, exc: Exception, message: Message, txt: str) -> None:
        """Красиво выводит traceback команды."""
        logger.exception("Command %s failed", txt)

        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        tb = utils.censor(tb)

        text = (
            f"🚫 **Ошибка в команде** {utils.mono(txt)}\n\n"
            f"{utils.mono(f'{type(exc).__name__}: {exc}')}\n\n"
            f"{utils.quote(tb, 2500)}"
        )

        with contextlib.suppress(Exception):
            await utils.answer(message, text)

        # Отправляем лог ошибки в лог-чат
        try:
            log_chat_id = await utils.get_log_chat(self._client, self._db)
            chat_id = utils.get_chat_id(message)
            if log_chat_id and log_chat_id != chat_id:
                log_err_text = (
                    f"🚫 **Ошибка выполнения команды** {utils.mono(txt)}\n"
                    f"> 📍 **Чат:** {chat_id}\n\n"
                    f"{utils.quote(tb, 3000)}"
                )
                await self._client.send_message(log_chat_id, log_err_text)
        except Exception:
            pass

    async def handle_watchers(self, message: Message) -> None:
        """Прогоняет сообщение через все вотчеры."""
        disabled = set(self._db.get(main.__name__, "disabled_watchers", []))
        blacklist = self._db.get(main.__name__, "watcher_blacklist", {})
        chat_id = utils.get_chat_id(message)

        for watcher_ in self._modules.watchers.copy():
            owner_cls = getattr(getattr(watcher_, "__self__", None), "__class__", None)
            name = owner_cls.__name__ if owner_cls else ""

            if name in disabled or chat_id in blacklist.get(name, []):
                continue

            if await self._handle_tags(message, watcher_):
                continue

            try:
                await watcher_(message)
            except StopLoop:
                continue
            except Exception:
                logger.exception("Error in watcher %s", watcher_)

    async def handle_raw(self, frame, client: Client) -> None:
        """Передаёт сырой фрейм зарегистрированным обработчикам."""
        raw_opcode = getattr(frame, "opcode", None)

        try:
            from pymax.protocol import Opcode

            name = Opcode(raw_opcode).name
        except Exception:
            name = str(raw_opcode)

        for handler in self._modules.raw_handlers.copy():
            events = getattr(handler, "events", ())

            if events and name not in events and str(raw_opcode) not in events:
                continue

            try:
                await handler(frame)
            except Exception:
                logger.exception("Error in raw handler %s", handler)
