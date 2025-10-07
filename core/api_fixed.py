import asyncio
import json
from pathlib import Path
import traceback
import aiohttp
import aiofiles

# --- КОНФИГУРАЦИЯ БОТА ---
BOT_NAME = "Maxli"
BOT_VERSION = "0.3.2" # Повышаем версию
BOT_VERSION_CODE = 33
MODULES_DIR = Path("modules")
LOG_BUFFER = []  # Глобальный буфер логов (последние строки)

def _append_log(text: str):
    import logging
    try:
        lines = text.splitlines()
        LOG_BUFFER.extend(lines)
        # Также пишем каждую строку в стандартный логгер
        logger = logging.getLogger("maxli.LOG_BUFFER")
        for line in lines:
            logger.info(line)
        # Ограничиваем размер буфера
        max_lines = 5000
        if len(LOG_BUFFER) > max_lines:
            del LOG_BUFFER[: len(LOG_BUFFER) - max_lines]
    except Exception:
        pass

# --- ФУНКЦИЯ ДЛЯ СУПЕР-ОТЛАДКИ ---
async def log_critical_error(e, message, client, chat_id=None):
    header = "\n" + "="*50 + "\n" + "!!! КРИТИЧЕСКАЯ ОШИБКА ВЫПОЛНЕНИЯ КОМАНДЫ !!!"\
        + f"\nКоманда: {getattr(message, 'text', '')}"\
        + f"\nОшибка: {e.__class__.__name__}: {e}\n"
    print(header)
    _append_log(header)
    print("--- JSON СООБЩЕНИЯ, ВЫЗВАВШЕГО ОШИБКУ ---")
    log_message_json(message, "")
    try:
        # Добавляем traceback в буфер логов
        tb = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
        _append_log(tb)
    except Exception:
        pass
    
    if not chat_id:
        print("--- Попытка найти chat_id для отладки... ---")
        temp_api_instance = API(client, {})
        temp_api_instance.set_me(client.me)
        chat_id = await temp_api_instance.await_chat_id(message)
        print(f"--- Результат поиска chat_id: {chat_id} ---")
    
    if chat_id:
        try:
            all_convs = client.dialogs + client.chats
            target_chat = next((c for c in all_convs if c.id == chat_id), None)
            if target_chat:
                print("--- JSON ЧАТА/ДИАЛОГА ---")
                print(json.dumps(target_chat.__dict__, indent=2, default=str))
        except Exception as debug_e:
            print(f"!!! Ошибка при сборе отладочной информации о чате: {debug_e} !!!")
    else:
        print("--- Не удалось определить chat_id для сбора полной информации о чате. ---")
    print("="*50 + "\n")
    
def log_message_json(message, prefix=""):
    if hasattr(message, '__dict__'):
        print(prefix + json.dumps(message.__dict__, indent=2, default=str))
    else:
        print(prefix + str(message))

