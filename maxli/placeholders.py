# ©️ Maxli, 2026
# This file is a part of Maxli Userbot
# 🌐 https://github.com/Igroshka/Maxli
# Архитектура повторяет Heroku Userbot (AGPLv3)

from __future__ import annotations

import inspect
import logging
import typing

logger = logging.getLogger(__name__)

custom_placeholders: dict[str, dict[str, typing.Any]] = {}


def register_placeholder(
    placeholder: str,
    callback: typing.Callable,
    description: str | None = None,
) -> bool:
    """Регистрирует кастомный плейсхолдер от модуля."""
    owner_cls = getattr(getattr(callback, "__self__", None), "__class__", None)
    module_name = owner_cls.__name__ if owner_cls else "core"
    module_instance = getattr(callback, "__self__", None)

    custom_placeholders[placeholder] = {
        "module_name": module_name,
        "module_instance": module_instance,
        "callback": callback,
        "description": description,
        "placeholder_name": placeholder,
    }
    logger.debug("Registered placeholder {%s} from %s", placeholder, module_name)
    return True


async def get_placeholder(placeholder: str, data: dict | None = None) -> str:
    """Вычисляет и возвращает значение плейсхолдера."""
    if placeholder not in custom_placeholders:
        return ""

    callback = custom_placeholders[placeholder]["callback"]
    try:
        if inspect.iscoroutinefunction(callback):
            try:
                res = await callback(data)
            except TypeError:
                res = await callback()
        else:
            try:
                res = callback(data)
            except TypeError:
                res = callback()
        return str(res)
    except Exception:
        logger.exception("Error evaluating placeholder {%s}", placeholder)
        return ""


async def get_placeholders(data: dict, custom_message: str | None) -> dict:
    """Заполняет словарь `data` значениями всех найденных в `custom_message` плейсхолдеров."""
    if custom_message is None:
        return data

    res = dict(data)
    for placeholder_name, placeholder_data in custom_placeholders.items():
        if f"{{{placeholder_name}}}" in custom_message:
            res[placeholder_name] = await get_placeholder(placeholder_name, res)

    return res


def unregister_placeholders(module_name: str) -> bool:
    """Удаляет все плейсхолдеры, зарегистрированные указанным модулем."""
    to_remove = [
        name
        for name, data in custom_placeholders.items()
        if data.get("module_name") == module_name
    ]
    for name in to_remove:
        del custom_placeholders[name]
        logger.debug("Unregistered placeholder {%s} for module %s", name, module_name)
    return True


def config_placeholders() -> str | None:
    """Возвращает форматированный список всех плейсхолдеров для документации настроек."""
    result = []
    for name, data in sorted(custom_placeholders.items()):
        desc = data.get("description") or "Без описания"
        result.append(f"{{{name}}} — {desc}")

    return "\n".join(result) if result else None


def module_placeholders(module_name: str) -> list[str]:
    """Возвращает список плейсхолдеров конкретного модуля."""
    return [
        name
        for name, data in custom_placeholders.items()
        if data.get("module_name") == module_name
    ]


def help_placeholders(module_name: str) -> list[str]:
    """Возвращает список плейсхолдеров для отображения в справке модуля."""
    result = []
    for name, data in sorted(custom_placeholders.items()):
        if data.get("module_name") == module_name:
            desc = data.get("description") or "Без описания"
            result.append(f"{{{name}}} — {desc}")
    return result


def debug_placeholders() -> dict:
    """Возвращает реестр плейсхолдеров (для отладки)."""
    return custom_placeholders
