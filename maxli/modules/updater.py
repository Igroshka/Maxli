# ©️ Maxli, 2026
# This file is a part of Maxli Userbot
# 🌐 https://github.com/Igroshka/Maxli
# Портировано с heroku/modules/updater.py (AGPLv3)

# meta developer: @Igroshka
# scope: maxli_only

import logging
import os
import subprocess
import time

from pymax import Message

from .. import _internal, loader, main, utils, version

logger = logging.getLogger(__name__)


@loader.tds
class UpdaterMod(loader.Module):
    """Обновление, перезапуск и остановка юзербота"""

    strings = {"name": "Updater"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "autoupdate",
                False,
                lambda: "Проверять обновления автоматически раз в сутки",
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "notify_update",
                True,
                lambda: "Сообщать в «Избранное», когда вышло обновление",
                validator=loader.validators.Boolean(),
            ),
        )

    async def client_ready(self):
        await self._report_restart()

    # ------------------------------------------------------------------ #
    #                             restart flow                            #
    # ------------------------------------------------------------------ #

    async def _report_restart(self) -> None:
        """Досылает уведомление в чат, из которого юзербота перезапустили."""
        info = self._db.get(main.__name__, "restart_info", None)

        if not info:
            return

        self._db.unset(main.__name__, "restart_info")

        chat_id = info.get("chat")
        started = info.get("time", 0)

        if not chat_id:
            return

        took = f" за {round(time.time() - started, 1)} с" if started else ""
        kind = "обновлён" if info.get("update") else "перезапущен"

        try:
            await self._client.send_message(
                chat_id,
                f"✅ **Maxli {kind}**{took}\n"
                f"Версия: {utils.mono(version.pretty())}",
            )
        except Exception:
            logger.debug("Could not report restart", exc_info=True)

    def _remember_restart(self, message: Message, update: bool = False) -> None:
        self._db.set(
            main.__name__,
            "restart_info",
            {
                "chat": utils.get_chat_id(message),
                "time": time.time(),
                "update": update,
            },
        )
        self._db.save()

    @loader.owner
    @loader.command()
    async def restartcmd(self, message: Message):
        """Перезапустить юзербота"""
        await utils.answer(message, "🔄 Перезапускаюсь...")
        self._remember_restart(message)
        _internal.restart()

    @loader.owner
    @loader.command()
    async def ubstopcmd(self, message: Message):
        """Полностью остановить юзербота"""
        await utils.answer(message, "🛑 Выключаюсь. Запусти меня руками, когда понадоблюсь.")
        self._db.save()
        _internal.die()

    # ------------------------------------------------------------------ #
    #                                update                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _git_sync(*args: str) -> str | None:
        """Запускает git в каталоге репозитория и отдаёт вывод."""
        try:
            return (
                subprocess.check_output(
                    ["git", *args],
                    stderr=subprocess.DEVNULL,
                    cwd=_internal.get_repo_dir(),
                )
                .decode(errors="replace")
                .strip()
            )
        except Exception:
            return None

    async def _git(self, *args: str) -> str | None:
        """Асинхронная обёртка: git ходит в сеть и блокировал бы event loop."""
        return await utils.run_sync(self._git_sync, *args)

    async def _pending_commits(self) -> list[str]:
        """Коммиты, которые есть на origin, но не применены локально."""
        await self._git("fetch", "--quiet")
        log = await self._git("log", "--oneline", "HEAD..@{u}")
        return log.splitlines() if log else []

    @loader.command()
    async def changelogcmd(self, message: Message):
        """Что изменилось в последних коммитах"""
        log = await self._git("log", "--oneline", "-15")

        if not log:
            await utils.answer(message, "❌ Maxli установлен не из git")
            return

        await utils.answer(message, f"📝 **История изменений**\n{utils.quote(log)}")

    @loader.command()
    async def sourcecmd(self, message: Message):
        """Ссылка на исходники и текущая версия"""
        commit = _internal.get_git_hash() or "—"
        count = _internal.get_commit_count() or version.version_code

        await utils.answer(
            message,
            f"📦 **Maxli v{version.pretty()}**\n"
            f"Коммит: {utils.mono(commit)} (build {count})\n"
            f"Ветка: {utils.mono(version.branch)}\n"
            f"Исходники: https://github.com/YouRooni/Maxli",
        )

    @loader.owner
    @loader.command()
    async def updatecmd(self, message: Message):
        """Обновить Maxli из git и перезапуститься"""
        if not os.path.isdir(os.path.join(_internal.get_repo_dir(), ".git")):
            await utils.answer(
                message,
                "❌ Maxli установлен не из git — обновить автоматически не выйдет",
            )
            return

        message = await utils.answer(message, "⬇️ Проверяю обновления...") or message

        pending = await self._pending_commits()

        if not pending:
            await utils.answer(message, "✅ Уже последняя версия")
            return

        preview = utils.quote("\n".join(pending[:15]), 1500)
        message = (
            await utils.answer(
                message,
                f"⬇️ Обновляюсь, коммитов: {len(pending)}\n{preview}",
            )
            or message
        )

        if not _internal.pull():
            await utils.answer(
                message,
                "❌ git pull не прошёл. Скорее всего есть локальные изменения — "
                "разберись руками.",
            )
            return

        _internal.install_requirements()
        await utils.answer(message, "🔄 Обновился, перезапускаюсь...")
        self._remember_restart(message, update=True)
        _internal.restart()

    @loader.loop(interval=86400, autostart=True, wait_before=True)
    async def update_checker(self):
        """Раз в сутки проверяет наличие обновлений."""
        if not self.config["autoupdate"] and not self.config["notify_update"]:
            return

        pending = await self._pending_commits()

        if not pending:
            return

        if self.config["autoupdate"]:
            logger.info("Autoupdate: %s new commits, updating", len(pending))

            if _internal.pull():
                _internal.install_requirements()
                self._db.set(
                    main.__name__,
                    "restart_info",
                    {
                        "chat": await utils.get_self_chat_id(),
                        "time": time.time(),
                        "update": True,
                    },
                )
                self._db.save()
                _internal.restart()

            return

        if self.config["notify_update"] and self.get("notified") != pending[0]:
            chat_id = await utils.get_log_chat(self._client, self._db)

            if chat_id is None:
                return

            self.set("notified", pending[0])

            with_prefix = utils.mono(f"{self.get_prefix()}update")
            await self._client.send_message(
                chat_id,
                f"⬇️ **Доступно обновление Maxli** ({len(pending)} коммитов)\n"
                f"{utils.quote(chr(10).join(pending[:10]), 1000)}\n"
                f"Обновиться: {with_prefix}",
            )
