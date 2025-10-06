import asyncio
import json
from typing import Any, override

import websockets

from pymax.exceptions import WebSocketNotConnectedError
from pymax.interfaces import ClientProtocol
from pymax.payloads import BaseWebSocketMessage, SyncPayload
from pymax.static import ChatType, Constants, Opcode
from pymax.types import Channel, Chat, Dialog, Me, Message


class WebSocketMixin(ClientProtocol):
    @property
    def ws(self) -> websockets.ClientConnection:
        if self._ws is None or not self.is_connected:
            self.logger.critical("WebSocket not connected when access attempted")
            raise WebSocketNotConnectedError
        return self._ws

    def _make_message(
        self, opcode: int, payload: dict[str, Any], cmd: int = 0
    ) -> dict[str, Any]:
        self._seq += 1

        msg = BaseWebSocketMessage(
            ver=11,
            cmd=cmd,
            seq=self._seq,
            opcode=opcode,
            payload=payload,
        ).model_dump(by_alias=True)

        self.logger.debug(
            "make_message opcode=%s cmd=%s seq=%s", opcode, cmd, self._seq
        )
        return msg

    async def _send_interactive_ping(self) -> None:
        while self.is_connected:
            try:
                await self._send_and_wait(
                    opcode=1,
                    payload={"interactive": True},
                    cmd=0,
                )
                self.logger.debug("Interactive ping sent successfully")
            except Exception:
                self.logger.warning("Interactive ping failed", exc_info=True)
            await asyncio.sleep(30)

    async def _connect(self, user_agent: dict[str, Any]) -> dict[str, Any]:
        try:
            self.logger.info("Connecting to WebSocket %s", self.uri)
            # Cancel and await any previous recv_task to avoid concurrency errors
            if self._recv_task and not self._recv_task.done():
                self._recv_task.cancel()
                try:
                    await self._recv_task
                except asyncio.CancelledError:
                    self.logger.debug("Previous recv_task cancelled before reconnect")
            self._ws = await websockets.connect(self.uri, origin="https://web.max.ru")
            self.is_connected = True
            self._incoming = asyncio.Queue()
            self._pending = {}
            self._recv_task = asyncio.create_task(self._recv_loop())
            self.logger.info("WebSocket connected, starting handshake")
            return await self._handshake(user_agent)
        except Exception as e:
            self.logger.error("Failed to connect: %s", e, exc_info=True)
            raise ConnectionError(f"Failed to connect: {e}")

    async def _handshake(self, user_agent: dict[str, Any]) -> dict[str, Any]:
        try:
            self.logger.debug(
                "Sending handshake with user_agent keys=%s", list(user_agent.keys())
            )
            resp = await self._send_and_wait(
                opcode=Opcode.SESSION_INIT,
                payload={"deviceId": str(self._device_id), "userAgent": user_agent},
            )
            self.logger.info("Handshake completed")
            return resp
        except Exception as e:
            self.logger.error("Handshake failed: %s", e, exc_info=True)
            raise ConnectionError(f"Handshake failed: {e}")

    async def _recv_loop(self) -> None:
        if self._ws is None:
            self.logger.warning("Recv loop started without websocket instance")
            return

        self.logger.debug("Receive loop started")
        while True:
            try:
                raw = await self._ws.recv()
                try:
                    data = json.loads(raw)
                except Exception:
                    self.logger.warning("JSON parse error", exc_info=True)
                    continue

                seq = data.get("seq")
                fut = self._pending.get(seq) if isinstance(seq, int) else None

                if fut and not fut.done():
                    fut.set_result(data)
                    self.logger.debug("Matched response for pending seq=%s", seq)
                else:
                    if self._incoming is not None:
                        try:
                            self._incoming.put_nowait(data)
                        except asyncio.QueueFull:
                            self.logger.warning(
                                "Incoming queue full; dropping message seq=%s",
                                data.get("seq"),
                            )

                    if (
                        data.get("opcode") == Opcode.NOTIF_MESSAGE
                        and self._on_message_handlers
                    ):
                        try:
                            for handler, filter in self._on_message_handlers:
                                payload = data.get("payload", {})
                                
                                # Отладочный вывод полного payload для команды load
                                if payload.get("message", {}).get("text", "").startswith(",lm"):
                                    print("🔍 DEBUG: Полный необработанный JSON payload:")
                                    import json as json_module
                                    print(json_module.dumps(payload, indent=2, ensure_ascii=False))
                                    
                                    print("\n🔍 DEBUG: Структура payload:")
                                    print(f"   Payload keys: {list(payload.keys())}")
                                    if "message" in payload:
                                        msg_data = payload["message"]
                                        print(f"   Message keys: {list(msg_data.keys())}")
                                        if "replyToMessage" in msg_data:
                                            print(f"   Reply to message: {msg_data['replyToMessage']}")
                                        else:
                                            print("   Reply to message: НЕТ")
                                            
                                        # Проверяем все возможные варианты полей ответа
                                        reply_fields = [k for k in msg_data.keys() if 'reply' in k.lower() or 'answer' in k.lower() or 'response' in k.lower()]
                                        if reply_fields:
                                            print(f"   Найдены поля связанные с ответом: {reply_fields}")
                                            for field in reply_fields:
                                                print(f"     {field}: {msg_data[field]}")
                                        else:
                                            print("   Поля связанные с ответом: НЕТ")
                                
                                msg = Message.from_dict(payload.get("message"))
                                if msg:
                                    if msg.status:
                                        continue  # TODO: заглушка! сделать отдельный хендлер
                                    
                                    # Добавляем chat_id из payload в сообщение
                                    chat_id = payload.get("chatId")
                                    if chat_id:
                                        msg.chat_id = chat_id
                                        print(f"🔧 PyMax: добавлен chat_id {chat_id} к сообщению {msg.id}")
                                        self.logger.debug(f"Added chat_id {chat_id} to message {msg.id}")
                                    else:
                                        # Fallback для чата "Избранное" - используем специальный ID
                                        if hasattr(self, 'me') and self.me and msg.sender == self.me.id:
                                            # Для чата "Избранное" используем специальный ID
                                            # В Max чат "Избранное" часто имеет ID равный ID пользователя
                                            msg.chat_id = self.me.id
                                            print(f"🔧 PyMax: установлен chat_id для 'Избранного': {self.me.id} к сообщению {msg.id}")
                                        else:
                                            print(f"⚠️ PyMax: chat_id не найден в payload для сообщения {msg.id}")
                                            print(f"   Payload keys: {list(payload.keys())}")
                                    
                                    # Обрабатываем поле link для ответов на сообщения
                                    message_data = payload.get("message", {})
                                    if "link" in message_data and message_data["link"].get("type") == "REPLY":
                                        reply_data = message_data["link"].get("message", {})
                                        if reply_data:
                                            msg.reply_to_message = reply_data
                                            print(f"🔧 PyMax: добавлен reply_to_message к сообщению {msg.id}")
                                            print(f"   Reply message ID: {reply_data.get('id')}")
                                            print(f"   Reply message attaches: {len(reply_data.get('attaches', []))}")
                                    
                                    if filter:
                                        if filter.match(msg):
                                            result = handler(msg)
                                        else:
                                            continue
                                    else:
                                        result = handler(msg)
                                    if asyncio.iscoroutine(result):
                                        task = asyncio.create_task(result)
                                        self._background_tasks.add(task)
                                        task.add_done_callback(
                                            lambda t: self._background_tasks.discard(t)
                                            or self._log_task_exception(t)
                                        )
                        except Exception:
                            self.logger.exception("Error in on_message_handler")

            except websockets.exceptions.ConnectionClosed as e:
                msg = "[connection] WebSocket connection closed; exiting recv loop (network issue?)"
                self.logger.warning(msg)
                try:
                    from core.api import LOG_BUFFER, _append_log
                    _append_log(msg)
                except Exception:
                    pass
                break
            except Exception as e:
                err_msg = f"[connection] Error in recv_loop: {e}"
                self.logger.exception(err_msg)
                try:
                    from core.api import LOG_BUFFER, _append_log
                    _append_log(err_msg)
                except Exception:
                    pass
                await asyncio.sleep(0.5)

    def _log_task_exception(self, task: asyncio.Task[Any]) -> None:
        try:
            # Если задача была отменена, task.exception() может выбросить CancelledError.
            # В этом случае ничего не логируем — это нормальное завершение при закрытии.
            if task.cancelled():
                self.logger.debug("Background task was cancelled, skipping exception check")
                return
            exc = task.exception()
            if exc:
                self.logger.exception("Background task exception: %s", exc)
        except asyncio.CancelledError:
            # Игнорируем отмену — может произойти при одновременном закрытии
            return
        except Exception:
            # Любые другие ошибки при получении исключения задачи логируем на debug
            self.logger.debug("Error while fetching task exception", exc_info=True)

    @override
    async def _send_and_wait(
        self,
        opcode: int,
        payload: dict[str, Any],
        cmd: int = 0,
        timeout: float = Constants.DEFAULT_TIMEOUT.value,
    ) -> dict[str, Any]:
        ws = self.ws

        msg = self._make_message(opcode, payload, cmd)
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[msg["seq"]] = fut

        try:
            self.logger.debug(
                "Sending frame opcode=%s cmd=%s seq=%s", opcode, cmd, msg["seq"]
            )
            await ws.send(json.dumps(msg))
            data = await asyncio.wait_for(fut, timeout=timeout)
            self.logger.debug(
                "Received frame for seq=%s opcode=%s",
                data.get("seq"),
                data.get("opcode"),
            )
            return data
        except Exception:
            self.logger.exception(
                "Send and wait failed (opcode=%s, seq=%s)", opcode, msg["seq"]
            )
            raise RuntimeError("Send and wait failed")
        finally:
            self._pending.pop(msg["seq"], None)

    async def _sync(self) -> None:
        try:
            self.logger.info("Starting initial sync")

            payload = SyncPayload(
                interactive=True,
                token=self._token,
                chats_sync=0,
                contacts_sync=0,
                presence_sync=0,
                drafts_sync=0,
                chats_count=40,
            ).model_dump(by_alias=True)

            data = await self._send_and_wait(opcode=19, payload=payload)
            raw_payload = data.get("payload", {})

            if error := raw_payload.get("error"):
                self.logger.error("Sync error: %s", error)
                return

            for raw_chat in raw_payload.get("chats", []):
                try:
                    if raw_chat.get("type") == ChatType.DIALOG.value:
                        self.dialogs.append(Dialog.from_dict(raw_chat))
                    elif raw_chat.get("type") == ChatType.CHAT.value:
                        self.chats.append(Chat.from_dict(raw_chat))
                    elif raw_chat.get("type") == ChatType.CHANNEL.value:
                        self.channels.append(Channel.from_dict(raw_chat))
                except Exception:
                    self.logger.exception("Error parsing chat entry")

            if raw_payload.get("profile", {}).get("contact"):
                self.me = Me.from_dict(
                    raw_payload.get("profile", {}).get("contact", {})
                )

            self.logger.info(
                "Sync completed: dialogs=%d chats=%d channels=%d",
                len(self.dialogs),
                len(self.chats),
                len(self.channels),
            )
        except Exception:
            self.logger.exception("Sync failed")

    @override
    async def _get_chat(self, chat_id: int) -> Chat | None:
        for chat in self.chats:
            if chat.id == chat_id:
                return chat
        return None
