# ©️ Maxli, 2026
# This file is a part of Maxli Userbot
# 🌐 https://github.com/Igroshka/Maxli
# Портировано с heroku/modules/heroku_backup.py (AGPLv3)

# meta developer: @Igroshka
# scope: maxli_only

import datetime
import io
import json
import logging
import time
import zipfile

from pymax import File, Message

from .. import loader, utils

logger = logging.getLogger(__name__)


@loader.tds
class MaxliBackupMod(loader.Module):
    """Резервные копии базы данных и модулей"""

    strings = {"name": "MaxliBackup"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "period",
                0,
                lambda: "Период автобэкапа в часах (0 — выключить)",
                validator=loader.validators.Integer(minimum=0, maximum=168),
            ),
            loader.ConfigValue(
                "target_chat",
                0,
                lambda: "Куда слать автобэкап (0 — в «Избранное», то есть себе)",
                validator=loader.validators.Integer(),
            ),
        )

    async def client_ready(self):
        self._backup_chat = self.config["target_chat"] or (
            await utils.get_backup_chat(self._client, self._db)
        )

    @staticmethod
    def _stamp() -> str:
        return datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")

    # ------------------------------------------------------------------ #
    #                               database                              #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def backupdbcmd(self, message: Message):
        """Прислать резервную копию базы данных"""
        payload = json.dumps(dict(self._db), ensure_ascii=False, indent=2, default=str)

        await utils.answer_file(
            message,
            payload.encode(),
            caption=f"🗃 **Бэкап базы Maxli** — {self._stamp()}",
            name=f"maxli-db-{self._stamp()}.json",
        )

    @loader.owner
    @loader.command()
    async def restoredbcmd(self, message: Message):
        """<json> — восстановить базу из текста бэкапа

        Проще всего: скопируй содержимое файла бэкапа в аргумент команды.
        """
        payload = utils.get_args_raw(message)

        if not payload:
            await utils.answer(
                message,
                "❌ Пришли содержимое json-бэкапа аргументом команды",
            )
            return

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            await utils.answer(message, f"❌ Битый JSON: {utils.mono(e)}")
            return

        if not isinstance(data, dict):
            await utils.answer(message, "❌ В бэкапе должен быть объект верхнего уровня")
            return

        self._db.clear()
        self._db.update(data)
        self._db.save()

        await utils.answer(
            message,
            "✅ База восстановлена. Перезапусти юзербота: "
            + utils.mono(f"{self.get_prefix()}restart"),
        )

    # ------------------------------------------------------------------ #
    #                                modules                              #
    # ------------------------------------------------------------------ #

    def _modules_archive(self) -> bytes:
        buffer = io.BytesIO()

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for directory in (loader.LOADED_MODULES_DIR, loader.BASE_DIR / "modules"):
                if not directory.exists():
                    continue

                for path in directory.glob("*.py"):
                    archive.write(path, arcname=f"{directory.name}/{path.name}")

        return buffer.getvalue()

    @loader.command()
    async def backupmodscmd(self, message: Message):
        """Прислать архив с пользовательскими модулями"""
        payload = self._modules_archive()

        if len(payload) < 100:
            await utils.answer(message, "📦 Пользовательских модулей нет")
            return

        await utils.answer_file(
            message,
            payload,
            caption=f"📦 **Бэкап модулей Maxli** — {self._stamp()}",
            name=f"maxli-mods-{self._stamp()}.zip",
        )

    @loader.command()
    async def backupallcmd(self, message: Message):
        """Прислать базу и модули одним архивом"""
        buffer = io.BytesIO()

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "maxli-db.json",
                json.dumps(dict(self._db), ensure_ascii=False, indent=2, default=str),
            )

            for directory in (loader.LOADED_MODULES_DIR, loader.BASE_DIR / "modules"):
                if not directory.exists():
                    continue

                for path in directory.glob("*.py"):
                    archive.write(path, arcname=f"{directory.name}/{path.name}")

        await utils.answer_file(
            message,
            buffer.getvalue(),
            caption=f"💾 **Полный бэкап Maxli** — {self._stamp()}",
            name=f"maxli-full-{self._stamp()}.zip",
        )

    # ------------------------------------------------------------------ #
    #                              autobackup                             #
    # ------------------------------------------------------------------ #

    @loader.loop(interval=3600, autostart=True, wait_before=True)
    async def autobackup(self):
        """Раз в час проверяет, не пора ли сделать автобэкап."""
        period = self.config["period"]

        if not period or not self._backup_chat:
            return

        last = self.get("last_backup", 0)
        now = int(time.time())

        if now - last < period * 3600:
            return

        payload = json.dumps(dict(self._db), ensure_ascii=False, indent=2, default=str)

        try:
            await self._client.send_message(
                self._backup_chat,
                f"🗃 **Автобэкап базы Maxli** — {self._stamp()}",
                attachments=[
                    File(payload.encode(), name=f"maxli-db-{self._stamp()}.json")
                ],
            )
        except Exception:
            logger.exception("Autobackup failed")
            return

        self.set("last_backup", now)
