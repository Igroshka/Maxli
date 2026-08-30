"""Утилиты Maxli.

Аналог ``heroku/utils.py``, адаптированный под PyMax 2.3.1 и мессенджер MAX.
"""

from __future__ import annotations

import asyncio
import collections
import contextlib
import functools
import inspect
import io
import logging
import os
import random
import re
import shlex
import string
import time
import typing
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
from pymax import Client, File, Message, Photo, Video
from pymax.types import Chat, User

logger = logging.getLogger(__name__)

init_ts = time.perf_counter()

_client: Client | None = None


# --------------------------------------------------------------------------- #
#                                   client                                    #
# --------------------------------------------------------------------------- #


def bind_client(client: Client) -> None:
    """Запоминает активный клиент, чтобы утилиты работали без явной передачи."""
    global _client
    _client = client


def get_client() -> Client:
    """Возвращает активный клиент."""
    if _client is None:
        raise RuntimeError("Client is not bound yet")
    return _client


def get_me_id() -> int | None:
    """ID текущего аккаунта или ``None``, если профиль ещё не загружен."""
    if _client is None or _client.me is None:
        return None
    return _client.me.contact.id


def is_outgoing(message: Message) -> bool:
    """``True``, если сообщение отправлено нами."""
    me = get_me_id()
    return me is not None and message.sender == me


#: ID сообщений, которые отредактировал сам юзербот (ответы команд).
_own_edits: collections.deque = collections.deque(maxlen=512)


def mark_own_edit(message_id: int) -> None:
    """Помечает правку как сделанную юзерботом."""
    _own_edits.append(message_id)


def is_own_edit(message_id: int) -> bool:
    """``True``, если это наша собственная правка, а не пользовательская."""
    return message_id in _own_edits


# --------------------------------------------------------------------------- #
#                                  arguments                                  #
# --------------------------------------------------------------------------- #


def get_args_raw(message: Message | str) -> str:
    """Возвращает всё, что идёт после команды, одной строкой."""
    text = message if isinstance(message, str) else (message.text or "")
    return args[1] if len(args := text.split(maxsplit=1)) > 1 else ""


def get_args(message: Message | str) -> list[str]:
    """Разбивает аргументы с учётом кавычек."""
    raw = get_args_raw(message)
    if not raw:
        return []

    try:
        parsed = shlex.split(raw)
    except ValueError:
        parsed = raw.split()

    return [item for item in map(str.strip, parsed) if item]


def get_args_split_by(message: Message | str, separator: str) -> list[str]:
    """Разбивает аргументы по произвольному разделителю."""
    raw = get_args_raw(message)
    return [item for item in map(str.strip, raw.split(separator)) if item]


def get_args_html(message: Message) -> str:
    """Синоним :func:`get_args_raw` — MAX не отдаёт HTML отдельно."""
    return get_args_raw(message)


# --------------------------------------------------------------------------- #
#                                   entities                                  #
# --------------------------------------------------------------------------- #


def get_chat_id(message: Message | Chat | int | None) -> int | None:
    """Достаёт ID чата из сообщения, чата или числа.

    У ``Message`` есть и ``chat_id``, и ``id`` — брать ``id`` как запасной
    вариант нельзя, это ID сообщения, а не чата.
    """
    if message is None:
        return None

    if isinstance(message, int):
        return message

    if isinstance(message, Message):
        return message.chat_id

    return getattr(message, "id", None)


def get_sender_id(message: Message) -> int | None:
    """ID отправителя сообщения."""
    return getattr(message, "sender", None)


def get_display_name(entity: User | Chat | None) -> str:
    """Отображаемое имя пользователя или чата."""
    if entity is None:
        return "Unknown"

    if isinstance(entity, Chat) or hasattr(entity, "title"):
        title = getattr(entity, "title", None)
        if title:
            return title

    names = getattr(entity, "names", None) or []
    for name in names:
        value = getattr(name, "name", None) or getattr(name, "first_name", None)
        if value:
            return value

    return str(getattr(entity, "id", "Unknown"))


_chat_cache: dict[int, tuple[float, Chat]] = {}
CHAT_CACHE_TTL = 300


def get_dialog_id(user_id: int) -> int | None:
    """ID личного диалога с пользователем.

    MAX вычисляет его как XOR двух ID (см. ``UserService.get_chat_id``).
    """
    me = get_me_id()
    return None if me is None else me ^ int(user_id)


