# ©️ Maxli, 2026
# This file is a part of Maxli Userbot
# 🌐 https://github.com/Igroshka/Maxli
# Портировано с heroku/modules/translations.py (AGPLv3)

# meta developer: @Igroshka
# scope: maxli_only

import logging

import aiohttp
from pymax import Message

from .. import loader, translations, utils

logger = logging.getLogger(__name__)


@loader.tds
class TranslationsMod(loader.Module):
    """Язык интерфейса и пакеты переводов"""

    strings = {"name": "Translations"}

    @loader.command()
    async def setlangcmd(self, message: Message):
        """<ru|en> — сменить язык интерфейса"""
        args = utils.get_args_raw(message).strip().lower()

        if not args:
            available = [
                path.stem
                for path in translations.PACKS.iterdir()
                if path.suffix in {".yml", ".yaml", ".json"}
            ]
            await utils.answer(
                message,
                f"🌐 Текущий язык: {utils.mono(self.tr.language)}\n"
                f"Доступные: {utils.mono(', '.join(sorted(available)))}",
            )
            return

        if not await self.tr.set_language(args):
            await utils.answer(message, f"❌ Пакет {utils.mono(args)} не найден")
            return

        await self.allmodules.reload_translations()
        await utils.answer(message, f"🌐 Язык переключён на {utils.mono(args)}")

    @loader.command()
    async def dllangpackcmd(self, message: Message):
        """<ссылка> — скачать и установить пакет переводов (.yml или .json)"""
        url = utils.get_args_raw(message).strip()

        if not utils.check_url(url):
            await utils.answer(message, "❌ Укажи прямую ссылку на файл перевода")
            return

        name = url.rstrip("/").rsplit("/", 1)[-1]

        if not name.endswith((".yml", ".yaml", ".json")):
            await utils.answer(message, "❌ Поддерживаются только .yml, .yaml и .json")
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    payload = await response.text()
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось скачать: {utils.mono(e)}")
            return

        path = translations.PACKS / name
        path.write_text(payload, encoding="utf-8")

        code = path.stem

        if not await self.tr.set_language(code):
            await utils.answer(
                message,
                f"⚠️ Пакет сохранён как {utils.mono(name)}, но применить не вышло",
            )
            return

        await self.allmodules.reload_translations()
        await utils.answer(message, f"🌐 Пакет {utils.mono(code)} установлен и применён")

    @loader.command()
    async def langpackscmd(self, message: Message):
        """Список установленных пакетов переводов"""
        packs = sorted(
            path.name
            for path in translations.PACKS.iterdir()
            if path.suffix in {".yml", ".yaml", ".json"}
        )

        listing = "\n".join(
            f"{'✅' if path.rsplit('.', 1)[0] == self.tr.language else '▫️'} "
            f"{utils.mono(path)}"
            for path in packs
        )

        await utils.answer(message, f"🌐 **Пакеты переводов**\n{listing or '▫️ пусто'}")

    @loader.command()
    async def reloadlangcmd(self, message: Message):
        """Перечитать пакеты переводов с диска"""
        if not await self.allmodules.reload_translations():
            await utils.answer(message, "❌ Не удалось перезагрузить переводы")
            return

        await utils.answer(message, "🌐 Переводы перезагружены")
