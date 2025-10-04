import json

CONFIG_FILE = "maxli_config.json"

def load_config():
    """Загружает конфиг, запрашивает номер телефона, если его нет."""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            conf = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        conf = {}

    if "phone" not in conf or not conf["phone"]:
        conf["phone"] = input(">>> Введите номер телефона (например, +79123456789): ")
    
    if "prefix" not in conf: conf["prefix"] = "."
    if "aliases" not in conf: conf["aliases"] = {}

    save_config(conf)
    return conf

def save_config(config_data):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=4)

config = load_config()
PHONE = config.get("phone")
PREFIX = config.get("prefix", ".")
ALIASES = config.get("aliases", {})