# ©️ Maxli, 2026
# This file is a part of Maxli Userbot
# 🌐 https://github.com/Igroshka/Maxli

# meta developer: @Igroshka
# scope: maxli_only

from pymax import Message

from .. import loader, utils, validators


@loader.tds
class MaxliConfigMod(loader.Module):
    """Управление настройками модулей"""

    strings = {
        "name": "Config",
        "no_mod": "❌ Модуль {} не найден",
        "no_cfg": "❌ У модуля {} нет настроек",
        "set": "⚙️ **{}.{}** = {}",
        "invalid": "❌ Некорректное значение: {}",
    }

    def _render_module(self, module: loader.Module) -> str:
        prefix = self.get_prefix()
        blocks = [utils.heading(f"⚙️ Настройки {utils.unmark(module.strings['name'])}")]

        for category, options in module.config.grouped_options().items():
            if category:
                blocks.append(f"**— {category} —**")

            for option in options:
                value = module.config[option]
                changed = "" if value == module.config.getdef(option) else " ✏️"

                # Каждая опция — своя цитата: значение и описание не расползаются
                blocks.append(
                    f"▫️ **{option}**{changed}\n"
                    + utils.quote(
                        f"{value}\n{utils.unmark(module.config.getdoc(option))}"
                    )
                )

        blocks.append(
            "Изменить: "
            + utils.mono(f"{prefix}cfg {module.__class__.__name__} <опция> <значение>")
        )
        return "\n".join(blocks)

    @loader.command(alias="cfg")
    async def configcmd(self, message: Message):
        """[модуль] [опция] [значение] — посмотреть или изменить настройки"""
        args = utils.get_args(message)

        if not args:
            configurable = [
                mod for mod in self.allmodules.modules if getattr(mod, "config", None)
            ]

            listing = utils.quote(
                "\n".join(
                    f"{mod.__class__.__name__} — {utils.unmark(mod.strings['name'])}"
                    for mod in sorted(configurable, key=lambda m: m.__class__.__name__)
                )
            )
            await utils.answer(
                message,
                utils.heading("⚙️ Модули с настройками") + "\n" + listing,
            )
            return

        clean_mod = utils.unmark(args[0]).strip("*:_`\"' ")
        module = self.lookup(clean_mod) or self.lookup(args[0])

        if not module:
            await utils.answer(message, self.strings["no_mod"].format(args[0]))
            return

        if not getattr(module, "config", None):
            await utils.answer(message, self.strings["no_cfg"].format(args[0]))
            return

        if len(args) == 1:
            await utils.answer(message, self._render_module(module))
            return

        clean_opt = utils.unmark(args[1]).strip("*:_`\"' ")
        # Ищем опцию без учета регистра и спецсимволов
        matched_option = next(
            (opt for opt in module.config if opt.lower() == clean_opt.lower()),
            clean_opt,
        )

        if matched_option not in module.config:
            await utils.answer(
                message,
                f"❌ У модуля **{module.strings['name']}** нет опции {utils.mono(clean_opt)}",
            )
            return

        if len(args) == 2:
            await utils.answer(
                message,
                f"⚙️ **{matched_option}**\n"
                + utils.quote(
                    f"{module.config[matched_option]}\n"
                    f"{utils.unmark(module.config.getdoc(matched_option))}\n"
                    f"по умолчанию: {module.config.getdef(matched_option)}"
                ),
            )
            return

        raw = utils.get_args_raw(message)
        raw_parts = raw.split(maxsplit=2)
        value_to_set = raw_parts[2] if len(raw_parts) > 2 else " ".join(args[2:])
        value_to_set = value_to_set.strip("`\"'")

        try:
            module.config[matched_option] = value_to_set
        except validators.ValidationError as e:
            await utils.answer(message, self.strings["invalid"].format(e.message))
            return

        self.allmodules.save_config(module)

        await utils.answer(
            message,
            self.strings["set"].format(
                module.__class__.__name__,
                matched_option,
                module.config[matched_option],
            ),
        )

    @loader.command()
    async def resetcfgcmd(self, message: Message):
        """<модуль> [опция] — сбросить настройки к значениям по умолчанию"""
        args = utils.get_args(message)

        if not args:
            await utils.answer(message, "❌ Укажи модуль")
            return

        module = self.lookup(args[0])

        if not module or not getattr(module, "config", None):
            await utils.answer(message, self.strings["no_cfg"].format(args[0]))
            return

        options = [args[1]] if len(args) > 1 else list(module.config)

        for option in options:
            if option in module.config:
                module.config.set_no_raise(option, module.config.getdef(option))

        self.allmodules.save_config(module)
        await utils.answer(message, f"♻️ Сброшено: {utils.mono(', '.join(options))}")