async def get_self_chat_id() -> int | None:
    """ID чата «Избранное» — диалога с самим собой.

    Ищет диалог, единственный участник которого — мы. Если в кэше его нет,
    один раз догружает список чатов. Возвращает ``None``, если найти не удалось:
    отправлять в такой чат нельзя, и вызывающий код должен это учитывать.
    """
    me = get_me_id()

    if me is None:
        return None

    def find(chats) -> int | None:
        for chat in chats or []:
            participants = getattr(chat, "participants", None) or {}
            if is_private(chat) and set(participants) == {me}:
                return chat.id
        return None

    client = get_client()

    if (found := find(getattr(client, "chats", None))) is not None:
        return found

    with contextlib.suppress(Exception):
        return find(await client.fetch_chats())

    return None


def get_reply_id(message: Message) -> int | None:
    """ID сообщения, на которое отвечает данное.

    В MAX ответ приходит в поле ``link`` вида
    ``{"type": "REPLY", "messageId": 123}`` — pydantic-модель PyMax разрешает
    дополнительные поля, поэтому читаем его напрямую.
    """
    link = getattr(message, "link", None)

    if isinstance(link, dict):
        if str(link.get("type", "")).upper() != "REPLY":
            return None

        raw = link.get("messageId") or link.get("message_id")
        if raw is None and isinstance(link.get("message"), dict):
            raw = link["message"].get("id")

        with contextlib.suppress(TypeError, ValueError):
            return int(raw)

    return None


async def get_reply(message: Message) -> Message | None:
    """Возвращает сообщение, на которое отвечает данное."""
    reply_id = get_reply_id(message)
    chat_id = get_chat_id(message)

    if reply_id is None or chat_id is None:
        return None

    with contextlib.suppress(Exception):
        return await get_client().get_message(chat_id, reply_id)

    return None


def get_file_attach(message: Message | None) -> typing.Any | None:
    """Первое файловое вложение сообщения."""
    for attach in getattr(message, "attaches", None) or []:
        if str(getattr(attach, "type", "")).upper().endswith("FILE"):
            return attach

    return None


async def get_attach_url(message: Message, attach: typing.Any) -> str | None:
    """Прямая ссылка на вложение.

    MAX отдаёт её не всегда сразу — тогда докручиваем через ``FILE_DOWNLOAD``.
    """
    if url := getattr(attach, "url", None):
        return url

    file_id = getattr(attach, "file_id", None) or getattr(attach, "audio_id", None)
    chat_id = get_chat_id(message)

    if file_id is None or chat_id is None:
        return None

    with contextlib.suppress(Exception):
        result = await get_client().get_file_by_id(chat_id, message.id, file_id)

        if result is not None and getattr(result, "url", None):
            return result.url

    return None


async def get_reply_document(message: Message) -> tuple[str, bytes] | None:
    """Имя и содержимое файла из сообщения, на которое отвечают.

    Возвращает ``None``, если ответа нет, в нём нет файла или его не скачать.
    """
    reply = await get_reply(message)
    attach = get_file_attach(reply)

    if reply is None or attach is None:
        return None

    url = await get_attach_url(reply, attach)

    if not url:
        return None

    timeout = aiohttp.ClientTimeout(total=120, connect=15, sock_read=60)

    with contextlib.suppress(Exception):
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, allow_redirects=True) as response:
                response.raise_for_status()
                data = await response.read()

        return getattr(attach, "name", None) or "file.bin", data

    return None


async def get_target_user(message: Message, args: str = "") -> User | None:
    """Определяет пользователя, к которому относится команда.

    Порядок: аргумент (ID, телефон или ссылка на профиль) → автор сообщения,
    на которое отвечают → ``None``.
    """
    args = (args or "").strip()
    client = get_client()

    if args:
        if args.lstrip("-").isdigit():
            with contextlib.suppress(Exception):
                if (user := await client.get_user(int(args))) is not None:
                    return user

        if args.startswith("+"):
            with contextlib.suppress(Exception):
                return await client.search_by_phone(args)

    reply = await get_reply(message)
    if reply is not None and reply.sender is not None:
        with contextlib.suppress(Exception):
            return await client.get_user(reply.sender)

    return None


async def get_target_id(message: Message, args: str = "") -> int | None:
    """Как :func:`get_target_user`, но возвращает только ID."""
    args = (args or "").strip()

    with contextlib.suppress(TypeError, ValueError):
        return int(args)

    user = await get_target_user(message, args)
    return user.id if user else None


