"""Базовые типы Maxli.

Аналог ``heroku/types.py``: класс :class:`Module`, конфигурация модулей,
исключения загрузки и интроспекция команд/вотчеров.
"""

from __future__ import annotations

import ast
import asyncio
import collections
import contextlib
import inspect
import logging
import typing
from dataclasses import dataclass, field
from importlib.abc import SourceLoader

from pymax import Message

logger = logging.getLogger(__name__)

JSONSerializable = typing.Union[str, int, float, bool, list, dict, None]
Command = typing.Callable[..., typing.Awaitable[typing.Any]]


# --------------------------------------------------------------------------- #
#                                   loader                                     #
# --------------------------------------------------------------------------- #


class StringLoader(SourceLoader):
    """Загружает модуль из строки, а не из файла."""

    def __init__(self, data: str, origin: str):
        self.data = data.encode("utf-8") if isinstance(data, str) else data
        self.origin = origin

    def get_source(self, _=None) -> str:
        return self.data.decode("utf-8")

    def get_code(self, fullname: str):
        source = self.get_source()
        if source is None:
            return None
        return compile(source, self.origin, "exec", dont_inherit=True)

    def get_filename(self, *args, **kwargs) -> str:
        return self.origin

    def get_data(self, *args, **kwargs) -> bytes:
        return self.data


# --------------------------------------------------------------------------- #
#                                  exceptions                                  #
# --------------------------------------------------------------------------- #


class LoadError(Exception):
    """Модуль сообщает, что не может быть загружен."""

    def __init__(self, error_message: str):  # skipcq: PYL-W0231
        self._error_message = error_message

    def __str__(self) -> str:
        return self._error_message


class CoreOverwriteError(LoadError):
    """Попытка перезаписать системный модуль или команду."""

    def __init__(self, module: str | None = None, command: str | None = None):
        self.module = module
        self.command = command
        super().__init__(str(self))

    def __str__(self) -> str:
        if self.command:
            return f"Command {self.command} is a core command and can't be overwritten"
        return f"Module {self.module} is a core module and can't be overwritten"


class CoreUnloadError(Exception):
    """Попытка выгрузить системный модуль."""

    def __init__(self, module: str):
        self.module = module

    def __str__(self) -> str:
        return f"Module {self.module} is core and can't be unloaded"


class SelfUnload(Exception):
    """Модуль просит выгрузить себя."""

    def __init__(self, error_message: str = ""):  # skipcq: PYL-W0231
        self._error_message = error_message

    def __str__(self) -> str:
        return self._error_message


class SelfSuspend(Exception):
    """Модуль просит приостановить загрузку без вывода ошибки."""

    def __init__(self, error_message: str = ""):  # skipcq: PYL-W0231
        self._error_message = error_message

    def __str__(self) -> str:
        return self._error_message


class StopLoop(Exception):
    """Останавливает ``InfiniteLoop``."""


# --------------------------------------------------------------------------- #
#                                    config                                    #
# --------------------------------------------------------------------------- #


class _Placeholder:
    """Маркер «значение не задано»."""


async def _wrap(func: typing.Callable[[], typing.Awaitable]) -> typing.Any:
    with contextlib.suppress(Exception):
        return await func()


def _syncwrap(func: typing.Callable[[], typing.Any]) -> typing.Any:
    with contextlib.suppress(Exception):
        return func()


@dataclass(repr=True)
class ConfigValue:
    """Одна настройка модуля."""

    option: str
    default: typing.Any = None
    doc: typing.Union[typing.Callable[[], str], str] = "No description"
    value: typing.Any = field(default_factory=_Placeholder)
    validator: typing.Any = None
    on_change: typing.Any = None

    def __post_init__(self):
        if isinstance(self.value, _Placeholder):
            self.value = self.default

    def set_no_raise(self, value: typing.Any) -> bool:
        """Устанавливает значение, не бросая ``ValidationError``."""
        return self.__setattr__("value", value, ignore_validation=True)

    def __setattr__(self, key: str, value: typing.Any, *, ignore_validation: bool = False):
        if key == "value":
            with contextlib.suppress(Exception):
                value = ast.literal_eval(value)

            if isinstance(value, (set, tuple)):
                value = list(value)

            if isinstance(value, list):
                value = [item.strip() if isinstance(item, str) else item for item in value]

            if self.validator is not None:
                from . import validators

                if value is not None:
                    try:
                        value = self.validator.validate(value)
                    except validators.ValidationError:
                        if not ignore_validation:
                            raise

                        logger.debug(
                            "Config value %s is broken, resetting to %s",
                            self.option,
                            self.default,
                        )
                        value = self.default
                else:
                    fallbacks = {
                        "String": "",
                        "Integer": 0,
                        "Boolean": False,
                        "Series": [],
                        "Float": 0.0,
                    }
                    value = fallbacks.get(self.validator.internal_id, None)

            self._save_marker = True

        object.__setattr__(self, key, value)

        if key == "value" and not ignore_validation and callable(self.on_change):
            if inspect.iscoroutinefunction(self.on_change):
                asyncio.ensure_future(_wrap(self.on_change))
            else:
                _syncwrap(self.on_change)


