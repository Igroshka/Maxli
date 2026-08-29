"""Логирование Maxli.

Аналог ``heroku/log.py``: кольцевой буфер последних записей + вывод в консоль
и в файл. Буфер используется командой ``.logs``.
"""

from __future__ import annotations

import collections
import logging
import logging.handlers
import sys
from pathlib import Path

from . import utils

FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
DATE_FORMAT = "%H:%M:%S"

LEVELS = {
    "CRITICAL": 50,
    "ERROR": 40,
    "WARNING": 30,
    "INFO": 20,
    "DEBUG": 10,
    "ALL": 0,
}


class MaxliException(Exception):
    """Исключение с приложенным контекстом для красивого вывода."""

    def __init__(
        self,
        message: str,
        local_vars: str = "",
        full_stack: str = "",
        sysinfo: tuple | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.local_vars = local_vars
        self.full_stack = full_stack
        self.sysinfo = sysinfo

    @classmethod
    def from_exc_info(cls, exc_type, exc_value, tb, stack: str = "") -> "MaxliException":
        """Собирает исключение из ``sys.exc_info()``."""
        import traceback

        full_stack = "".join(traceback.format_exception(exc_type, exc_value, tb))
        local_vars = ""

        frame = tb
        while frame and frame.tb_next:
            frame = frame.tb_next

        if frame:
            local_vars = "\n".join(
                f"{name} = {value!r}" for name, value in frame.tb_frame.f_locals.items()
            )

        return cls(
            message=f"{exc_type.__name__}: {exc_value}",
            local_vars=utils.smart_truncate(local_vars, 2000),
            full_stack=stack + full_stack,
            sysinfo=(exc_type, exc_value, tb),
        )


class MemoryHandler(logging.Handler):
    """Держит последние ``capacity`` записей в памяти."""

    def __init__(self, capacity: int = 2000):
        super().__init__(0)
        self.buffer: collections.deque = collections.deque(maxlen=capacity)
        self.setFormatter(logging.Formatter(FORMAT, datefmt=DATE_FORMAT))

    def emit(self, record: logging.LogRecord) -> None:
        self.buffer.append(record)

    def dumps(self, level: int = 0, named: bool = False) -> list[str]:
        """Отдаёт отформатированные записи не ниже уровня ``level``."""
        return [
            self.format(record)
            for record in list(self.buffer)
            if record.levelno >= level and (not named or record.name)
        ]

    def clear(self) -> None:
        """Очищает буфер."""
        self.buffer.clear()


_memory_handler: MemoryHandler | None = None


def get_memory_handler() -> MemoryHandler:
    """Возвращает активный буфер логов."""
    if _memory_handler is None:
        raise RuntimeError("Logging is not initialised yet")
    return _memory_handler


def init(level: str | int = "INFO", log_file: str | Path | None = None) -> MemoryHandler:
    """Настраивает логирование юзербота."""
    global _memory_handler

    if isinstance(level, str):
        level = LEVELS.get(level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(0)

    for handler in root.handlers.copy():
        root.removeHandler(handler)

    formatter = logging.Formatter(FORMAT, datefmt=DATE_FORMAT)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    stream = logging.StreamHandler(sys.stdout)
    stream.setLevel(level)
    stream.setFormatter(formatter)
    root.addHandler(stream)

    _memory_handler = MemoryHandler()
    root.addHandler(_memory_handler)

    path = Path(log_file or utils.relative_path("maxli.log"))
    file_handler = logging.handlers.RotatingFileHandler(
        path,
        maxBytes=2 * 1024 * 1024,
        backupCount=2,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    for noisy in ("pymax", "websockets", "aiohttp", "asyncio"):
        logging.getLogger(noisy).setLevel(max(level, logging.WARNING))

    sys.excepthook = _excepthook
    return _memory_handler


def _excepthook(exc_type, exc_value, tb) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, tb)
        return

    logging.getLogger("maxli").critical(
        "Unhandled exception",
        exc_info=(exc_type, exc_value, tb),
    )
