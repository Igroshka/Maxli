# ©️ Maxli, 2026
# This file is a part of Maxli Userbot
# 🌐 https://github.com/Igroshka/Maxli
# Портировано с heroku/modules/eval.py (AGPLv3)

# meta developer: @YouRooni
# scope: maxli_only

from __future__ import annotations

import ast
import asyncio
import contextlib
import io
import json
import time
import traceback
import typing

import pymax
from pymax import Message

from .. import loader, main, utils


@loader.tds
class EvalMod(loader.Module):
    """Выполнение Python-кода внутри юзербота"""

    strings = {
        "name": "Eval",
        "result": "Результат",
        "error": "Ошибка",
        "empty": "❌ Нечего выполнять",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "show_code",
                True,
                lambda: "Показывать исходный код в ответе",
                validator=loader.validators.Boolean(),
            ),
        )

    async def _namespace(self, message: Message) -> dict:
        reply = await utils.get_reply(message)
        chat_id = utils.get_chat_id(message)

        return {
            "message": message,
            "m": message,
            "reply": reply,
            "r": reply,
            "client": self._client,
            "c": self._client,
            "chat": chat_id,
            "chat_id": chat_id,
            "db": self._db,
            "self": self,
            "loader": loader,
            "utils": utils,
            "main": main,
            "modules": self.allmodules,
            "lookup": self.lookup,
            "pymax": pymax,
            "json": json,
            "time": time,
            "asyncio": asyncio,
        }

    @loader.owner
    @loader.command(alias="e")
    async def evalcmd(self, message: Message):
        """<код> — выполнить Python-код (доступны: r, m, c, db, self, utils)"""
        code = utils.get_args_raw(message)
        reply = await utils.get_reply(message)

        if not code and reply and getattr(reply, "text", None):
            code = reply.text

        if not code:
            await utils.answer(message, self.strings["empty"])
            return

        namespace = await self._namespace(message)
        stdout = io.StringIO()

        wrapper = "async def __maxli_eval__():\n" + "\n".join(
            f"    {line}" for line in code.splitlines()
        )

        start_time = time.perf_counter()
        is_error = False

        try:
            tree = ast.parse(wrapper)
            body = tree.body[0].body

            # Последнее выражение возвращаем автоматически
            if body and isinstance(body[-1], ast.Expr):
                body[-1] = ast.Return(value=body[-1].value)
                ast.fix_missing_locations(tree)

            exec(compile(tree, "<eval>", "exec"), namespace)  # noqa: S102

            with contextlib.redirect_stdout(stdout):
                result = await namespace["__maxli_eval__"]()
        except Exception:
            is_error = True
            result = traceback.format_exc()

        exec_time = time.perf_counter() - start_time
        print_output = stdout.getvalue()

        formatted_result = self._format_result_value(result)

        text = self._format(
            code=code,
            output=formatted_result,
            print_output=print_output,
            exec_time=exec_time,
            error=is_error,
        )

        if len(text) > 4000:
            full_out = f"Code:\n{code}\n\n"
            if print_output:
                full_out += f"Stdout:\n{print_output}\n\n"
            full_out += f"Result ({exec_time:.3f}s):\n{formatted_result}"

            await utils.answer_file(
                message,
                full_out.encode("utf-8"),
                caption=f"{'🚫 Ошибка' if is_error else '✅ Результат'} ({exec_time:.2f}с)",
                name="eval_result.txt",
            )
            return

        await utils.answer(message, text)

    @staticmethod
    def _format_result_value(val: typing.Any) -> str:
        """Форматирует результат в JSON или читаемый вид."""
        if val is None:
            return "None"

        # Pydantic модели PyMax (Message, Chat, User и т.д.)
        if hasattr(val, "model_dump_json"):
            with contextlib.suppress(Exception):
                return val.model_dump_json(indent=2)

        if hasattr(val, "model_dump"):
            with contextlib.suppress(Exception):
                return json.dumps(val.model_dump(), indent=2, ensure_ascii=False, default=str)

        if hasattr(val, "dict"):
            with contextlib.suppress(Exception):
                return json.dumps(val.dict(), indent=2, ensure_ascii=False, default=str)

        if isinstance(val, (dict, list)):
            with contextlib.suppress(Exception):
                return json.dumps(val, indent=2, ensure_ascii=False, default=str)

        return repr(val)

    def _format(
        self,
        code: str,
        output: str,
        print_output: str = "",
        exec_time: float = 0.0,
        error: bool = False,
    ) -> str:
        parts = []

        if self.config["show_code"]:
            parts.append(f"🧬 **Код:**\n{utils.quote(utils.smart_truncate(code, 1500))}")

        if print_output:
            parts.append(f"🖨 **Вывод (stdout):**\n{utils.quote(utils.smart_truncate(print_output.strip(), 1000))}")

        icon = "🚫" if error else "✅"
        label = self.strings["error"] if error else self.strings["result"]
        time_str = f"{exec_time * 1000:.1f}мс" if exec_time < 1 else f"{exec_time:.2f}с"

        parts.append(f"{icon} **{label}** (⏱ {time_str}):\n{utils.quote(utils.smart_truncate(output, 2000))}")

        return "\n\n".join(parts)

    @loader.owner
    @loader.command()
    async def dbcmd(self, message: Message):
        """[namespace] [ключ] — посмотреть содержимое базы данных"""
        args = utils.get_args(message)

        if not args:
            owners = "\n".join(f"▫️ {utils.mono(owner)}" for owner in sorted(self._db))
            await utils.answer(
                message,
                f"🗃 **Namespace-ы БД:**\n{utils.quote(owners or '▫️ пусто')}",
            )
            return

        if len(args) == 1:
            data = dict(self._db).get(args[0], {})
            data_str = json.dumps(data, indent=2, ensure_ascii=False, default=str)
            await utils.answer(
                message,
                f"🗃 {utils.mono(args[0])}:\n{utils.quote(data_str)}",
            )
            return

        value = self._db.get(args[0], args[1])
        val_str = (
            json.dumps(value, indent=2, ensure_ascii=False, default=str)
            if isinstance(value, (dict, list))
            else repr(value)
        )
        await utils.answer(
            message,
            f"🗃 {utils.mono(f'{args[0]}.{args[1]}')}:\n{utils.quote(val_str)}",
        )