class ConfigCategory(list):
    """Группа настроек, отображаемая одним блоком в ``.config``."""

    def __init__(
        self,
        name: str,
        *config_values: ConfigValue,
        doc: typing.Union[typing.Callable[[], str], str] = "No description",
    ):
        super().__init__(config_values)
        self.name = str(name)
        self.doc = doc

    def getdoc(self) -> str:
        """Описание категории."""
        if callable(self.doc):
            with contextlib.suppress(Exception):
                return self.doc()
            return "No description"
        return self.doc


class ModuleConfig(dict):
    """Конфиг модуля.

    Принимает либо новый формат (:class:`ConfigValue` / :class:`ConfigCategory`),
    либо legacy-тройки ``"key", default, "doc"``.
    """

    def __init__(self, *entries: typing.Union[str, ConfigValue, ConfigCategory]):
        self._option_categories: dict[str, str] = {}
        self._categories: dict[str, ConfigCategory] = {}

        if entries and all(
            isinstance(entry, (ConfigValue, ConfigCategory)) for entry in entries
        ):
            self._config = {}
            for entry in entries:
                if isinstance(entry, ConfigCategory):
                    self._categories[entry.name] = entry
                    for cv in entry:
                        self._config[cv.option] = cv
                        self._option_categories[cv.option] = entry.name
                else:
                    self._config[entry.option] = entry
        else:
            keys, defaults, docstrings = [], [], []
            for i, entry in enumerate(entries):
                if i % 3 == 0:
                    keys.append(entry)
                elif i % 3 == 1:
                    defaults.append(entry)
                else:
                    docstrings.append(entry)

            self._config = {
                key: ConfigValue(option=key, default=default, doc=doc)
                for key, default, doc in zip(keys, defaults, docstrings)
            }

        super().__init__({option: cv.value for option, cv in self._config.items()})

    def getdoc(self, key: str, message: Message | None = None) -> str:
        """Описание настройки."""
        ret = self._config[key].doc

        if callable(ret):
            try:
                ret = ret(message)
            except Exception:
                ret = ret()

        return ret

    def getdef(self, key: str) -> typing.Any:
        """Значение настройки по умолчанию."""
        return self._config[key].default

    def get_category(self, key: str) -> ConfigCategory | None:
        """Категория, к которой относится настройка."""
        name = self._option_categories.get(key)
        return self._categories.get(name) if name else None

    def grouped_options(self) -> collections.OrderedDict:
        """Настройки, сгруппированные по категориям."""
        result: collections.OrderedDict = collections.OrderedDict()
        for option in self._config:
            result.setdefault(self._option_categories.get(option), []).append(option)
        return result

    def __setitem__(self, key: str, value: typing.Any) -> None:
        self._config[key].value = value
        # В dict кладём уже провалидированное значение — именно оно уходит в БД
        super().__setitem__(key, self._config[key].value)

    def set_no_raise(self, key: str, value: typing.Any) -> None:
        """Записывает значение, игнорируя ошибки валидации."""
        self._config[key].set_no_raise(value)
        super().__setitem__(key, self._config[key].value)

    def __getitem__(self, key: str) -> typing.Any:
        try:
            return self._config[key].value
        except KeyError:
            return None

    def reload(self) -> None:
        """Синхронизирует dict-представление со значениями ``ConfigValue``."""
        for key in self._config:
            super().__setitem__(key, self._config[key].value)

    def change_validator(self, key: str, validator) -> None:
        """Меняет валидатор настройки на лету."""
        self._config[key].validator = validator


LibraryConfig = ModuleConfig


# --------------------------------------------------------------------------- #
#                                introspection                                 #
# --------------------------------------------------------------------------- #


def _get_members(
    mod: "Module",
    ending: str,
    attribute: str | None = None,
    strict: bool = False,
) -> dict:
    """Собирает методы модуля, чьё имя оканчивается на ``ending``."""
    return {
        (
            method_name.rsplit(ending, maxsplit=1)[0] or method_name
            if (method_name == ending if strict else method_name.endswith(ending))
            else method_name
        ).lower(): getattr(mod, method_name)
        for method_name in dir(mod)
        if not isinstance(getattr(type(mod), method_name, None), property)
        and callable(getattr(mod, method_name, None))
        and (
            (method_name == ending if strict else method_name.endswith(ending))
            or (attribute and getattr(getattr(mod, method_name), attribute, False))
        )
    }


def get_commands(mod: "Module") -> dict:
    """Команды модуля (методы ``*cmd``)."""
    return _get_members(mod, "cmd", "is_command")


def get_watchers(mod: "Module") -> dict:
    """Вотчеры модуля (метод ``watcher``)."""
    return _get_members(mod, "watcher", "is_watcher", strict=True)


def get_raw_handlers(mod: "Module") -> dict:
    """Обработчики сырых событий (методы ``*_raw_handler``)."""
    return _get_members(mod, "_raw_handler", "is_raw_handler")


