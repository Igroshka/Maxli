# ©️ Maxli, 2026
# This file is a part of Maxli Userbot
# 🌐 https://github.com/Igroshka/Maxli
# Портировано с heroku/modules/heroku_security.py (AGPLv3)

# meta developer: @Igroshka
# scope: maxli_only

import time

from pymax import Message

from .. import loader, security, utils


@loader.tds
class MaxliSecurityMod(loader.Module):
    """Права доступа: владельцы, sudo, support, группы и точечные разрешения"""

    strings = {"name": "MaxliSecurity"}

    #: Человекочитаемые названия битов прав
    MASKS = {
        "owner": security.OWNER,
        "sudo": security.SUDO,
        "support": security.SUPPORT,
        "chat_owner": security.CHAT_OWNER,
        "chat_admin": security.CHAT_ADMIN,
        "chat_member": security.CHAT_MEMBER,
        "pm": security.PM,
        "everyone": security.EVERYONE,
    }

    @property
    def _sec(self) -> security.SecurityManager:
        return self.allmodules.security

    @staticmethod
    def _render_flags(flags: int) -> str:
        active = [name for name, bit in MaxliSecurityMod.MASKS.items() if flags & bit]
        return ", ".join(active) or "никто"

    # ------------------------------------------------------------------ #
    #                             command masks                           #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def securitycmd(self, message: Message):
        """[команда] [флаги] — посмотреть или изменить права команды

        Флаги через запятую: owner, sudo, support, chat_owner, chat_admin,
        chat_member, pm, everyone
        """
        args = utils.get_args(message)

        if not args:
            masks = self._db.get(security.__name__, "masks", {})

            body = [
                f"{key} — {self._render_flags(int(value))}"
                for key, value in sorted(masks.items())
            ] or ["изменённых прав нет"]

            body.append("")
            body.append(
                "по умолчанию: "
                + self._render_flags(
                    self._db.get(
                        security.__name__,
                        "default_permissions",
                        security.DEFAULT_PERMISSIONS,
                    )
                )
            )

            await utils.answer(
                message,
                utils.heading("🛡 Права команд") + "\n" + utils.quote("\n".join(body)),
            )
            return

        command = args[0].lower()
        func = self.allmodules.commands.get(command)

        if func is None:
            await utils.answer(message, f"❌ Команда {utils.mono(command)} не найдена")
            return

        if len(args) == 1:
            await utils.answer(
                message,
                f"🛡 {utils.mono(command)}: {self._render_flags(self._sec.get_flags(func))}",
            )
            return

        flags = 0
        unknown = []

        for token in " ".join(args[1:]).replace(",", " ").split():
            bit = self.MASKS.get(token.lower())
            if bit is None:
                unknown.append(token)
            else:
                flags |= bit

        if unknown:
            await utils.answer(message, f"❌ Неизвестные флаги: {utils.mono(', '.join(unknown))}")
            return

        self._sec.set_flags(func, flags)
        await utils.answer(
            message,
            f"🛡 {utils.mono(command)} → {self._render_flags(flags)}",
        )

    # ------------------------------------------------------------------ #
    #                                owners                               #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def owneraddcmd(self, message: Message):
        """<id | ответом> — выдать права владельца"""
        user_id = await utils.get_target_id(message, utils.get_args_raw(message))

        if user_id is None:
            await utils.answer(message, "❌ Не понял, кому выдавать права")
            return

        self._sec.add_owner(user_id)
        await utils.answer(message, f"👑 {utils.mono(user_id)} — владелец")

    @loader.command()
    async def ownerrmcmd(self, message: Message):
        """<id | ответом> — забрать права владельца"""
        user_id = await utils.get_target_id(message, utils.get_args_raw(message))

        if user_id is None:
            await utils.answer(message, "❌ Не понял, у кого забирать права")
            return

        self._sec.remove_owner(user_id)
        await utils.answer(message, f"🚫 {utils.mono(user_id)} больше не владелец")

    @loader.command()
    async def ownerlistcmd(self, message: Message):
        """Показать владельцев, sudo и support"""
        def block(title: str, items: list) -> str:
            body = "\n".join(str(uid) for uid in items) or "пусто"
            return f"{title}\n{utils.quote(body)}"

        await utils.answer(
            message,
            "\n".join(
                [
                    block("👑 **Владельцы**", self._sec.owner),
                    block("🔑 **Sudo**", self._sec.sudo),
                    block("🛠 **Support**", self._sec.support),
                ]
            ),
        )

    @loader.command()
    async def sudoaddcmd(self, message: Message):
        """<id | ответом> — выдать sudo-права"""
        user_id = await utils.get_target_id(message, utils.get_args_raw(message))

        if user_id is None:
            await utils.answer(message, "❌ Не понял, кому выдавать права")
            return

        self._sec.add_sudo(user_id)
        await utils.answer(message, f"🔑 {utils.mono(user_id)} — sudo")

    @loader.command()
    async def sudormcmd(self, message: Message):
        """<id | ответом> — забрать sudo-права"""
        user_id = await utils.get_target_id(message, utils.get_args_raw(message))

        if user_id is None:
            await utils.answer(message, "❌ Не понял, у кого забирать права")
            return

        self._sec.remove_sudo(user_id)
        await utils.answer(message, f"🚫 {utils.mono(user_id)} больше не sudo")

    @loader.command()
    async def supportaddcmd(self, message: Message):
        """<id | ответом> — выдать support-права"""
        user_id = await utils.get_target_id(message, utils.get_args_raw(message))

        if user_id is None:
            await utils.answer(message, "❌ Не понял, кому выдавать права")
            return

        self._sec.add_support(user_id)
        await utils.answer(message, f"🛠 {utils.mono(user_id)} — support")

    @loader.command()
    async def supportrmcmd(self, message: Message):
        """<id | ответом> — забрать support-права"""
        user_id = await utils.get_target_id(message, utils.get_args_raw(message))

        if user_id is None:
            await utils.answer(message, "❌ Не понял, у кого забирать права")
            return

        self._sec.remove_support(user_id)
        await utils.answer(message, f"🚫 {utils.mono(user_id)} больше не support")

    # ------------------------------------------------------------------ #
    #                           security groups                           #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def newsgroupcmd(self, message: Message):
        """<имя> [флаги] — создать группу безопасности"""
        args = utils.get_args(message)

        if not args:
            await utils.answer(message, "❌ Укажи имя группы")
            return

        flags = 0
        for token in " ".join(args[1:]).replace(",", " ").split():
            flags |= self.MASKS.get(token.lower(), 0)

        if not self._sec.create_sgroup(args[0], flags):
            await utils.answer(message, f"❌ Группа {utils.mono(args[0])} уже существует")
            return

        await utils.answer(
            message,
            f"👥 Группа **{args[0]}** создана — {self._render_flags(flags)}",
        )

    @loader.command()
    async def sgroupscmd(self, message: Message):
        """Список групп безопасности"""
        groups = self._sec.sgroups

        if not groups:
            await utils.answer(message, "👥 Групп безопасности нет")
            return

        blocks = [utils.heading("👥 Группы безопасности")]

        for group in groups.values():
            blocks.append(
                f"▫️ **{group.name}**\n"
                + utils.quote(
                    f"права: {self._render_flags(group.permissions)}\n"
                    f"участников: {len(group.users)}"
                )
            )

        await utils.answer(message, "\n".join(blocks))

    @loader.command()
    async def sgroupcmd(self, message: Message):
        """<имя> — состав группы безопасности"""
        args = utils.get_args_raw(message).strip()
        group = self._sec.sgroups.get(args)

        if group is None:
            await utils.answer(message, f"❌ Группа {utils.mono(args)} не найдена")
            return

        body = [f"права: {self._render_flags(group.permissions)}", ""]
        body += [str(uid) for uid in group.users] or ["участников нет"]

        await utils.answer(
            message,
            f"👥 **{group.name}**\n" + utils.quote("\n".join(body)),
        )

    @loader.command()
    async def sgroupaddcmd(self, message: Message):
        """<группа> <id | ответом> — добавить пользователя в группу"""
        args = utils.get_args(message)

        if not args:
            await utils.answer(message, "❌ Укажи группу")
            return

        user_id = await utils.get_target_id(message, args[1] if len(args) > 1 else "")

        if user_id is None:
            await utils.answer(message, "❌ Не понял, кого добавлять")
            return

        if not self._sec.sgroup_add_user(args[0], user_id):
            await utils.answer(message, f"❌ Группа {utils.mono(args[0])} не найдена")
            return

        await utils.answer(message, f"👥 {utils.mono(user_id)} добавлен в **{args[0]}**")

    @loader.command()
    async def sgroupdelcmd(self, message: Message):
        """<группа> <id | ответом> — убрать пользователя из группы"""
        args = utils.get_args(message)

        if not args:
            await utils.answer(message, "❌ Укажи группу")
            return

        user_id = await utils.get_target_id(message, args[1] if len(args) > 1 else "")

        if user_id is None:
            await utils.answer(message, "❌ Не понял, кого убирать")
            return

        if not self._sec.sgroup_remove_user(args[0], user_id):
            await utils.answer(message, f"❌ Группа {utils.mono(args[0])} не найдена")
            return

        await utils.answer(message, f"👥 {utils.mono(user_id)} убран из **{args[0]}**")

    @loader.command()
    async def delsgroupcmd(self, message: Message):
        """<имя> — удалить группу безопасности"""
        args = utils.get_args_raw(message).strip()

        if not self._sec.delete_sgroup(args):
            await utils.answer(message, f"❌ Группа {utils.mono(args)} не найдена")
            return

        await utils.answer(message, f"🗑 Группа **{args}** удалена")

    # ------------------------------------------------------------------ #
    #                          targeted security                          #
    # ------------------------------------------------------------------ #

    @loader.command()
    async def tseccmd(self, message: Message):
        """<id | ответом> <команда|$модуль> [часы] — точечно выдать доступ"""
        args = utils.get_args(message)

        if not args:
            await self._show_tsec(message)
            return

        if len(args) < 2:
            await utils.answer(message, "❌ Нужны цель и команда")
            return

        user_id = await utils.get_target_id(message, args[0])

        if user_id is None:
            await utils.answer(message, "❌ Не понял, кому выдавать доступ")
            return

        rule = args[1].lower()
        duration = int(args[2]) * 3600 if len(args) > 2 and args[2].isdigit() else 0

        self._sec.add_rule("user", user_id, rule, duration)

        expires = f" на {args[2]} ч" if duration else " бессрочно"
        await utils.answer(
            message,
            f"🎫 {utils.mono(user_id)} получил доступ к {utils.mono(rule)}{expires}",
        )

    async def _show_tsec(self, message: Message) -> None:
        rules = self._db.get(security.__name__, "tsec", {}).get("user", {})

        if not rules:
            await utils.answer(message, "🎫 Точечных правил нет")
            return

        now = round(time.time())
        lines = []

        for user_id, items in rules.items():
            active = [
                item["rule"]
                for item in items
                if not item.get("expires") or item["expires"] > now
            ]

            if active:
                lines.append(f"{user_id}: {', '.join(active)}")

        await utils.answer(
            message,
            utils.heading("🎫 Точечные разрешения")
            + "\n"
            + utils.quote("\n".join(lines) or "активных правил нет"),
        )

    @loader.command()
    async def tsecrmcmd(self, message: Message):
        """<id | ответом> — снять все точечные разрешения с пользователя"""
        user_id = await utils.get_target_id(message, utils.get_args_raw(message))

        if user_id is None:
            await utils.answer(message, "❌ Не понял, у кого снимать доступ")
            return

        if not self._sec.remove_rules("user", user_id):
            await utils.answer(message, f"❌ У {utils.mono(user_id)} нет правил")
            return

        await utils.answer(message, f"🎫 Правила {utils.mono(user_id)} сняты")

    @loader.command()
    async def tsecclrcmd(self, message: Message):
        """Снять все точечные разрешения"""
        self._db.set(security.__name__, "tsec", {})
        await utils.answer(message, "🎫 Все точечные разрешения сняты")
