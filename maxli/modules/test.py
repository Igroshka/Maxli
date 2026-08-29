# ©️ Maxli, 2026
# This file is a part of Maxli Userbot
# 🌐 https://github.com/Igroshka/Maxli
# Портировано с heroku/modules/test.py (AGPLv3)

# meta developer: @Igroshka
# scope: maxli_only

import asyncio
import logging

from pymax import Message

from .. import log, loader, utils

logger = logging.getLogger(__name__)


@loader.tds
class TestMod(loader.Module):
    """Логи, диагностика и отладка юзербота"""

    strings = {"name": "Tester"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "force_send_all",
                False,
                lambda: "Слать в логи вообще всё, включая DEBUG",
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "tglog_level",
                "WARNING",
                lambda: "Уровень логов по умолчанию для .logs",
                validator=loader.validators.Choice(
                    ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "ALL"]
                ),
            ),
        )

    # ------------------------------------------------------------------ #
    #                                  logs                               #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def logscmd(self, message: Message):
        """[уровень] — прислать логи файлом

        Уровни: CRITICAL, ERROR, WARNING, INFO, DEBUG, ALL
        """
        args = utils.get_args_raw(message).strip().upper()
        name = args or self.config["tglog_level"]

        if name not in log.LEVELS:
            await utils.answer(
                message,
                f"❌ Неизвестный уровень {utils.mono(name)}. "
                f"Доступны: {utils.mono(', '.join(log.LEVELS))}",
            )
            return

        records = log.get_memory_handler().dumps(log.LEVELS[name])

        if not records:
            await utils.answer(message, f"📁 Логов уровня {utils.mono(name)} нет")
            return

        await utils.answer_file(
            message,
            "\n".join(records).encode(),
            caption=f"📁 **Логи Maxli** — {name}, строк: {len(records)}",
            name=f"maxli-logs-{name.lower()}.txt",
        )

    @loader.command()
    async def clearlogscmd(self, message: Message):
        """Очистить буфер логов"""
        log.get_memory_handler().clear()
        await utils.answer(message, "🧹 Буфер логов очищен")

    @loader.command()
    async def loglevelcmd(self, message: Message):
        """<уровень> — сменить уровень логирования в консоль"""
        args = utils.get_args_raw(message).strip().upper()

        if args not in log.LEVELS:
            current = next(
                (
                    handler.level
                    for handler in logging.getLogger().handlers
                    if type(handler) is logging.StreamHandler
                ),
                logging.INFO,
            )
            await utils.answer(
                message,
                f"📊 Текущий уровень: {utils.mono(logging.getLevelName(current))}\n"
                f"Доступны: {utils.mono(', '.join(log.LEVELS))}",
            )
            return

        for handler in logging.getLogger().handlers:
            # Строго StreamHandler: RotatingFileHandler — его наследник,
            # а файловый лог должен продолжать писать всё
            if type(handler) is logging.StreamHandler:
                handler.setLevel(log.LEVELS[args])

        await utils.answer(message, f"📊 Уровень логов: {utils.mono(args)}")

    # ------------------------------------------------------------------ #
    #                               diagnostics                           #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def debugmodscmd(self, message: Message):
        """Состояние загруженных модулей"""
        core, plain, broken = [], [], []

        for module in sorted(
            self.allmodules.modules,
            key=lambda m: m.__class__.__name__,
        ):
            entry = (
                f"{module.__class__.__name__} — "
                f"команд {len(module.commands)}, вотчеров {len(module.watchers)}"
            )

            if not module.commands and not module.watchers:
                broken.append(entry)
            elif str(getattr(module, "__origin__", "")).startswith("<core"):
                core.append(entry)
            else:
                plain.append(entry)

        blocks = [utils.heading(f"🧩 Модули — {len(self.allmodules.modules)}")]

        for title, items in (
            (f"🛡 **Системные — {len(core)}**", core),
            (f"🧩 **Пользовательские — {len(plain)}**", plain),
            (f"❔ **Без команд — {len(broken)}**", broken),
        ):
            if items:
                blocks.append(f"{title}\n{utils.quote(chr(10).join(items))}")

        await utils.answer(message, utils.smart_truncate("\n".join(blocks)))

    @loader.command()
    async def suspendcmd(self, message: Message):
        """<секунды> — приостановить обработку команд"""
        args = utils.get_args_raw(message).strip()

        if not args.isdigit():
            await utils.answer(message, "❌ Укажи количество секунд")
            return

        seconds = min(int(args), 3600)
        await utils.answer(message, f"⏸ Засыпаю на {seconds} с")
        await asyncio.sleep(seconds)
        logger.info("Resumed after %s seconds of suspension", seconds)

    @loader.command()
    async def dumpcmd(self, message: Message):
        """Показать сырое содержимое сообщения, на которое отвечаешь"""
        reply = await utils.get_reply(message)
        target = reply or message

        await utils.answer(
            message,
            f"🧾 **Message {target.id}**\n"
            + utils.quote(target.model_dump_json(indent=2, exclude_none=True)),
        )