async def get_chat(message: Message | int) -> Chat | None:
    """Загружает чат сообщения, кэшируя результат на 5 минут.

    Кэш нужен потому, что теги вотчеров (``only_pm``, ``no_groups``) и проверки
    прав дёргают эту функцию на каждое входящее сообщение.
    """
    chat_id = get_chat_id(message)
    if chat_id is None:
        return None

    cached = _chat_cache.get(chat_id)
    if cached and time.time() - cached[0] < CHAT_CACHE_TTL:
        return cached[1]

    with contextlib.suppress(Exception):
        chat = await get_client().get_chat(chat_id)
        if chat is not None:
            _chat_cache[chat_id] = (time.time(), chat)
        return chat

    return None


def drop_chat_cache(chat_id: int | None = None) -> None:
    """Сбрасывает кэш чатов целиком или для одного чата."""
    if chat_id is None:
        _chat_cache.clear()
    else:
        _chat_cache.pop(chat_id, None)


def is_private(chat: Chat | None) -> bool:
    """``True``, если это личный диалог."""
    return chat is not None and str(getattr(chat, "type", "")).upper().endswith("DIALOG")


def is_channel(chat: Chat | None) -> bool:
    """``True``, если это канал."""
    return chat is not None and str(getattr(chat, "type", "")).upper().endswith("CHANNEL")


def is_group(chat: Chat | None) -> bool:
    """``True``, если это групповой чат."""
    return chat is not None and str(getattr(chat, "type", "")).upper().endswith("CHAT")


# --------------------------------------------------------------------------- #
#                                   answering                                 #
# --------------------------------------------------------------------------- #


async def answer(
    message: Message,
    response: str,
    *,
    reply: bool = False,
    attachments: typing.Sequence[Photo | File | Video] | None = None,
    notify: bool = True,
) -> Message | None:
    """Отвечает на сообщение.

    Если сообщение отправлено нами — редактирует его на месте (поведение
    Heroku). Иначе отправляет новое сообщение в тот же чат.
    """
    if is_outgoing(message) and not reply and not attachments:
        with contextlib.suppress(Exception):
            edited = await message.edit(response)
            # Помечаем правку своей, чтобы диспетчер не выполнил команду повторно
            mark_own_edit(message.id)
            return edited

    if reply:
        return await message.reply(response, attachments, notify=notify)

    return await message.answer(response, attachments=attachments, notify=notify)


async def answer_file(
    message: Message,
    file: str | bytes | Path,
    caption: str = "",
    *,
    name: str | None = None,
    photo: bool = False,
    video: bool = False,
) -> Message | None:
    """Отправляет файл в чат сообщения."""
    kind = Photo if photo else Video if video else File

    if isinstance(file, bytes):
        attachment = kind(file, name=name or "file.bin")
    elif str(file).startswith(("http://", "https://")):
        attachment = kind(url=str(file), name=name)
    else:
        attachment = kind(path=str(file), name=name)

    return await message.answer(caption, attachments=[attachment])


async def delete(message: Message, for_me: bool = False) -> bool:
    """Удаляет сообщение, глуша ошибки."""
    with contextlib.suppress(Exception):
        return await message.delete(for_me=for_me)
    return False


# --------------------------------------------------------------------------- #
#                                   strings                                   #
# --------------------------------------------------------------------------- #


def escape_quotes(text: str) -> str:
    """Экранирует двойные кавычки."""
    return str(text).replace('"', '\\"')


def escape_md(text: str) -> str:
    """Экранирует markdown-разметку MAX."""
    return re.sub(r"([*_`~\[\]])", r"\\\1", str(text))


def mono(text: str) -> str:
    """Возвращает чистый текст без бэктиков."""
    return str(text).replace("`", "")


def heading(text: str) -> str:
    """Заголовок MAX (элемент ``HEADING``).

    Разметка внутри заголовка не разбирается — передавай простой текст.
    """
    return "# " + str(text).replace("\n", " ")


def quote(text: str) -> str:
    """Оборачивает текст в цитату MAX (элемент ``QUOTE``).

    Каждая строка получает свой маркер ``>``; идущие подряд строки MAX
    показывает одним блоком.

    ⚠️ Внутри цитаты MAX **не разбирает markdown**: ``**жирный**`` и
    ``` `моно` ``` останутся видимыми символами. Передавай простой текст —
    для этого есть :func:`unmark`.
    """
    lines = str(text).splitlines() or [""]

    # Пустая строка разорвала бы блок надвое: парсер MAX съедает пробел после
    # «>» и при нулевой длине не создаёт элемент QUOTE. Поэтому пустым строкам
    # даём два пробела — один служебный, второй становится телом цитаты.
    return "\n".join(f"> {line}" if line.strip() else ">  " for line in lines)


