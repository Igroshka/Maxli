# ©️ Maxli, 2026
# This file is a part of Maxli Userbot
# 🌐 https://github.com/Igroshka/Maxli

# meta developer: @YouRooni
# scope: maxli_only

from __future__ import annotations

import asyncio
import time

from pymax import Message

from .. import loader, utils


@loader.tds
class TerminalMod(loader.Module):
    """Выполнение команд в системной оболочке"""

    strings = {"name": "Terminal", "running": "⏳ Выполняется..."}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "timeout",
                120,
                lambda: "Таймаут выполнения команды в секундах",
                validator=loader.validators.Integer(minimum=1, maximum=3600),
            ),
            loader.ConfigValue(
                "output_limit",
                3000,
                lambda: "Максимальная длина вывода в сообщении",
                validator=loader.validators.Integer(minimum=100, maximum=4000),
            ),
        )
        self.activeproc: dict[int, asyncio.subprocess.Process] = {}

    @loader.owner
    @loader.command(alias="sh")
    async def terminalcmd(self, message: Message):
        """<команда> — выполнить команду в терминале"""
        command = utils.get_args_raw(message)

        if not command:
            await utils.answer(message, "❌ Укажи команду")
            return

        message = await utils.answer(message, self.strings["running"]) or message

        start_time = time.perf_counter()

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=utils.get_base_dir(),
            )
        except Exception as e:
            await utils.answer(message, f"❌ {utils.mono(f'{type(e).__name__}: {e}')}")
            return

        chat_id = utils.get_chat_id(message)
        self.activeproc[chat_id] = process

        try:
            stdout, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=self.config["timeout"],
            )
        except asyncio.TimeoutError:
            process.kill()
            await utils.answer(message, "⏳ Команда превысила таймаут и была убита")
            return
        finally:
            self.activeproc.pop(chat_id, None)

        exec_time = time.perf_counter() - start_time
        time_str = f"{exec_time * 1000:.1f}мс" if exec_time < 1 else f"{exec_time:.2f}с"

        output = stdout.decode(errors="replace").strip() or "(пусто)"
        icon = "✅" if process.returncode == 0 else "🚫"

        info_line = f"**Код выхода:** {process.returncode} · ⏱ {time_str}"
        header = f"💻 {command}\n{info_line}"

        if len(output) > self.config["output_limit"]:
            await utils.answer_file(
                message,
                output.encode("utf-8"),
                caption=header,
                name="output.txt",
            )
            return

        body = f"{info_line}\n\n{utils.code_block(output)}"
        text = f"💻 {utils.mono(command)}\n{utils.quote(body)}"
        await utils.answer(message, text)

    @loader.owner
    @loader.command()
    async def killcmd(self, message: Message):
        """Убить процесс, запущенный в этом чате"""
        chat_id = utils.get_chat_id(message)
        process = self.activeproc.get(chat_id)

        if process is None:
            await utils.answer(message, "❌ В этом чате нет активных процессов")
            return

        process.kill()
        self.activeproc.pop(chat_id, None)
        await utils.answer(message, "☠️ Процесс убит")
