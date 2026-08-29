# ©️ Maxli, 2026
# This file is a part of Maxli Userbot
# 🌐 https://github.com/Igroshka/Maxli
# Портировано с heroku/modules/quickstart.py (AGPLv3)

# meta developer: @Igroshka
# scope: maxli_only

import logging

from pymax import Message

from .. import loader, utils, version

logger = logging.getLogger(__name__)


@loader.tds
class QuickstartMod(loader.Module):
    """Приветствие и краткая инструкция при первом запуске"""

    strings = {"name": "Quickstart"}

    async def client_ready(self):
        if self.get("greeted"):
            return

        chat_id = await utils.get_self_chat_id()

        if chat_id is None:
            logger.debug("Self chat is not resolved yet, will greet next time")
            return

        try:
            await self._client.send_message(chat_id, self._greeting())
        except Exception:
            logger.debug("Could not send quickstart greeting", exc_info=True)
            return

        # Флаг ставим только после успешной отправки, иначе приветствие
        # потеряется навсегда из-за одной неудачи на старте
        self.set("greeted", True)

    def _greeting(self) -> str:
        prefix = self.get_prefix()

        def block(title: str, rows: list[str]) -> str:
            return f"{title}\n" + utils.quote("\n".join(rows))

        return "\n".join(
            [
                utils.heading(f"🌌 Maxli v{version.pretty()} запущен"),
                utils.quote(
                    "Юзербот работает прямо из твоего аккаунта MAX: пишешь команду "
                    "в любом чате — она выполняется, а сообщение превращается в ответ."
                ),
                block(
                    "**С чего начать**",
                    [
                        f"{prefix}help — все модули и команды",
                        f"{prefix}info — состояние юзербота",
                        f"{prefix}setprefix ! — сменить префикс",
                        f"{prefix}setlang en — переключить язык",
                    ],
                ),
                block(
                    "**Модули**",
                    [
                        f"{prefix}dlmod <имя> — поставить из репозитория",
                        f"{prefix}loadmod <ссылка> — поставить по прямой ссылке",
                        f"{prefix}unloadmod <имя> — удалить модуль",
                    ],
                ),
                block(
                    "**Возможности MAX**",
                    [
                        f"{prefix}chats <запрос> — найти чат",
                        f"{prefix}newgroup <название> — создать группу",
                        f"{prefix}user — профиль в ответ на сообщение",
                    ],
                ),
                block(
                    "**Безопасность**",
                    [
                        f"{prefix}owneradd <id> — дать полный доступ",
                        f"{prefix}security <команда> <флаги> — права команды",
                    ],
                ),
                f"Показать снова: {utils.mono(prefix + 'quickstart')}",
            ]
        )

    @loader.command()
    async def quickstartcmd(self, message: Message):
        """Показать инструкцию для начинающих"""
        await utils.answer(message, self._greeting())
