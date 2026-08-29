"""Переводы Maxli.

Аналог ``heroku/translations.py``. Langpack — YAML/JSON-файл вида::

    maxli.modules.help.name: "Help"
    maxli.modules.help.no_mod: "Модуль не найден"

Модуль получает доступ к строкам через ``self.strings["key"]``.
"""

from __future__ import annotations

import json
import logging
import typing
from pathlib import Path

logger = logging.getLogger(__name__)

PACKS = Path(__file__).parent / "langpacks"
SUPPORTED_LANGUAGES = ("en", "ru")
LANGUAGE_ALIASES = {"рус": "ru", "русский": "ru", "eng": "en", "english": "en"}

DEFAULT_PREFIX = "maxli.modules."


def normalize_language(language: str) -> str:
    """Приводит название языка к коду."""
    language = (language or "en").strip().lower()
    return LANGUAGE_ALIASES.get(language, language)


def get_language_pack_path(language: str) -> Path | None:
    """Ищет файл langpack-а по коду языка."""
    for suffix in (".yml", ".yaml", ".json"):
        path = PACKS / f"{normalize_language(language)}{suffix}"
        if path.exists():
            return path
    return None


def fmt(text: str, kwargs: dict) -> str:
    """Подставляет ``{key}`` в строку, не падая на лишних скобках."""
    for key, value in kwargs.items():
        placeholder = "{" + str(key) + "}"
        if placeholder in text:
            text = text.replace(placeholder, str(value))
    return text


def _load_pack(path: Path) -> dict:
    """Читает langpack из YAML или JSON."""
    raw = path.read_text(encoding="utf-8")

    if path.suffix == ".json":
        return json.loads(raw)

    try:
        import yaml
    except ImportError:
        logger.error("PyYAML is not installed, cannot read %s", path)
        return {}

    return yaml.safe_load(raw) or {}


class BaseTranslator:
    """Общая логика доступа к загруженным строкам."""

    _data: dict

    def getkey(self, key: str) -> typing.Any:
        """Возвращает строку по полному ключу или ``False``."""
        return self._data.get(key, False)

    def gettext(self, text: str) -> str:
        """Возвращает перевод или исходный текст."""
        return self.getkey(text) or text


class Translator(BaseTranslator):
    """Активный переводчик юзербота."""

    def __init__(self, db):
        self.db = db
        self._data: dict = {}
        self.raw_data: dict[str, dict] = {}
        self._language = "ru"

    async def init(self) -> bool:
        """Загружает базовый (en) и выбранный пользователем langpack."""
        base = get_language_pack_path("en")
        self._data = _load_pack(base) if base else {}
        self.raw_data["en"] = dict(self._data)

        language = normalize_language(self.db.get(__name__, "lang", "ru"))
        self._language = language

        if language == "en":
            return True

        path = get_language_pack_path(language)
        if path is None:
            logger.warning("Language pack %s not found, falling back to en", language)
            return False

        pack = _load_pack(path)
        self.raw_data[language] = pack
        self._data.update(pack)
        logger.debug("Loaded language pack %s (%s keys)", language, len(pack))
        return True

    @property
    def language(self) -> str:
        """Текущий язык (закэширован, чтобы не читать БД на каждую строку)."""
        return self._language

    async def set_language(self, language: str) -> bool:
        """Меняет язык и перезагружает строки."""
        language = normalize_language(language)
        if get_language_pack_path(language) is None:
            return False

        self.db.set(__name__, "lang", language)
        return await self.init()


class Strings:
    """Обёртка над ``module.strings``, которую модуль получает как ``self.strings``."""

    def __init__(self, mod, translator: Translator | None = None):
        self._mod = mod
        self._translator = translator

    @property
    def _base_strings(self) -> dict:
        # Читаем именно атрибут класса: у экземпляра ``strings`` уже подменён
        # на этот объект, и обращение к нему привело бы к рекурсии.
        return getattr(type(self._mod), "strings", {}) or {}

    def _full_key(self, key: str) -> str:
        return f"{self._mod.__class__.__module__}.{key}"

    def get(self, key: str, default: str | None = None) -> str:
        """Как ``dict.get``: строка или ``default``, если ключа нет нигде."""
        if key in self._base_strings or (
            self._translator and self._translator.getkey(self._full_key(key))
        ):
            return self[key]

        return default if default is not None else self[key]

    def get_lang(self, key: str, language: str) -> str:
        """Строка на конкретном языке."""
        if self._translator:
            pack = self._translator.raw_data.get(normalize_language(language), {})
            if (value := pack.get(self._full_key(key))) is not None:
                return value

        return self[key]

    def __getitem__(self, key: str) -> str:
        if self._translator:
            translated = self._translator.getkey(self._full_key(key))
            if translated:
                return translated

        language = self._translator.language if self._translator else "ru"
        localized = getattr(self._mod, f"strings_{language}", None)
        if isinstance(localized, dict) and key in localized:
            return localized[key]

        return self._base_strings.get(key, f"#{key}")

    def __call__(self, key: str, _: typing.Any = None) -> str:
        return self[key]

    def __contains__(self, key: str) -> bool:
        return key in self._base_strings

    def __iter__(self):
        return iter(self._base_strings)

    def format(self, key: str, **kwargs) -> str:
        """Строка с подстановкой значений."""
        return fmt(self[key], kwargs)
