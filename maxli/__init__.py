"""Maxli — модульный юзербот для мессенджера MAX.

Архитектура повторяет Heroku Userbot, транспорт — PyMax (``maxapi-python``).

Пример модуля::

    from maxli import loader, utils


    @loader.tds
    class HelloMod(loader.Module):
        \"\"\"Здоровается\"\"\"

        strings = {"name": "Hello"}

        @loader.command()
        async def hellocmd(self, message):
            \"\"\"Поздороваться\"\"\"
            await utils.answer(message, "Привет!")
"""

from .version import __version__, branch, version_code

__all__ = ("__version__", "branch", "version_code")