#: Маркеры разметки MAX, которые внутри цитаты показались бы как есть.
_MD_MARKERS = re.compile(r"```|\*\*|~~|`|\*")

#: Начало строки, которое MAX принял бы за свою цитату или заголовок.
_MD_LINE_PREFIX = re.compile(r"^\s*[>#]+\s*", re.MULTILINE)


def unmark(text: str) -> str:
    """Убирает markdown-маркеры, чтобы текст было не стыдно положить в цитату.

    Снимает не только инлайновые маркеры, но и ведущие ``>``/``#``: иначе
    чужое описание, начинающееся с цитаты, дало бы ``> > текст``.

    Одиночные ``_`` не трогаются: они часто встречаются в именах настроек и
    команд, а внутри цитаты всё равно не интерпретируются.
    """
    return _MD_LINE_PREFIX.sub("", _MD_MARKERS.sub("", str(text)))


def code_block(text: str, limit: int = 3000) -> str:
    """Форматирует многострочный текст для вставки в сообщение без сырых бэктиков."""
    return smart_truncate(str(text), limit)


def censor(text: str) -> str:
    """Прячет телефоны и токены в тексте перед выводом в логи."""
    text = re.sub(r"\+?\d{10,15}", "+**********", text)
    return re.sub(r"[0-9a-f]{32,}", "**********", text, flags=re.I)


def chunks(seq: typing.Sequence, size: int) -> list:
    """Режет последовательность на куски по ``size``."""
    return [seq[i : i + size] for i in range(0, len(seq), size)]


