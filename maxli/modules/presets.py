# ©️ Maxli, 2026
# This file is a part of Maxli Userbot
# 🌐 https://github.com/Igroshka/Maxli
# Портировано с heroku/modules/presets.py (AGPLv3)

# meta developer: @Igroshka
# scope: maxli_only

import json
import logging

import aiohttp
from pymax import Message

from .. import loader, utils

logger = logging.getLogger(__name__)

#: Встроенные наборы модулей. Значения — имена файлов в репозитории модулей.
BUILTIN_PRESETS: dict[str, list[str]] = {
    "minimal": [],
    "basic": ["afk", "notes", "weather"],
    "chat": ["antispam", "welcome", "chatstats"],
    "fun": ["quotes", "randomizer", "emojimix"],
}


@loader.tds
class PresetsMod(loader.Module):
    """Наборы модулей: установить сразу пачку одной командой"""

    strings = {"name": "Presets"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "presets_url",
                "",
                lambda: "Ссылка на JSON со своими пресетами (пусто — только встроенные)",
                validator=loader.validators.String(),
            ),
        )

    async def _fetch_presets(self) -> dict[str, list[str]]:
        """Встроенные пресеты плюс внешние, если задана ссылка."""
        presets = dict(BUILTIN_PRESETS)
        url = self.config["presets_url"]

        if not utils.check_url(url):
            return presets

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    external = json.loads(await response.text())

            if isinstance(external, dict):
                presets.update(
                    {
                        name: list(mods)
                        for name, mods in external.items()
                        if isinstance(mods, list)
                    }
                )
        except Exception:
            logger.exception("Failed to fetch external presets")

        # Свои пресеты, сохранённые через .savepreset — в них лежат прямые ссылки
        presets.update(self.get("saved", {}))
        return presets

    @loader.command()
    async def presetscmd(self, message: Message):
        """Список доступных пресетов"""
        presets = await self._fetch_presets()

        blocks = [utils.heading("📦 Пресеты модулей")]

        for name, mods in presets.items():
            blocks.append(
                f"▫️ **{name}** — модулей: {len(mods)}\n"
                + utils.quote(", ".join(mods) if mods else "пусто")
            )

        blocks.append(
            f"Установить: {utils.mono(self.get_prefix() + 'loadpreset <имя>')}"
        )
        await utils.answer(message, "\n".join(blocks))

    @loader.owner
    @loader.command()
    async def loadpresetcmd(self, message: Message):
        """<имя> — установить все модули из пресета"""
        name = utils.get_args_raw(message).strip().lower()
        presets = await self._fetch_presets()

        if name not in presets:
            await utils.answer(
                message,
                f"❌ Пресет {utils.mono(name)} не найден. "
                f"Доступны: {utils.mono(', '.join(presets))}",
            )
            return

        mods = presets[name]

        if not mods:
            await utils.answer(message, f"📦 Пресет {utils.mono(name)} пуст")
            return

        message = (
            await utils.answer(
                message,
                f"📦 Ставлю пресет **{name}** — модулей: {len(mods)}...",
            )
            or message
        )

        loader_mod = self.lookup("LoaderMod")

        if not loader_mod:
            await utils.answer(message, "❌ Модуль Loader недоступен")
            return

        installed, failed = [], []

        for mod_name in mods:
            # В своих пресетах хранятся готовые ссылки, во встроенных — имена
            url = (
                mod_name
                if utils.check_url(mod_name)
                else f"{loader_mod.config['MODULES_REPO'].rstrip('/')}/{mod_name}.py"
            )

            try:
                module = await loader_mod._load_from_url(url)
                installed.append(module.strings["name"])
            except Exception as e:
                logger.debug("Preset module %s failed: %s", mod_name, e)
                failed.append(mod_name)

        text = f"📦 **Пресет {name} установлен**"

        if installed:
            text += "\n✅ **Загружены**\n" + utils.quote(
                ", ".join(utils.unmark(item) for item in installed)
            )

        if failed:
            text += "\n❌ **Не установились**\n" + utils.quote(", ".join(failed))

        await utils.answer(message, text)

    @loader.owner
    @loader.command()
    async def savepresetcmd(self, message: Message):
        """<имя> — сохранить текущий набор пользовательских модулей как пресет"""
        name = utils.get_args_raw(message).strip().lower()

        if not name:
            await utils.answer(message, "❌ Укажи имя пресета")
            return

        loader_mod = self.lookup("LoaderMod")
        links = dict(getattr(loader_mod, "_links", {})) if loader_mod else {}

        if not links:
            await utils.answer(message, "❌ Установленных по ссылке модулей нет")
            return

        saved = self.pointer("saved", {})
        saved[name] = list(links.values())

        await utils.answer(
            message,
            f"💾 Пресет **{name}** сохранён — модулей: {len(links)}",
        )

    @loader.owner
    @loader.command()
    async def mypresetscmd(self, message: Message):
        """Свои сохранённые пресеты"""
        saved = self.get("saved", {})

        if not saved:
            await utils.answer(message, "💾 Своих пресетов нет")
            return

        body = "\n".join(f"{name} — модулей: {len(urls)}" for name, urls in saved.items())
        await utils.answer(
            message,
            utils.heading("💾 Свои пресеты") + "\n" + utils.quote(body),
        )
