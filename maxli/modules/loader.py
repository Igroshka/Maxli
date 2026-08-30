# ©️ Maxli, 2026
# This file is a part of Maxli Userbot
# 🌐 https://github.com/Igroshka/Maxli

# meta developer: @Igroshka
# scope: maxli_only

import asyncio
import logging
import os
import re
import sys
from pathlib import Path

import aiohttp
from pymax import Message

from .. import loader, utils, version
from ..types import CoreUnloadError, LoadError

logger = logging.getLogger(__name__)

VALID_URL = re.compile(r"^https?://\S+\.py$")


@loader.tds
class LoaderMod(loader.Module):
    """Загрузка, обновление и удаление модулей"""

    strings = {"name": "Loader"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "MODULES_REPO",
                "https://raw.githubusercontent.com/Igroshka/Maxli-Modules/main",
                lambda: "Репозиторий модулей по умолчанию",
                validator=loader.validators.Link(),
            ),
            loader.ConfigValue(
                "additional_repos",
                [],
                lambda: "Дополнительные репозитории модулей",
                validator=loader.validators.Series(loader.validators.Link()),
            ),
            loader.ConfigValue(
                "share_link",
                False,
                lambda: "Показывать ссылку на модуль после загрузки",
                validator=loader.validators.Boolean(),
            ),
        )

    @property
    def repos(self) -> list[str]:
        """Все репозитории: основной плюс дополнительные."""
        return [self.config["MODULES_REPO"], *self.config["additional_repos"]]

    async def client_ready(self):
        self._links = self.pointer("links", {})
        await self._restore()

    # ------------------------------------------------------------------ #
    #                             requirements                            #
    # ------------------------------------------------------------------ #

    async def install_requirements(self, requirements: list[str]) -> bool:
        """Устанавливает pip-зависимости модуля."""
        requirements = [req for req in dict.fromkeys(requirements) if req]
        if not requirements:
            return True

        logger.info("Installing requirements: %s", requirements)

        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "-q",
            "--disable-pip-version-check",
            "--no-warn-script-location",
            *requirements,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error("pip failed: %s", stderr.decode(errors="ignore"))
            return False

        return True

    # ------------------------------------------------------------------ #
    #                              persistence                            #
    # ------------------------------------------------------------------ #

    async def _restore(self) -> None:
        """Догружает модули, установленные по ссылке, после перезапуска."""
        for name, link in dict(self._links).items():
            if self.lookup(name):
                continue

            try:
                await self._load_from_url(link)
            except Exception:
                logger.exception("Failed to restore module %s", name)

    # ------------------------------------------------------------------ #
    #                                loading                              #
    # ------------------------------------------------------------------ #

    async def _fetch(self, url: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.text()

    async def _load_from_url(self, url: str) -> loader.Module:
        source = await self._fetch(url)
        module = await self._load_source(source, origin=url)
        self._links[module.__class__.__name__] = url
        return module

    async def _load_source(self, source: str, origin: str = "<string>") -> loader.Module:
        meta = self.allmodules.parse_meta(source)

        required = meta.get("min_maxli")
        if required and required > version.version_code:
            raise LoadError(
                f"Модуль требует Maxli с версией кода ≥ {required}, "
                f"у тебя {version.version_code}"
            )

        requirements = self.allmodules.parse_requirements(source)
        if requirements and not await self.install_requirements(requirements):
            raise LoadError(f"Не удалось установить зависимости: {requirements}")

        return await self.allmodules.load_module_source(source, origin)

    # ------------------------------------------------------------------ #
    #                                commands                             #
    # ------------------------------------------------------------------ #

    @loader.command(alias="lm")
    async def loadmodcmd(self, message: Message):
        """[путь или ссылка] — загрузить модуль из файла, по ссылке или из ответа на файл"""
        args = utils.get_args_raw(message).strip()

        # Без аргумента команду обычно пишут ответом на присланный .py-файл.
        document = await utils.get_reply_document(message) if not args else None

        if not args and document is None:
            await utils.answer(
                message,
                "❌ Укажи путь к файлу, ссылку или ответь на файл модуля",
            )
            return

        if document is not None and not document[0].endswith(".py"):
            await utils.answer(
                message,
                f"❌ {utils.mono(document[0])} — это не .py-файл",
            )
            return

        message = await utils.answer(message, self.strings["loading"]) or message

        try:
            if document is not None:
                name, data = document
                module = await self._load_source(
                    data.decode("utf-8"),
                    origin=name,
                )
            elif VALID_URL.match(args):
                module = await self._load_from_url(args)
            else:
                path = Path(args)
                if not path.exists():
                    await utils.answer(message, f"❌ Файл {utils.mono(args)} не найден")
                    return

                module = await self._load_source(
                    path.read_text(encoding="utf-8"),
                    origin=str(path),
                )
        except LoadError as e:
            await utils.answer(message, self.strings["error"].format(e))
            return
        except Exception as e:
            logger.exception("Module load failed")
            await utils.answer(message, self.strings["error"].format(f"{type(e).__name__}: {e}"))
            return

        await utils.answer(
            message,
            self._loaded_text(module),
        )

    @loader.command(alias="dlm")
    async def dlmodcmd(self, message: Message):
        """<имя или ссылка> — скачать модуль из репозитория"""
        args = utils.get_args_raw(message)

        if not args:
            await utils.answer(message, "❌ Укажи имя модуля или ссылку")
            return

        message = await utils.answer(message, self.strings["loading"]) or message

        candidates = (
            [args]
            if VALID_URL.match(args)
            else [f"{repo.rstrip('/')}/{args}.py" for repo in self.repos]
        )

        last_error: Exception | None = None

        for url in candidates:
            try:
                module = await self._load_from_url(url)
            except Exception as e:  # noqa: PERF203 — перебираем репозитории по очереди
                logger.debug("dlmod from %s failed: %s", url, e)
                last_error = e
                continue

            await utils.answer(message, self._loaded_text(module, url))
            return

        await utils.answer(
            message,
            self.strings["error"].format(
                f"{type(last_error).__name__}: {last_error}"
                if last_error
                else f"модуль {args} не найден ни в одном репозитории"
            ),
        )

    def _loaded_text(self, module: loader.Module, url: str | None = None) -> str:
        prefix = self.get_prefix()
        meta = getattr(module, "__meta__", None) or {}

        body = [
            f"{prefix}{name} — "
            f"{utils.unmark(((func.__doc__ or 'Без описания').strip().splitlines() or ['Без описания'])[0])}"
            for name, func in sorted(module.commands.items())
        ]

        if meta.get("developer"):
            body.append(f"👤 {utils.unmark(meta['developer'])}")

        if url and self.config["share_link"]:
            body.append(f"🔗 {url}")

        text = self.strings["loaded"].format(module.strings["name"])

        if body:
            text += "\n" + utils.quote("\n".join(body))

        return text

    @loader.command(alias="ulm")
    async def unloadmodcmd(self, message: Message):
        """<модуль> — выгрузить модуль"""
        args = utils.get_args_raw(message)

        if not args:
            await utils.answer(message, "❌ Укажи модуль")
            return

        try:
            worked = await self.allmodules.unload_module(args)
        except CoreUnloadError as e:
            await utils.answer(message, f"🛡 {e}")
            return

        if not worked:
            await utils.answer(message, self.strings["not_found"].format(args))
            return

        for name in worked:
            self._links.pop(name, None)

            stored = loader.LOADED_MODULES_DIR / f"{name}.py"
            if stored.exists():
                os.remove(stored)

        await utils.answer(message, self.strings["unloaded"].format(", ".join(worked)))

    @loader.command()
    async def reloadmodcmd(self, message: Message):
        """<модуль> — перезагрузить модуль из его источника"""
        args = utils.get_args_raw(message)
        module = self.lookup(args) if args else None

        if not module:
            await utils.answer(message, self.strings["not_found"].format(args))
            return

        source = getattr(module, "__source__", "")
        origin = getattr(module, "__origin__", "<string>")

        if not source:
            await utils.answer(message, "❌ Исходник модуля недоступен")
            return

        await self.allmodules.unload_module(module.__class__.__name__)

        try:
            reloaded = await self._load_source(source, origin)
        except Exception as e:
            await utils.answer(message, self.strings["error"].format(e))
            return

        await utils.answer(message, self._loaded_text(reloaded))

    @loader.command()
    async def modsourcecmd(self, message: Message):
        """<модуль> — прислать исходный код модуля файлом"""
        args = utils.get_args_raw(message)
        module = self.lookup(args) if args else None

        if not module:
            await utils.answer(message, self.strings["not_found"].format(args))
            return

        source = getattr(module, "__source__", "")
        if not source:
            await utils.answer(message, "❌ Исходник недоступен")
            return

        await utils.answer_file(
            message,
            source.encode(),
            caption=f"📄 **{module.strings['name']}**",
            name=f"{module.__class__.__name__}.py",
        )

    # ------------------------------------------------------------------ #
    #                             repositories                            #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def reposcmd(self, message: Message):
        """Список репозиториев модулей"""
        body = "\n".join(
            f"{'⭐' if index == 0 else '▫️'} {repo}"
            for index, repo in enumerate(self.repos)
        )
        await utils.answer(
            message,
            utils.heading("📚 Репозитории модулей") + "\n" + utils.quote(body),
        )

    @loader.command()
    async def addrepocmd(self, message: Message):
        """<ссылка> — добавить репозиторий модулей"""
        url = utils.get_args_raw(message).strip().rstrip("/")

        if not utils.check_url(url):
            await utils.answer(message, "❌ Это не похоже на ссылку")
            return

        if url in self.repos:
            await utils.answer(message, "❌ Такой репозиторий уже добавлен")
            return

        self.config["additional_repos"] = [*self.config["additional_repos"], url]
        self.allmodules.save_config(self)

        await utils.answer(message, f"📚 Репозиторий добавлен:\n{url}")

    @loader.command()
    async def delrepocmd(self, message: Message):
        """<ссылка> — убрать репозиторий модулей"""
        url = utils.get_args_raw(message).strip().rstrip("/")
        current = list(self.config["additional_repos"])

        if url not in current:
            await utils.answer(message, "❌ Такого репозитория нет в списке")
            return

        current.remove(url)
        self.config["additional_repos"] = current
        self.allmodules.save_config(self)

        await utils.answer(message, f"🗑 Репозиторий убран:\n{url}")

    # ------------------------------------------------------------------ #
    #                              bulk actions                           #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def modscmd(self, message: Message):
        """Список пользовательских модулей"""
        mods = [
            module
            for module in self.allmodules.modules
            if not str(getattr(module, "__origin__", "")).startswith("<core")
        ]

        if not mods:
            await utils.answer(message, "🧩 Пользовательских модулей нет")
            return

        lines = []

        for module in sorted(mods, key=lambda m: str(m.strings["name"]).lower()):
            developer = (getattr(module, "__meta__", None) or {}).get("developer", "")
            lines.append(
                f"{utils.unmark(module.strings['name'])} "
                f"({module.__class__.__name__})"
                + (f" — {utils.unmark(developer)}" if developer else "")
            )

        await utils.answer(
            message,
            utils.smart_truncate(
                utils.heading(f"🧩 Пользовательские модули — {len(mods)}")
                + "\n"
                + utils.quote("\n".join(lines))
            ),
        )

    @loader.owner
    @loader.command()
    async def clearmodulescmd(self, message: Message):
        """Выгрузить и удалить все пользовательские модули"""
        mods = [
            module.__class__.__name__
            for module in self.allmodules.modules
            if not str(getattr(module, "__origin__", "")).startswith("<core")
        ]

        if not mods:
            await utils.answer(message, "🧩 Пользовательских модулей нет")
            return

        for name in mods:
            try:
                await self.allmodules.unload_module(name)
            except Exception:
                logger.exception("Failed to unload %s", name)

            self._links.pop(name, None)

            stored = loader.LOADED_MODULES_DIR / f"{name}.py"
            if stored.exists():
                os.remove(stored)

        await utils.answer(message, f"🧹 Удалено модулей: {len(mods)}")

    @loader.command(alias="ml")
    async def sendmodcmd(self, message: Message):
        """<модуль> — прислать файл модуля (синоним .modsource)"""
        await self.modsourcecmd(message)
