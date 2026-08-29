"""Точка сборки Maxli.

Аналог ``heroku/main.py``: разбирает аргументы, поднимает БД, переводчик,
клиент PyMax, загрузчик модулей и диспетчер команд.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import sys
import time
from pathlib import Path

from pymax import Client, ExtraConfig, Message, WebClient

from . import log, utils, version
from .database import Database
from .dispatcher import CommandDispatcher
from .loader import Modules
from .translations import Translator

logger = logging.getLogger(__name__)

BASE_DIR = Path(utils.get_base_dir())
CONFIG_PATH = BASE_DIR / "config.json"
SESSIONS_DIR = BASE_DIR / "sessions"

BANNER = r"""
   __  __            _ _
  |  \/  |          | (_)
  | \  / | __ ___  _| |_
  | |\/| |/ _` \ \/ / | |
  | |  | | (_| |>  <| | |
  |_|  |_|\__,_/_/\_\_|_|   v{version}
  MAX userbot on PyMax {pymax}
"""


def _read_config() -> dict:
    """Читает ``config.json``."""
    if not CONFIG_PATH.exists():
        return {}

    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.error("config.json is corrupted, ignoring it")
        return {}


def _save_config(config: dict) -> None:
    """Пишет ``config.json``."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_config_key(key: str, default=None):
    """Возвращает значение из ``config.json``."""
    return _read_config().get(key, default)


def save_config_key(key: str, value) -> bool:
    """Записывает значение в ``config.json``."""
    config = _read_config()
    config[key] = value
    _save_config(config)
    return True


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """Разбирает аргументы командной строки."""
    parser = argparse.ArgumentParser(prog="maxli", description="Maxli — юзербот для MAX")
    parser.add_argument("--phone", "-p", help="номер телефона аккаунта MAX")
    parser.add_argument("--session", default="maxli.db", help="имя файла сессии")
    parser.add_argument("--proxy", help="прокси для подключения к MAX")
    parser.add_argument("--web", action="store_true", help="использовать WebClient и QR-логин")
    parser.add_argument("--log-level", default="INFO", help="уровень логирования")
    parser.add_argument("--root", action="store_true", help="разрешить запуск от root")
    parser.add_argument(
        "--no-modules",
        action="store_true",
        help="не загружать пользовательские модули",
    )
    return parser.parse_args(argv)


class Maxli:
    """Супервизор юзербота."""

    def __init__(self):
        self.arguments: argparse.Namespace | None = None
        self.client: Client | WebClient | None = None
        self.db: Database | None = None
        self.modules: Modules | None = None
        self.dispatcher: CommandDispatcher | None = None
        self.translator: Translator | None = None
        self.ready = asyncio.Event()
        self._booted = False

    # ------------------------------------------------------------------ #
    #                                 setup                               #
    # ------------------------------------------------------------------ #

    def _get_phone(self) -> str:
        """Достаёт номер телефона из аргументов, конфига или спрашивает у пользователя."""
        phone = self.arguments.phone or get_config_key("phone")

        if not phone:
            phone = input(">>> Введите номер телефона (например, +79123456789): ").strip()
            save_config_key("phone", phone)

        return phone

    def _build_client(self) -> Client | WebClient:
        """Создаёт клиент PyMax."""
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

        extra = ExtraConfig(
            proxy=self.arguments.proxy or get_config_key("proxy"),
            log_level=self.arguments.log_level,
            reconnect=True,
            reconnect_delay=2.0,
        )

        if self.arguments.web:
            return WebClient(
                session_name=self.arguments.session,
                work_dir=str(SESSIONS_DIR),
                extra_config=extra,
            )

        return Client(
            phone=self._get_phone(),
            session_name=self.arguments.session,
            work_dir=str(SESSIONS_DIR),
            extra_config=extra,
        )

    def _badge(self) -> None:
        """Печатает баннер запуска."""
        import pymax

        print(
            BANNER.format(version=version.pretty(), pymax=pymax.__version__),
            flush=True,
        )

    # ------------------------------------------------------------------ #
    #                                 boot                                #
    # ------------------------------------------------------------------ #

    async def _boot(self, client: Client) -> None:
        """Вызывается PyMax после успешного подключения.

        PyMax зовёт ``on_start`` заново после каждого reconnect, поэтому
        полная инициализация выполняется ровно один раз.
        """
        utils.bind_client(client)

        if self._booted:
            logger.info("Reconnected, runtime is already initialised")
            if self.dispatcher is not None:
                self.ready.set()
            return

        logger.info(
            "Logged in as %s (%s)",
            utils.get_display_name(client.me.contact if client.me else None),
            utils.get_me_id(),
        )

        self.db = Database(BASE_DIR / "maxli-db.json")
        await self.db.init()

        self.translator = Translator(self.db)
        await self.translator.init()

        self.modules = Modules(client, self.db, self.translator)
        self.dispatcher = CommandDispatcher(self.modules, client, self.db)

        await self.modules.register_all(core_only=self.arguments.no_modules)

        # Инициализируем сервисные группы логов и бэкапов ДО client_ready модулей
        log_chat_id = None
        try:
            log_chat_id = await utils.get_log_chat(client, self.db)
            await utils.get_backup_chat(client, self.db)
        except Exception as e:
            logger.error("Failed to initialize service chats: %s", e, exc_info=True)

        self.modules.send_config()
        await self.modules.send_ready()

        logger.info(
            "Maxli v%s started: %s modules, %s commands",
            version.pretty(),
            len(self.modules.modules),
            len(self.modules.commands),
        )

        # Отправляем оповещение о запуске в лог-чат
        if log_chat_id:
            try:
                pref = self.db.get("main", "command_prefix", self.db.get("main", "prefix", "."))
                startup_text = (
                    f"🪐 **Maxli v{version.pretty()} успешно запущен!**\n\n"
                    f"📦 **Модулей:** {len(self.modules.modules)}\n"
                    f"⚡️ **Команд:** {len(self.modules.commands)}\n"
                    f"🔑 **Префикс:** {pref}\n"
                    f"⏱ **Время:** {time.strftime('%d.%m.%Y %H:%M:%S')}"
                )
                await client.send_message(log_chat_id, startup_text)
                logger.info("Startup log successfully sent to log chat: %s", log_chat_id)
            except Exception as e:
                logger.error("Failed to send startup log: %s", e, exc_info=True)

        # Флаг ставится только после успешной инициализации: если что-то упало,
        # следующий reconnect честно попробует подняться заново.
        self._booted = True
        self.ready.set()

    def _attach_handlers(self, client: Client) -> None:
        """Вешает обработчики PyMax."""

        @client.on_start()
        async def _on_start(client_: Client) -> None:
            await self._boot(client_)

        @client.on_message()
        async def _on_message(message: Message, client_: Client) -> None:
            if not self.ready.is_set():
                return
            await self.dispatcher.handle_incoming(message, client_)

        @client.on_message_edit()
        async def _on_message_edit(message: Message, client_: Client) -> None:
            if not self.ready.is_set():
                return
            await self.dispatcher.handle_edit(message, client_)

        @client.on_raw()
        async def _on_raw(frame, client_: Client) -> None:
            if not self.ready.is_set():
                return
            await self.dispatcher.handle_raw(frame, client_)

        @client.on_error()
        async def _on_error(exc: Exception, context) -> None:
            logger.exception("Dispatch error in %s", context.event_type, exc_info=exc)

        @client.on_disconnect()
        async def _on_disconnect(exc: Exception, reconnect: bool, delay: float) -> None:
            logger.warning(
                "Disconnected (%s). Reconnect=%s in %ss",
                exc,
                reconnect,
                delay,
            )
            self.ready.clear()

    # ------------------------------------------------------------------ #
    #                                  run                                #
    # ------------------------------------------------------------------ #

    async def amain(self) -> None:
        """Асинхронная точка входа."""
        self.client = self._build_client()
        self._attach_handlers(self.client)

        try:
            await self.client.start()
        finally:
            with contextlib.suppress(Exception):
                await self.client.close()

            if self.db is not None:
                await self.db.close()

    def main(self, argv: list[str] | None = None) -> None:
        """Синхронная точка входа."""
        self.arguments = parse_arguments(argv)

        log.init(self.arguments.log_level)
        self._badge()

        if os.name != "nt" and os.geteuid() == 0 and not self.arguments.root:
            logger.warning(
                "Running as root is not recommended. Pass --root to override."
            )
            sys.exit(1)

        try:
            asyncio.run(self.amain())
        except KeyboardInterrupt:
            logger.info("Interrupted by user")


maxli = Maxli()
