import json
from typing import Any, Dict

CONFIG_FILE = "maxli_config.json"

def _ensure_defaults(conf: Dict[str, Any]) -> Dict[str, Any]:
    if "phone" not in conf or not conf["phone"]:
        conf["phone"] = input(">>> Введите номер телефона (например, +79123456789): ")
    if "prefix" not in conf: conf["prefix"] = "."
    if "aliases" not in conf: conf["aliases"] = {}
    # Устанавливаем полезные алиасы по умолчанию, но не перезаписываем пользовательские
    default_aliases = {
        "cfg": "config",
        "lm": "load",
        "ml": "sendmodule",
        "ulm": "unload",
        "fcfg": "configset",
    }
    for k, v in default_aliases.items():
        conf.setdefault("aliases", {}).setdefault(k, v)
    # Глобальные тексты (шаблоны) с подстановкой переменных
    if "texts" not in conf:
        conf["texts"] = {
            "module_loaded": "✅ Модуль '{name}' v{version} установлен (Maxli v{maxli_version})",
            "module_unloaded": "✅ Модуль '{name}' удалён",
        }
    # Реестр настроек внешних модулей
    if "external_modules" not in conf:
        conf["external_modules"] = {}
    # Баннеры для системных команд
    if "banners" not in conf:
        conf["banners"] = {  # keys: info, ping, help
            "info": "",
            "ping": "",
            "help": ""
        }
    return conf

def load_config():
    """Загружает конфиг и применяет значения по умолчанию."""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            conf = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        conf = {}
    conf = _ensure_defaults(conf)
    save_config(conf)
    return conf

def save_config(config_data):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)

def render_text(key: str, **variables) -> str:
    """Возвращает отрендеренный шаблон из config['texts'] с подстановкой переменных."""
    template = config.get("texts", {}).get(key, "")
    try:
        return template.format(**variables)
    except Exception:
        return template

def register_module_settings(module_name: str, settings_schema: Dict[str, Any]):
    """Регистрирует (или обновляет) схему настроек внешнего модуля.
    settings_schema: {"option_key": {"default": Any, "description": str}}
    """
    conf = config
    # Зарезервированные системные имена модулей
    reserved_names = {"info", "management", "ping", "settings", "modules", "restart"}
    normalized_name = module_name
    if module_name in reserved_names:
        normalized_name = f"{module_name}_maxli"
    if normalized_name not in conf["external_modules"]:
        conf["external_modules"][normalized_name] = {"settings": {}, "descriptions": {}}
    for key, meta in (settings_schema or {}).items():
        default_value = meta.get("default")
        description = meta.get("description", "")
        # Значение не перетираем, если уже задано пользователем
        if key not in conf["external_modules"][normalized_name]["settings"]:
            conf["external_modules"][normalized_name]["settings"][key] = default_value
        conf["external_modules"][normalized_name]["descriptions"][key] = description
    save_config(conf)
    return normalized_name

def get_module_setting(module_name: str, key: str, default: Any = None) -> Any:
    # С учётом нормализации имён
    reserved_names = {"info", "management", "ping", "settings", "modules", "restart"}
    normalized_name = f"{module_name}_maxli" if module_name in reserved_names else module_name
    return config.get("external_modules", {}).get(normalized_name, {}).get("settings", {}).get(key, default)

def get_banner_url(command_name: str) -> str:
    return config.get("banners", {}).get(command_name, "")

config = load_config()
PHONE = config.get("phone")
PREFIX = config.get("prefix", ".")
ALIASES = config.get("aliases", {})