def rand(size: int) -> str:
    """Случайная строка из букв и цифр."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=size))


def check_url(url: str) -> bool:
    """Проверяет, что строка — валидный http(s)-URL."""
    with contextlib.suppress(Exception):
        parsed = urlparse(url)
        return bool(parsed.scheme in {"http", "https"} and parsed.netloc)
    return False


def humanbytes(size: int | float) -> str:
    """Человекочитаемый размер."""
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(size) < 1024:
            return f"{size:.2f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.2f} PiB"


def uptime() -> int:
    """Аптайм процесса в секундах."""
    return round(time.perf_counter() - init_ts)


def formatted_uptime() -> str:
    """Аптайм в формате ``1d 2h 3m 4s``."""
    total = uptime()
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or parts:
        parts.append(f"{hours}h")
    if minutes or parts:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


# --------------------------------------------------------------------------- #
#                                  execution                                  #
# --------------------------------------------------------------------------- #


async def run_sync(func: typing.Callable, *args, **kwargs) -> typing.Any:
    """Выполняет блокирующую функцию в отдельном потоке."""
    return await asyncio.get_event_loop().run_in_executor(
        None,
        functools.partial(func, *args, **kwargs),
    )


async def maybe_await(value: typing.Any) -> typing.Any:
    """Ожидает значение, если оно awaitable."""
    if inspect.isawaitable(value):
        return await value
    return value


def iter_attrs(obj: typing.Any) -> list[tuple[str, typing.Any]]:
    """Итерирует публичные атрибуты объекта."""
    return [(name, getattr(obj, name)) for name in dir(obj) if not name.startswith("__")]


def get_base_dir() -> str:
    """Корневая директория установки Maxli.

    В Docker (переменная ``MAXLI_DOCKER``) данные лежат в ``/data``, чтобы
    конфиг, база и пользовательские модули переживали пересборку образа.
    """
    if "MAXLI_DOCKER" in os.environ:
        return "/data"

    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def relative_path(*parts: str) -> Path:
    """Путь относительно корня Maxli."""
    return Path(get_base_dir()).joinpath(*parts)


def as_document(text: str, name: str = "output.txt") -> File:
    """Оборачивает длинный текст в файл для отправки."""
    return File(io.BytesIO(text.encode()).getvalue(), name=name)


def smart_truncate(text: str, limit: int = 4000, tail: str = "…") -> str:
    """Обрезает текст до лимита MAX."""
    return text if len(text) <= limit else text[: limit - len(tail)] + tail


# --------------------------------------------------------------------------- #
#                                service chats                               #
# --------------------------------------------------------------------------- #


_known_created_chats: set[int] = set()


async def create_service_group(client, name: str) -> int | None:
    """Создает сервисную группу в MAX напрямую по протоколу."""
    if not client or not getattr(client, "_app", None):
        logger.warning("create_service_group: client or _app is None")
        return None

    try:
        from pymax.api.chats.payloads import CreateGroupAttach, CreateGroupMessage, CreateGroupPayload
        from pymax.protocol import Opcode

        frame = CreateGroupPayload(
            message=CreateGroupMessage(
                cid=int(time.time() * 1000),
                attaches=[
                    CreateGroupAttach(
                        title=name,
                        user_ids=[],
                    )
                ],
            ),
            notify=True,
        )

        resp = await client._app.invoke(Opcode.MSG_SEND, frame.to_payload())
        data = resp.payload if hasattr(resp, "payload") else resp
        logger.info("Creating group '%s', raw server response: %s", name, data)

        if isinstance(data, dict):
            chat_obj = data.get("chat")
            if chat_obj:
                chat_id = chat_obj.get("id") if isinstance(chat_obj, dict) else getattr(chat_obj, "id", None)
                if chat_id:
                    cid = int(chat_id)
                    _known_created_chats.add(cid)
                    logger.info("Successfully created group '%s' with ID %s", name, cid)
                    return cid
    except Exception as e:
        logger.exception("Failed to create group '%s': %s", name, e)

    return None


async def get_log_chat(client=None, db=None) -> int | None:
    """Находит или создаёт группу для системных логов Maxli."""
    client = client or _client
    if client is None:
        return None

    try:
        chats = await client.fetch_chats()
    except Exception as e:
        logger.debug("Failed to fetch chats: %s", e)
        chats = getattr(client, "chats", []) or []

    if db is not None:
        saved_id = db.get("main", "log_chat", 0)
        if saved_id:
            chat_exists = (int(saved_id) in _known_created_chats) or any(chat.id == int(saved_id) for chat in chats)
            if chat_exists:
                return int(saved_id)
            logger.info("Saved log chat %s is not in active chats %s, resetting...", saved_id, [c.id for c in chats])
            db.set("main", "log_chat", 0)
            db.save()

    for chat in chats:
        title = str(getattr(chat, "title", "")).strip().lower()
        if title in {"maxli logs", "maxli log", "maxli logs (official)"}:
            logger.info("Found existing log chat: %s (%s)", getattr(chat, "title", ""), chat.id)
            if db is not None:
                db.set("main", "log_chat", chat.id)
                db.save()
            return chat.id

    # Создаём новую группу
    new_id = await create_service_group(client, "Maxli Logs")
    if new_id:
        if db is not None:
            db.set("main", "log_chat", new_id)
            db.save()
        return new_id

    return 0


async def get_backup_chat(client=None, db=None) -> int | None:
    """Находит или создаёт группу для бэкапов Maxli."""
    client = client or _client
    if client is None:
        return None

    try:
        chats = await client.fetch_chats()
    except Exception as e:
        logger.debug("Failed to fetch chats: %s", e)
        chats = getattr(client, "chats", []) or []

    if db is not None:
        saved_id = db.get("main", "backup_chat", 0)
        if saved_id:
            chat_exists = (int(saved_id) in _known_created_chats) or any(chat.id == int(saved_id) for chat in chats)
            if chat_exists:
                return int(saved_id)
            logger.info("Saved backup chat %s is not in active chats %s, resetting...", saved_id, [c.id for c in chats])
            db.set("main", "backup_chat", 0)
            db.save()

    for chat in chats:
        title = str(getattr(chat, "title", "")).strip().lower()
        if title in {"maxli backups", "maxli backup", "maxli backup (official)"}:
            logger.info("Found existing backup chat: %s (%s)", getattr(chat, "title", ""), chat.id)
            if db is not None:
                db.set("main", "backup_chat", chat.id)
                db.save()
            return chat.id

    # Создаём новую группу
    new_id = await create_service_group(client, "Maxli Backups")
    if new_id:
        if db is not None:
            db.set("main", "backup_chat", new_id)
            db.save()
        return new_id

    return 0


async def log_to_chat(text: str, client=None, db=None) -> None:
    """Отправляет служебное сообщение в лог-чат."""
    client = client or _client
    if client is None:
        return

    chat_id = await get_log_chat(client, db)
    if chat_id:
        with contextlib.suppress(Exception):
            await client.send_message(chat_id, text)


# --------------------------------------------------------------------------- #
#                                placeholders                                 #
# --------------------------------------------------------------------------- #

from .placeholders import (  # noqa: E402
    config_placeholders,
    debug_placeholders,
    get_placeholder,
    get_placeholders,
    help_placeholders,
    module_placeholders,
    register_placeholder,
    unregister_placeholders,
)
