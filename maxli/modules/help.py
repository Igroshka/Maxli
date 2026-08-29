# ©️ Maxli, 2026
# This file is a part of Maxli Userbot
# 🌐 https://github.com/Igroshka/Maxli
# Архитектура основана на Heroku Userbot (AGPLv3)

# meta developer: @Igroshka
# scope: maxli_only

from pymax import Message

from .. import loader, utils, version


@loader.tds
class HelpMod(loader.Module):
    """Показывает список модулей и команд"""

    strings = {"name": "Help"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "empty_modules",
                False,
                lambda: "Показывать модули без команд",
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "core_emoji",
                "🛡",
                lambda: "Эмодзи системного модуля",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "plain_emoji",
                "🧩",
                lambda: "Эмодзи пользовательского модуля",
                validator=loader.validators.String(),
            ),
        )

    @staticmethod
    def _is_core(module: loader.Module) -> bool:
        return str(getattr(module, "__origin__", "")).startswith("<core")

    def _emoji(self, module: loader.Module) -> str:
        return self.config["core_emoji"] if self._is_core(module) else self.config["plain_emoji"]

    @staticmethod
    def _short_doc(func) -> str:
        doc = (func.__doc__ or "Без описания").strip()
        return doc.splitlines()[0] if doc else "Без описания"

    def _module_help(self, module: loader.Module) -> str:
        prefix = self.get_prefix()
        doc = (module.__doc__ or self.strings["no_desc"]).strip()

        body = [utils.unmark(doc), ""]
        body += [
            f"{prefix}{name} — {utils.unmark(self._short_doc(func))}"
            for name, func in sorted(module.commands.items())
        ]

        if module.watchers:
            body.append(f"👁 вотчеров: {len(module.watchers)}")

        placeholders = utils.help_placeholders(module.__class__.__name__)
        if placeholders:
            body.append("")
            body.append("📌 **Плейсхолдеры:**")
            body += [f"  • {ph}" for ph in placeholders]

        developer = (getattr(module, "__meta__", None) or {}).get("developer")
        if developer:
            body.append(f"👤 {utils.unmark(developer)}")

        return (
            f"{self._emoji(module)} **{module.strings['name']}**\n"
            + utils.quote("\n".join(body))
        )

    @loader.command(alias="h")
    async def helpcmd(self, message: Message):
        """[модуль] — список модулей или справка по одному модулю"""
        args = utils.get_args_raw(message)

        if args:
            module = self.lookup(args)

            if not module:
                await utils.answer(message, self.strings["bad_module"].format(args))
                return

            await utils.answer(message, self._module_help(module))
            return

        prefix = self.get_prefix()
        core, plain = [], []

        for module in sorted(
            self.allmodules.modules,
            key=lambda m: str(m.strings["name"]).lower(),
        ):
            if not module.commands and not self.config["empty_modules"]:
                continue

            # Каждый модуль — отдельная цитата: список команд не сливается
            # с соседними и его удобно читать
            entry = (
                f"{self._emoji(module)} **{module.strings['name']}**\n"
                + utils.quote(
                    " ".join(f"{prefix}{cmd}" for cmd in sorted(module.commands))
                )
            )

            (core if self._is_core(module) else plain).append(entry)

        header = self.strings["all_header"].format(
            len(self.allmodules.modules),
            len(self.allmodules.commands),
        )

        text = "\n".join(
            [utils.heading(f"🌌 Maxli v{version.pretty()}"), f"_{header}_", ""]
            + core
            + plain
        )
        await utils.answer(message, utils.smart_truncate(text))

    @loader.command()
    async def modinfocmd(self, message: Message):
        """<модуль> — подробная информация о модуле"""
        args = utils.get_args_raw(message)
        module = self.lookup(args) if args else None

        if not module:
            await utils.answer(message, self.strings["bad_module"].format(args))
            return

        meta = getattr(module, "__meta__", None) or {}

        text = f"{self._emoji(module)} **{module.strings['name']}**\n" + utils.quote(
            "\n".join(
                [
                    f"класс: {module.__class__.__name__}",
                    f"источник: {getattr(module, '__origin__', '?')}",
                    f"версия: {getattr(module, '__version__', '—')}",
                    f"разработчик: {utils.unmark(meta.get('developer', '—'))}",
                    f"команд: {len(module.commands)}, вотчеров: {len(module.watchers)}",
                ]
            )
        )
        await utils.answer(message, text)