# --- НАШ API НАД PYMAX ---
class API:
    def __init__(self, client_instance, config_instance):
        self.client = client_instance
        self.config = config_instance
        self.me = None
        self.last_known_chat_id = None # Память ТОЛЬКО для ответов на "Прр"
        self.message_to_chat_cache = {} # Кэш для связи message_id -> chat_id
        self.BOT_NAME = BOT_NAME
        self.BOT_VERSION = BOT_VERSION
        self.BOT_VERSION_CODE = BOT_VERSION_CODE
        # Доступ к буферу логов из инстанса
        self.LOG_BUFFER = LOG_BUFFER

    def set_me(self, me_instance):
        self.me = me_instance
    
    def update_last_known_chat_id(self, message):
        """Обновляет 'память' о последнем активном чате (только для ответов на 'Прр')."""
        # Простое обновление last_known_chat_id для ответов на "Прр"
        if hasattr(self, 'me') and self.me and message.sender != self.me.id:
            # Используем chat_id из сообщения, если он есть
            if hasattr(message, 'chat_id') and message.chat_id:
                self.last_known_chat_id = message.chat_id
                print(f"✅ Обновлен last_known_chat_id: {self.last_known_chat_id}")
            else:
                # Fallback: ищем по отправителю
                self.last_known_chat_id = message.sender
                print(f"⚠️ Fallback: last_known_chat_id <- sender = {self.last_known_chat_id}")

    async def await_chat_id(self, message):
        """Пытается получить chat_id из message.id. 
        Возвращает None если не удалось найти chat_id."""
        chat_id = getattr(message, 'chat_id', None)
        if chat_id is not None:
            return chat_id

        msg_id = getattr(message, 'id', None)
        if msg_id is None:
            print(f"⚠️ await_chat_id: не найден message.id")
            return None

        print(f"⚠️ await_chat_id: ждем chat_id для сообщения {msg_id}")
        start_time = asyncio.get_running_loop().time()
        max_wait_time = 10  # Максимальное время ожидания в секундах
        check_interval = 0.5  # Интервал проверки в секундах

        while True:
            # 1. Проверяем message на наличие chat_id (могло обновиться)
            if hasattr(message, 'chat_id') and message.chat_id is not None:
                return message.chat_id

            # 2. Проверяем кэш
            if msg_id in self.message_to_chat_cache:
                return self.message_to_chat_cache[msg_id]

            # 3. Ищем через клиент
            chats = self.client.dialogs + self.client.chats
            for chat in chats:
                if chat.last_message and getattr(chat.last_message, 'id', None) == msg_id:
                    chat_id = chat.id
                    self.message_to_chat_cache[msg_id] = chat_id  # Кэшируем
                    print(f"✅ await_chat_id: найден chat_id = {chat_id}")
                    return chat_id

            # 4. Проверяем таймаут
            elapsed_time = asyncio.get_running_loop().time() - start_time
            if elapsed_time >= max_wait_time:
                print(f"⚠️ await_chat_id: таймаут {max_wait_time} сек")
                return None

            # 5. Ждем и повторяем
            await asyncio.sleep(check_interval)

    async def edit(self, message, text, markdown=False, **kwargs):
        """Безопасно редактирует сообщение. 
        Если markdown=True, использует markdown-парсинг с поддержкой UTF-16 и элементов."""
        # Получаем chat_id
        chat_id = await self.await_chat_id(message)
        if chat_id is None:
            print(f"❌ Не удалось получить chat_id для редактирования")
            return None

        msg_id = getattr(message, "id", None)
        if msg_id is None:
            print(f"❌ Нет ID сообщения для редактирования")
            return None

        notify = kwargs.pop("notify", False)

        try:
            # Базовые параметры для редактирования
            edit_params = {
                "chat_id": chat_id,
                "message_id": msg_id,
                "notify": notify,
                **kwargs
            }

            # Если используется markdown
            if markdown:
                from pymax.markdown_parser import get_markdown_parser
                parser = get_markdown_parser()
                clean_text, elements = parser.parse(text)
                print(f"📝 Markdown парсинг: '{text}' -> '{clean_text}' с {len(elements)} элементами")
                print(f"🔍 Элементы: {elements}")

                # Пробуем отредактировать с элементами
                try:
                    edit_params["text"] = clean_text
                    edit_params["elements"] = elements
                    result = await self.client.edit_message(**edit_params)
                    if result:
                        print("✅ Сообщение отредактировано с элементами")
                        return result
                except TypeError:
                    print("⚠️ Клиент не поддерживает элементы, пробуем без них")
                except Exception as e:
                    print(f"⚠️ Ошибка при редактировании с элементами: {e}")

                # Если не получилось с элементами, пробуем только текст
                try:
                    del edit_params["elements"]
                    result = await self.client.edit_message(**edit_params)
                    if result:
                        print("✅ Сообщение отредактировано без элементов")
                        return result
                except Exception as e:
                    print(f"⚠️ Ошибка при редактировании без элементов: {e}")

            # Если markdown=False или все попытки с markdown не удались
            try:
                edit_params["text"] = text
                result = await self.client.edit_message(**edit_params)
                if result:
                    print("✅ Сообщение успешно отредактировано")
                    return result
            except Exception as e:
                print(f"⚠️ Ошибка при обычном редактировании: {e}")

            # Если все попытки редактирования не удались, отправляем новое
            print("⚠️ Не удалось отредактировать, отправляем новое сообщение")
            if markdown:
                return await self._send_message_with_elements(
                    chat_id=chat_id,
                    text=clean_text,
                    elements=elements,
                    notify=notify,
                    **kwargs
                )
            else:
                return await self.client.send_message(
                    chat_id=chat_id,
                    text=text,
                    notify=notify,
                    **kwargs
                )

        except Exception as e:
            print(f"❌ Критическая ошибка при редактировании: {e}")
            await log_critical_error(e, message, self.client, chat_id)
            return None
            
    async def send(self, chat_id, text, markdown=False, **kwargs):
        notify = kwargs.pop("notify", False)
        # Проверяем валидность chat_id (0 - это валидный ID для "Избранного")
        if chat_id is None:
            print(f"❌ Некорректный chat_id в send: {chat_id}")
            return None

        # Специальная обработка для чата "Избранное"
        if chat_id == 0:
            print(f"🔧 Отправка в чат 'Избранное' с ID: {chat_id}")
            print(f"🔧 Используем ID = 0 для отправки в 'Избранное'")

        # Если включен markdown, парсим текст
        if markdown:
            from pymax.markdown_parser import get_markdown_parser
            parser = get_markdown_parser()
            clean_text, elements = parser.parse(text)
            print(f"📝 Markdown парсинг: '{text}' -> '{clean_text}' с {len(elements)} элементами")
            print(f"🔍 Элементы: {elements}")

            # Отправляем сообщение с элементами форматирования
            return await self._send_message_with_elements(
                chat_id=chat_id, 
                text=clean_text, 
                elements=elements, 
                notify=notify, 
                **kwargs
            )
        else:
            return await self.client.send_message(
                text=text,
                chat_id=chat_id,
                notify=notify,
                **kwargs
            )
    
    async def _send_message_with_elements(self, chat_id, text, elements, notify=False, **kwargs):
        """Отправляет сообщение с элементами форматирования."""
        from pymax.static import Opcode
        from pymax.payloads import SendMessagePayload, SendMessagePayloadMessage
        import time

        # Проверяем валидность chat_id
        if chat_id is None:
            print(f"❌ Некорректный chat_id: {chat_id}")
            return None

        print(f"📤 Отправляем сообщение с форматированием в чат {chat_id}")
        print(f"   Текст: {text}")
        print(f"   Элементы: {elements}")

        # Создаем payload для сообщения с элементами
        message_payload = SendMessagePayloadMessage(
            text=text,
            cid=int(time.time() * 1000),
            elements=elements,
            attaches=[],
            link=None
        )

        payload = SendMessagePayload(
            chat_id=chat_id,
            message=message_payload,
            notify=notify
        ).model_dump(by_alias=True)

        print(f"🔍 Payload для отправки: {payload}")

        data = await self.client._send_and_wait(
            opcode=Opcode.MSG_SEND,
            payload=payload
        )

        print(f"🔍 Ответ от сервера: {data}")

        if error := data.get("payload", {}).get("error"):
            print(f"❌ Ошибка отправки сообщения с форматированием: {error}")
            return None

        print(f"✅ Сообщение с форматированием успешно отправлено")
        return data

    async def send_file(self, chat_id, file_path, text="", markdown=False, **kwargs):
        """Отправляет файл в чат."""
        try:
            from pathlib import Path
            import aiofiles
            
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"Файл {file_path} не найден")

            async with aiofiles.open(file_path, 'rb') as f:
                file_content = await f.read()
            
            # Получаем URL для загрузки
            upload_url = await self._get_file_upload_url()
            if not upload_url:
                raise Exception("Не удалось получить URL для загрузки файла")
            
            print(f"✅ Получен URL для загрузки: {upload_url}")
            
            # Загружаем файл на сервер
            file_token = await self._upload_file_to_server(upload_url, file_content, file_path.name)
            if not file_token:
                raise Exception("Не удалось загрузить файл на сервер")
            
            print(f"✅ Файл загружен на сервер, токен: {file_token}")
            
            # Добавляем небольшую задержку для обработки файла сервером
            print(f"⏳ Ожидаем обработки файла сервером...")
            import asyncio
            await asyncio.sleep(2)  # Ждем 2 секунды
            
            # Если включен markdown, парсим текст
            if markdown:
                from pymax.markdown_parser import get_markdown_parser
                parser = get_markdown_parser()
                clean_text, elements = parser.parse(text)
                print(f"📝 Markdown парсинг для файла: '{text}' -> '{clean_text}' с {len(elements)} элементами")
                
                # Отправляем сообщение с файлом и элементами форматирования
                return await self._send_file_with_elements(
                    chat_id=chat_id,
                    text=clean_text,
                    elements=elements,
                    file_token=file_token,
                    filename=file_path.name,
                    **kwargs
                )
            else:
                # Отправляем сообщение с файлом без форматирования
                return await self._send_message_with_file(
                    chat_id=chat_id,
                    text=text,
                    file_token=file_token,
                    filename=file_path.name,
                    **kwargs
                )
            
        except Exception as e:
            print(f"❌ Ошибка отправки файла: {e}")
            import traceback
            print(f"🔍 DEBUG: Traceback: {traceback.format_exc()}")
            return None
    
    async def _send_file_with_elements(self, chat_id, text, elements, file_token, filename, **kwargs):
        """Отправляет файл с элементами форматирования."""
        try:
            from pymax.static import Opcode
            from pymax.payloads import SendMessagePayload, SendMessagePayloadMessage
            import time
            
            # Проверяем валидность chat_id
            if chat_id is None:
                print(f"❌ Некорректный chat_id в _send_file_with_elements: {chat_id}")
                return None
            
            print(f"📤 Отправляем файл с форматированием в чат {chat_id}")
            print(f"   Текст: {text}")
            print(f"   Элементы: {elements}")
            print(f"   Файл: {filename}")
            
            # Создаем вложения для файла
            if file_token.isdigit():
                # Это fileId, используем его как fileId
                attach_data = {
                    "_type": "FILE",
                    "name": filename,
                    "fileId": int(file_token)
                }
                print(f"🔍 DEBUG: Используем fileId: {file_token}")
            else:
                # Это токен
                attach_data = {
                    "_type": "FILE",
                    "name": filename,
                    "token": file_token
                }
                print(f"🔍 DEBUG: Используем токен: {file_token}")
            
            # Создаем payload для сообщения с элементами и файлом
            message_payload = SendMessagePayloadMessage(
                text=text,
                cid=int(time.time() * 1000),
                elements=elements,
                attaches=[attach_data],
                link=None
            )
            
            payload = SendMessagePayload(
                chat_id=chat_id,
                message=message_payload,
                notify=kwargs.get('notify', True)
            ).model_dump(by_alias=True)
            
            print(f"🔍 Payload для отправки файла: {payload}")
            
            data = await self.client._send_and_wait(
                opcode=Opcode.MSG_SEND,
                payload=payload
            )
            
            print(f"🔍 Ответ от сервера: {data}")
            
            if error := data.get("payload", {}).get("error"):
                print(f"❌ Ошибка отправки файла: {error}")
                return None
                
            print(f"✅ Файл успешно отправлен")
            return data
            
        except Exception as e:
            print(f"❌ Ошибка отправки файла: {e}")
            import traceback
            print(f"🔍 DEBUG: Traceback: {traceback.format_exc()}")
            return None