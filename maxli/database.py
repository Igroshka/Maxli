"""База данных Maxli.

Аналог ``heroku/database.py``: ``dict``-подобное хранилище с namespace-ами по
владельцу (``owner`` — обычно ``__name__`` модуля). В отличие от Heroku,
бэкапа в облако нет — данные лежат в JSON-файле рядом с юзерботом.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import typing
from pathlib import Path

from . import utils
from .pointers import PointerDict, PointerList, PointerSet

logger = logging.getLogger(__name__)

JSONSerializable = typing.Union[str, int, float, bool, list, dict, None]


class Database(dict):
    """Хранилище настроек юзербота и модулей."""

    #: Пауза перед записью на диск, чтобы не переписывать файл на каждый ``set``.
    SAVE_DELAY = 1.0

    def __init__(self, path: str | Path | None = None):
        super().__init__()
        self._path = Path(path or utils.relative_path("maxli-db.json"))
        self._saving = False
        self._save_task: asyncio.Task | None = None

    def __repr__(self) -> str:
        return f"Database({self._path}, {len(self)} owners)"

    # ------------------------------------------------------------------ #
    #                              lifecycle                              #
    # ------------------------------------------------------------------ #

    async def init(self) -> None:
        """Загружает базу с диска."""
        self.read()

    def read(self) -> dict:
        """Читает JSON-файл в память."""
        if not self._path.exists():
            logger.debug("Database file %s does not exist, starting empty", self._path)
            return self

        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.error("Database is corrupted, backing it up and starting fresh")
            self._backup_corrupted()
            return self
        except OSError as e:
            logger.error("Cannot read database: %s", e)
            return self

        if not isinstance(data, dict):
            logger.error("Database root is not an object, ignoring")
            return self

        self.clear()
        self.update(data)
        logger.debug("Loaded database with %s owners", len(self))
        return self

    def _backup_corrupted(self) -> None:
        broken = self._path.with_suffix(".json.broken")
        try:
            os.replace(self._path, broken)
            logger.warning("Corrupted database moved to %s", broken)
        except OSError:
            logger.exception("Failed to back up corrupted database")

    def save(self) -> bool:
        """Атомарно записывает базу на диск."""
        if self._saving:
            return True

        self._saving = True
        tmp = self._path.with_suffix(".json.tmp")

        try:
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(
                json.dumps(self, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            os.replace(tmp, self._path)
        except Exception:
            logger.exception("Database save failed")
            return False
        finally:
            self._saving = False

        return True

    def schedule_save(self) -> bool:
        """Откладывает запись на ``SAVE_DELAY`` секунд.

        Если event loop не запущен (старт, shutdown) — пишет сразу.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return self.save()

        if self._save_task and not self._save_task.done():
            return True

        async def _delayed() -> None:
            await asyncio.sleep(self.SAVE_DELAY)
            self.save()

        self._save_task = loop.create_task(_delayed())
        return True

    async def close(self) -> None:
        """Дописывает отложенные изменения перед выходом."""
        if self._save_task and not self._save_task.done():
            self._save_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._save_task

        self.save()

    # ------------------------------------------------------------------ #
    #                                access                               #
    # ------------------------------------------------------------------ #

    def get(
        self,
        owner: str,
        key: str,
        default: JSONSerializable = None,
    ) -> JSONSerializable:
        """Возвращает значение ``key`` из namespace ``owner``."""
        try:
            return super().__getitem__(owner)[key]
        except KeyError:
            return default

    def set(self, owner: str, key: str, value: JSONSerializable) -> bool:
        """Записывает значение и сохраняет базу."""
        if not utils_is_serializable(value):
            raise RuntimeError(f"Value {value!r} is not JSON-serializable")

        super().setdefault(owner, {})[key] = value
        return self.schedule_save()

    def unset(self, owner: str, key: str) -> bool:
        """Удаляет значение."""
        try:
            del super().__getitem__(owner)[key]
        except KeyError:
            return False
        return self.schedule_save()

    def pointer(
        self,
        owner: str,
        key: str,
        default: JSONSerializable = None,
        item_type: typing.Any = None,
    ) -> PointerList | PointerDict | PointerSet | JSONSerializable:
        """Возвращает указатель на значение в базе.

        Если значение — список, словарь или множество, вернётся объект, который
        сам пишет изменения в базу.
        """
        value = self.get(owner, key, default)
        mapping = {list: PointerList, dict: PointerDict, set: PointerSet}

        pointer_cls = mapping.get(item_type or type(value))
        if pointer_cls is None:
            return value

        return pointer_cls(self, owner, key, default)

    def __setitem__(self, owner: str, value: JSONSerializable) -> None:
        super().__setitem__(owner, value)
        self.schedule_save()

    def __delitem__(self, owner: str) -> None:
        super().__delitem__(owner)
        self.schedule_save()

    def update(self, *args, **kwargs) -> None:  # noqa: D102
        super().update(*args, **kwargs)


def utils_is_serializable(value: typing.Any) -> bool:
    """Проверяет, что значение можно положить в JSON."""
    try:
        json.dumps(value, default=str)
    except (TypeError, ValueError):
        return False
    return True
