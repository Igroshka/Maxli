"""Валидаторы значений конфига.

Аналог ``heroku/validators.py``, без телеграм-специфики.
Каждый валидатор имеет ``internal_id``, ``validate()`` и ``doc`` — словарь
переводов описания.
"""

from __future__ import annotations

import re
import typing
from urllib.parse import urlparse

ConfigAllowedTypes = typing.Union[list, tuple, set, dict, str, int, float, bool, None]


class ValidationError(Exception):
    """Значение не прошло проверку."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class Validator:
    """База для всех валидаторов."""

    internal_id: str = "Unknown"

    def __init__(
        self,
        validator: typing.Callable[[ConfigAllowedTypes], ConfigAllowedTypes],
        doc: str | dict | None = None,
        internal_id: str | None = None,
    ):
        self.validate = validator
        self.doc = {"en": doc, "ru": doc} if isinstance(doc, str) else (doc or {})
        if internal_id:
            self.internal_id = internal_id


class Boolean(Validator):
    """Логическое значение."""

    def __init__(self):
        super().__init__(
            self._validate,
            {"en": "boolean", "ru": "логическое значение"},
            "Boolean",
        )

    @staticmethod
    def _validate(value: ConfigAllowedTypes, /) -> bool:
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "yes", "on", "1", "да", "вкл"}:
                return True
            if lowered in {"false", "no", "off", "0", "нет", "выкл"}:
                return False
            raise ValidationError(f"Passed value ({value}) is not a boolean")

        if isinstance(value, int):
            return bool(value)

        raise ValidationError(f"Passed value ({value}) is not a boolean")


class Integer(Validator):
    """Целое число с опциональными границами."""

    def __init__(
        self,
        *,
        minimum: int | None = None,
        maximum: int | None = None,
    ):
        self.minimum = minimum
        self.maximum = maximum

        bounds = []
        if minimum is not None:
            bounds.append(f"≥ {minimum}")
        if maximum is not None:
            bounds.append(f"≤ {maximum}")
        suffix = f" ({', '.join(bounds)})" if bounds else ""

        super().__init__(
            self._validate,
            {"en": f"integer{suffix}", "ru": f"целое число{suffix}"},
            "Integer",
        )

    def _validate(self, value: ConfigAllowedTypes, /) -> int:
        try:
            value = int(str(value).strip())
        except (ValueError, TypeError):
            raise ValidationError(f"Passed value ({value}) is not an integer") from None

        if self.minimum is not None and value < self.minimum:
            raise ValidationError(f"Passed value ({value}) is lower than {self.minimum}")

        if self.maximum is not None and value > self.maximum:
            raise ValidationError(f"Passed value ({value}) is greater than {self.maximum}")

        return value


class Float(Validator):
    """Число с плавающей точкой."""

    def __init__(
        self,
        *,
        minimum: float | None = None,
        maximum: float | None = None,
    ):
        self.minimum = minimum
        self.maximum = maximum
        super().__init__(
            self._validate,
            {"en": "float", "ru": "дробное число"},
            "Float",
        )

    def _validate(self, value: ConfigAllowedTypes, /) -> float:
        try:
            value = float(str(value).strip())
        except (ValueError, TypeError):
            raise ValidationError(f"Passed value ({value}) is not a float") from None

        if self.minimum is not None and value < self.minimum:
            raise ValidationError(f"Passed value ({value}) is lower than {self.minimum}")

        if self.maximum is not None and value > self.maximum:
            raise ValidationError(f"Passed value ({value}) is greater than {self.maximum}")

        return value


class String(Validator):
    """Строка с ограничением длины."""

    def __init__(self, length: int | None = None, *, min_length: int | None = None):
        self.length = length
        self.min_length = min_length
        doc = f"string (max {length} chars)" if length else "string"
        super().__init__(
            self._validate,
            {"en": doc, "ru": doc.replace("string", "строка")},
            "String",
        )

    def _validate(self, value: ConfigAllowedTypes, /) -> str:
        value = str(value)

        if self.length is not None and len(value) > self.length:
            raise ValidationError(f"Passed value is longer than {self.length} characters")

        if self.min_length is not None and len(value) < self.min_length:
            raise ValidationError(f"Passed value is shorter than {self.min_length} characters")

        return value


class Choice(Validator):
    """Одно значение из списка допустимых."""

    def __init__(self, possible_values: typing.Iterable[ConfigAllowedTypes]):
        self.possible_values = list(possible_values)
        super().__init__(
            self._validate,
            {
                "en": f"one of {self.possible_values}",
                "ru": f"одно из {self.possible_values}",
            },
            "Choice",
        )

    def _validate(self, value: ConfigAllowedTypes, /) -> ConfigAllowedTypes:
        if value not in self.possible_values:
            raise ValidationError(
                f"Passed value ({value}) is not one of {self.possible_values}"
            )
        return value


class MultiChoice(Validator):
    """Несколько значений из списка допустимых."""

    def __init__(self, possible_values: typing.Iterable[ConfigAllowedTypes]):
        self.possible_values = list(possible_values)
        super().__init__(
            self._validate,
            {
                "en": f"multiple of {self.possible_values}",
                "ru": f"несколько из {self.possible_values}",
            },
            "MultiChoice",
        )

    def _validate(self, value: ConfigAllowedTypes, /) -> list:
        if not isinstance(value, (list, tuple, set)):
            value = [value]

        for item in value:
            if item not in self.possible_values:
                raise ValidationError(
                    f"Passed value ({item}) is not one of {self.possible_values}"
                )

        return list(value)


class Series(Validator):
    """Список значений, каждое из которых проверяется вложенным валидатором."""

    def __init__(
        self,
        validator: Validator | None = None,
        *,
        min_len: int | None = None,
        max_len: int | None = None,
        fixed_len: int | None = None,
    ):
        self.validator = validator
        self.min_len = min_len
        self.max_len = max_len
        self.fixed_len = fixed_len
        super().__init__(
            self._validate,
            {"en": "list of values", "ru": "список значений"},
            "Series",
        )

    def _validate(self, value: ConfigAllowedTypes, /) -> list:
        if isinstance(value, str):
            value = [item.strip() for item in value.split(",") if item.strip()]
        elif isinstance(value, (tuple, set)):
            value = list(value)
        elif not isinstance(value, list):
            # Одиночное значение — это список из одного элемента. Строку с
            # запятыми ConfigValue успевает превратить в число или кортеж
            # через literal_eval, поэтому сюда приходит уже не str.
            value = [value]

        if self.fixed_len is not None and len(value) != self.fixed_len:
            raise ValidationError(f"List must contain exactly {self.fixed_len} items")

        if self.min_len is not None and len(value) < self.min_len:
            raise ValidationError(f"List must contain at least {self.min_len} items")

        if self.max_len is not None and len(value) > self.max_len:
            raise ValidationError(f"List must contain at most {self.max_len} items")

        if self.validator is not None:
            value = [self.validator.validate(item) for item in value]

        return value


class Link(Validator):
    """Одна http(s)-ссылка."""

    def __init__(self):
        super().__init__(
            self._validate,
            {"en": "link", "ru": "ссылка"},
            "Link",
        )

    @staticmethod
    def _validate(value: ConfigAllowedTypes, /) -> str:
        value = str(value)
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValidationError(f"Passed value ({value}) is not a valid URL")
        return value


class RandomLinkList(list):
    """Список ссылок, который при обращении отдаёт случайную."""

    def __str__(self) -> str:
        import random

        return random.choice(self) if self else ""

    def __repr__(self) -> str:
        return f"RandomLinkList({list.__repr__(self)})"


class RandomLink(Series):
    """Список ссылок; используется случайная при каждом обращении."""

    def __init__(self):
        super().__init__(Link())
        self.internal_id = "RandomLink"
        self.doc = {"en": "list of links", "ru": "список ссылок"}
        self.validate = self._validate_links

    def _validate_links(self, value: ConfigAllowedTypes, /) -> RandomLinkList:
        return RandomLinkList(Series._validate(self, value))


class RegExp(Validator):
    """Строка, соответствующая регулярному выражению."""

    def __init__(self, regex: str, flags: int = 0, description: str | None = None):
        self.regex = regex
        self.flags = flags
        try:
            re.compile(regex, flags=flags)
        except re.error as e:
            raise ValueError(f"{regex} is not a valid regex") from e

        super().__init__(
            self._validate,
            {
                "en": description or f"string matching {regex}",
                "ru": description or f"строка по шаблону {regex}",
            },
            "RegExp",
        )

    def _validate(self, value: ConfigAllowedTypes, /) -> str:
        value = str(value)
        if not re.match(self.regex, value, flags=self.flags):
            raise ValidationError(f"Passed value ({value}) does not match {self.regex}")
        return value


class MaxID(Validator):
    """ID пользователя или чата MAX."""

    def __init__(self):
        super().__init__(
            self._validate,
            {"en": "MAX ID", "ru": "ID в MAX"},
            "MaxID",
        )

    @staticmethod
    def _validate(value: ConfigAllowedTypes, /) -> int:
        try:
            return int(str(value).strip())
        except (ValueError, TypeError):
            raise ValidationError(f"Passed value ({value}) is not a valid MAX ID") from None


class Hidden(Validator):
    """Скрытое значение (пароли, токены) — не показывается в .config."""

    def __init__(self, validator: Validator | None = None):
        self._inner = validator or String()
        super().__init__(
            self._validate,
            self._inner.doc,
            "Hidden",
        )

    def _validate(self, value: ConfigAllowedTypes, /) -> ConfigAllowedTypes:
        return self._inner.validate(value)


class NoneType(Validator):
    """Всегда ``None``."""

    def __init__(self):
        super().__init__(
            lambda _: None,
            {"en": "empty value", "ru": "пустое значение"},
            "NoneType",
        )


class Union(Validator):
    """Значение, подходящее хотя бы под один из валидаторов."""

    def __init__(self, *validators: Validator):
        self.validators = validators
        super().__init__(
            self._validate,
            {
                "en": " or ".join(v.doc.get("en", v.internal_id) for v in validators),
                "ru": " или ".join(v.doc.get("ru", v.internal_id) for v in validators),
            },
            "Union",
        )

    def _validate(self, value: ConfigAllowedTypes, /) -> ConfigAllowedTypes:
        for validator in self.validators:
            try:
                return validator.validate(value)
            except ValidationError:
                continue

        raise ValidationError(f"Passed value ({value}) is not valid")


class Emoji(Validator):
    """Одна или несколько эмодзи."""

    _PATTERN = re.compile(
        "[\U0001f000-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff]+"
    )

    def __init__(self, length: int | None = None):
        self.length = length
        super().__init__(
            self._validate,
            {"en": "emoji", "ru": "эмодзи"},
            "Emoji",
        )

    def _validate(self, value: ConfigAllowedTypes, /) -> str:
        value = str(value)
        if not self._PATTERN.fullmatch(value):
            raise ValidationError(f"Passed value ({value}) is not an emoji")

        if self.length is not None and len(value) != self.length:
            raise ValidationError(f"Passed value must contain {self.length} emoji")

        return value
