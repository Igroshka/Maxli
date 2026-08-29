# ©️ Maxli, 2026
# This file is a part of Maxli Userbot
# 🌐 https://github.com/Igroshka/Maxli

# meta developer: @Igroshka
# scope: maxli_only

import logging
import platform
import time

import pymax
from pymax import Message

from .. import _internal, loader, utils, version

logger = logging.getLogger(__name__)

try:
    import psutil
except ImportError:  # psutil опционален — без него просто нет блока «железа»
    psutil = None


@loader.tds
class MaxliInfoMod(loader.Module):
    """Информация о юзерботе"""

    strings = {"name": "MaxliInfo"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "custom_message",
                "",
                lambda: "Свой шаблон .info. Плейсхолдеры:\n"
                + (utils.config_placeholders() or "{version} {uptime} {owner} {prefix} {modules} {commands} {python} {pymax} {platform}"),
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "show_hardware",
                True,
                lambda: "Показывать нагрузку CPU и RAM",
                validator=loader.validators.Boolean(),
            ),
        )

    # ------------------------------------------------------------------ #
    #                            placeholders                             #
    # ------------------------------------------------------------------ #

    @loader.placeholder("version", "Версия юзербота")
    def _ph_version(self) -> str:
        return version.pretty()

    @loader.placeholder("uptime", "Время непрерывной работы")
    def _ph_uptime(self) -> str:
        return utils.formatted_uptime()

    @loader.placeholder("owner", "Имя владельца")
    def _ph_owner(self) -> str:
        me = self._client.me
        return utils.get_display_name(me.contact if me else None)

    @loader.placeholder("owner_id", "ID владельца")
    def _ph_owner_id(self) -> str:
        return str(utils.get_me_id() or "—")

    @loader.placeholder("prefix", "Основной префикс команд")
    def _ph_prefix(self) -> str:
        return self.get_prefix()

    @loader.placeholder("modules", "Количество загруженных модулей")
    def _ph_modules(self) -> str:
        return str(len(self.allmodules.modules))

    @loader.placeholder("commands", "Количество доступных команд")
    def _ph_commands(self) -> str:
        return str(len(self.allmodules.commands))

    @loader.placeholder("python", "Версия Python")
    def _ph_python(self) -> str:
        return platform.python_version()

    @loader.placeholder("pymax", "Версия библиотеки PyMax")
    def _ph_pymax(self) -> str:
        return pymax.__version__

    @loader.placeholder("platform", "Операционная система")
    def _ph_platform(self) -> str:
        return f"{platform.system()} {platform.release()}"

    def _base_data(self) -> dict:
        me = self._client.me
        return {
            "version": version.pretty(),
            "build": _internal.get_commit_count() or version.version_code,
            "hash": _internal.get_git_hash() or "—",
            "branch": version.branch,
            "uptime": utils.formatted_uptime(),
            "owner": utils.get_display_name(me.contact if me else None),
            "owner_id": utils.get_me_id() or "—",
            "prefix": self.get_prefix(),
            "modules": len(self.allmodules.modules),
            "commands": len(self.allmodules.commands),
            "python": platform.python_version(),
            "pymax": pymax.__version__,
            "platform": f"{platform.system()} {platform.release()}",
        }

    async def _render(self) -> str:
        data = self._base_data()

        if self.config["custom_message"]:
            data = await utils.get_placeholders(data, self.config["custom_message"])
            try:
                return self.config["custom_message"].format(**data)
            except Exception:
                text = self.config["custom_message"]
                for key, value in data.items():
                    text = text.replace("{" + str(key) + "}", str(value))
                return text

        lines = [
            f"👤 {self.strings['owner']}: {utils.unmark(data['owner'])} "
            f"({data['owner_id']})",
            f"⏱ {self.strings['uptime']}: {data['uptime']}",
            f"⌨️ {self.strings['prefix']}: {data['prefix']}",
            f"🧩 модулей: {data['modules']} · команд: {data['commands']}",
            f"🐍 Python: {data['python']} · PyMax: {data['pymax']}",
            f"💻 система: {data['platform']}",
        ]

        if self.config["show_hardware"] and psutil is not None:
            memory = psutil.virtual_memory()
            lines.append(
                f"📊 CPU: {psutil.cpu_percent()}% · "
                f"RAM: {utils.humanbytes(memory.used)} / "
                f"{utils.humanbytes(memory.total)}"
            )

        return (
            utils.heading(f"🌌 Maxli v{data['version']}")
            + f"\n_build {data['build']} · {data['hash']} · {data['branch']}_\n"
            + utils.quote("\n".join(lines))
        )

    @loader.command(alias="i")
    async def infocmd(self, message: Message):
        """Показать информацию о юзерботе"""
        await utils.answer(message, await self._render())

    @loader.command()
    async def pingcmd(self, message: Message):
        """Проверить задержку ответа"""
        start = time.perf_counter()
        sent = await utils.answer(message, "🏓 ...")
        latency = round((time.perf_counter() - start) * 1000)

        await utils.answer(
            sent or message,
            f"🏓 **Пинг:** {latency} мс\n⏱ **Аптайм:** {utils.formatted_uptime()}",
        )