# --------------------------------------------------------------------------- #
#                                    module                                    #
# --------------------------------------------------------------------------- #


class Module:
    """Базовый класс модуля Maxli."""

    strings = {"name": "Unknown"}

    #: Заполняется загрузчиком.
    allmodules: typing.Any = None
    config: ModuleConfig | None = None
    name: str = "Unknown"

    def config_complete(self) -> None:
        """Вызывается после того, как ``self.config`` заполнен из БД."""

    async def client_ready(self) -> None:
        """Вызывается после того, как клиент MAX готов к работе."""

    async def on_unload(self) -> None:
        """Вызывается при выгрузке или перезагрузке модуля."""

    async def on_dlmod(self) -> None:
        """Вызывается при первой загрузке модуля через ``.dlmod``/``.loadmod``."""

    def internal_init(self) -> None:
        """Инъекция зависимостей. Не вызывайте вручную."""
        self.db = self.allmodules.db
        self._db = self.allmodules.db
        self.client = self.allmodules.client
        self._client = self.allmodules.client
        self.lookup = self.allmodules.lookup
        self.get_prefix = self.allmodules.get_prefix
        self.get_prefixes = self.allmodules.get_prefixes
        self.max_id = getattr(self.allmodules, "max_id", None)
        self._max_id = self.max_id
        self.tr = self.allmodules.translator

    # ------------------------------------------------------------------ #
    #                              db helpers                             #
    # ------------------------------------------------------------------ #

    def get(self, key: str, default: JSONSerializable = None) -> JSONSerializable:
        """Читает значение из БД в namespace модуля."""
        return self._db.get(self.__class__.__name__, key, default)

    def set(self, key: str, value: JSONSerializable) -> bool:
        """Пишет значение в БД в namespace модуля."""
        return self._db.set(self.__class__.__name__, key, value)

    def pointer(
        self,
        key: str,
        default: JSONSerializable = None,
        item_type: typing.Any = None,
    ) -> typing.Any:
        """Возвращает самосохраняющийся указатель на значение в БД."""
        return self._db.pointer(self.__class__.__name__, key, default, item_type)

    # ------------------------------------------------------------------ #
    #                             introspection                           #
    # ------------------------------------------------------------------ #

    @property
    def commands(self) -> dict[str, Command]:
        """Команды, которые поддерживает модуль."""
        return get_commands(self)

    @commands.setter
    def commands(self, _):
        pass

    @property
    def watchers(self) -> dict[str, Command]:
        """Вотчеры модуля."""
        return get_watchers(self)

    @watchers.setter
    def watchers(self, _):
        pass

    @property
    def raw_handlers(self) -> dict[str, Command]:
        """Обработчики сырых событий модуля."""
        return get_raw_handlers(self)

    @raw_handlers.setter
    def raw_handlers(self, _):
        pass

    # ------------------------------------------------------------------ #
    #                                 misc                                #
    # ------------------------------------------------------------------ #

    async def invoke(
        self,
        command: str,
        args: str = "",
        message: Message | None = None,
        chat_id: int | None = None,
    ) -> Message | None:
        """Вызывает другую команду юзербота."""
        if command not in self.allmodules.commands:
            raise ValueError(f"Command {command} not found")

        if message is None and chat_id is None:
            raise ValueError("Either message or chat_id must be specified")

        text = f"{self.get_prefix()}{command} {args}".strip()

        if message is not None:
            sent = await message.answer(text)
        else:
            sent = await self._client.send_message(chat_id, text)

        if sent is not None:
            await self.allmodules.commands[command](sent)

        return sent

    async def animate(
        self,
        message: Message,
        frames: list[str],
        interval: float = 0.5,
    ) -> Message:
        """Проигрывает анимацию, редактируя сообщение."""
        from . import utils

        interval = max(interval, 0.3)

        for frame in frames:
            message = await utils.answer(message, frame) or message
            await asyncio.sleep(interval)

        return message


class Library:
    """Базовый класс библиотеки — переиспользуемого кода без команд."""

    name: str = "Unknown"
    allmodules: typing.Any = None

    def internal_init(self) -> None:
        """Инъекция зависимостей библиотеки."""
        self.db = self.allmodules.db
        self._db = self.allmodules.db
        self.client = self.allmodules.client
        self._client = self.allmodules.client
        self.lookup = self.allmodules.lookup

    async def init(self) -> None:
        """Вызывается после подключения библиотеки."""

    async def on_lib_update(self, *args, **kwargs) -> None:
        """Вызывается при обновлении библиотеки."""

    def _lib_get(self, key: str, default: JSONSerializable = None) -> JSONSerializable:
        return self._db.get(f"__lib__{self.__class__.__name__}", key, default)

    def _lib_set(self, key: str, value: JSONSerializable) -> bool:
        return self._db.set(f"__lib__{self.__class__.__name__}", key, value)

    def _lib_pointer(self, key: str, default: JSONSerializable = None) -> typing.Any:
        return self._db.pointer(f"__lib__{self.__class__.__name__}", key, default)
