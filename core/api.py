import asyncio
import json
from pathlib import Path
import traceback
import aiohttp
import aiofiles
import time

# --- КОНФИГУРАЦИЯ БОТА ---
BOT_NAME = "Maxli"
BOT_VERSION = "0.3.3" # Повышаем версию
BOT_VERSION_CODE = 34
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
                for dialog in self.client.dialogs:
                    if str(message.sender) in dialog.participants:
                        self.last_known_chat_id = dialog.id
                        print(f"⚠️ Fallback: обновлен last_known_chat_id: {self.last_known_chat_id}")
                        return

    async def await_chat_id(self, message):
        """
        УЛУЧШЕННЫЙ МЕТОД ПОЛУЧЕНИЯ CHAT_ID.
        Использует кэш, поиск по отправителю и fallback механизмы.
        """
        try:
            message_id_int = int(message.id)
        except (ValueError, TypeError):
            print(f"!!! КРИТИЧЕСКАЯ ОШИБКА: ID сообщения не является числом: {message.id} !!!")
            return None

        # 1. Проверяем кэш
        if message_id_int in self.message_to_chat_cache:
            cached_chat_id = self.message_to_chat_cache[message_id_int]
            print(f"✅ Найден chat_id в кэше: {cached_chat_id}")
            
            # Дополнительная проверка: убеждаемся, что это правильный чат
            for conv in (self.client.dialogs + self.client.chats):
                if conv.id == cached_chat_id and conv.last_message and conv.last_message.id == message_id_int:
                    print(f"✅ Подтверждено: чат {cached_chat_id} содержит сообщение {message_id_int}")
                    return cached_chat_id
            
            print(f"⚠️ Кэш устарел, ищем заново...")
            # Удаляем устаревшую запись из кэша
            del self.message_to_chat_cache[message_id_int]

        # 2. Ищем по ID последнего сообщения (самый точный способ)
        print(f"🔍 Ищем чат по ID последнего сообщения {message_id_int}...")
        print(f"📊 Доступно диалогов: {len(self.client.dialogs)}, чатов: {len(self.client.chats)}")
        
        # Показываем ID последних сообщений для отладки
        print(f"🔍 Проверяем диалоги:")
        for dialog in self.client.dialogs:
            last_msg_id = dialog.last_message.id if dialog.last_message else "None"
            print(f"   Диалог {dialog.id}: последнее сообщение {last_msg_id}")
            if dialog.last_message and dialog.last_message.id == message_id_int:
                print(f"✅ Найден диалог {dialog.id} по ID последнего сообщения")
                self.message_to_chat_cache[message_id_int] = dialog.id
                return dialog.id
        
        print(f"🔍 Проверяем чаты:")
        for chat in self.client.chats:
            last_msg_id = chat.last_message.id if chat.last_message else "None"
            print(f"   Чат {chat.id}: последнее сообщение {last_msg_id}")
            if chat.last_message and chat.last_message.id == message_id_int:
                print(f"✅ Найден чат {chat.id} по ID последнего сообщения")
                self.message_to_chat_cache[message_id_int] = chat.id
                return chat.id
        
        # 2.5. Специальная проверка для "Избранного" - если сообщение от нас и chat_id = 0
        if hasattr(self, 'me') and self.me and message.sender == self.me.id and hasattr(message, 'chat_id') and message.chat_id == 0:
            print(f"✅ Сообщение из 'Избранного' (chat_id=0), используем ID = 0")
            self.message_to_chat_cache[message_id_int] = 0
            return 0

        # 3. Уведомляем о неудаче и возвращаем None
        print(f"❌ Не удалось найти чат для сообщения {message_id_int}")
        return None

        print(f"❌ Не удалось найти chat_id для сообщения {message_id_int} от {message.sender}")
        
        # 6. Специальная обработка для чата "Избранное" (Saved Messages)
        # Если это сообщение от нас самих, возможно это чат "Избранное"
        if hasattr(self, 'me') and self.me and message.sender == self.me.id:
            # Ищем диалог с самим собой (часто это ID пользователя)
            for dialog in self.client.dialogs:
                if dialog.id == self.me.id:
                    print(f"✅ Найден чат 'Избранное' с ID: {dialog.id}")
                    self.message_to_chat_cache[message_id_int] = dialog.id
                    return dialog.id
            
            # Если диалог не найден, используем ID = 0 для "Избранного"
            print(f"⚠️ Чат 'Избранное' не найден в диалогах, используем ID = 0")
            self.message_to_chat_cache[message_id_int] = 0
            return 0
        
        return None

    def clear_message_cache(self, max_size=1000):
        """Очищает кэш сообщений, если он становится слишком большим."""
        if len(self.message_to_chat_cache) > max_size:
            # Оставляем только последние 500 записей
            items = list(self.message_to_chat_cache.items())
            self.message_to_chat_cache = dict(items[-500:])
            print(f"🧹 Очищен кэш сообщений, оставлено {len(self.message_to_chat_cache)} записей")

    async def get_chat_id_for_message(self, message):
        """Получение chat_id для сообщения (fallback метод)."""
        # Если chat_id уже есть в сообщении, используем его
        if hasattr(message, 'chat_id') and message.chat_id:
            return message.chat_id
            
        # Fallback: используем медленный поиск
        print(f"⚠️ Fallback: ищем chat_id для сообщения {message.id}")
        return await self.await_chat_id(message)

    async def edit(self, message, text, markdown=False, attaches=None, **kwargs):
        """Безопасно редактирует сообщение.
        Если markdown=True — парсим в clean_text + элементы (UTF-16) и:
          1) пробуем edit_message(..., elements=elements)
          2) если не поддерживается — пробуем edit_message(text only)
          3) если edit возвращает None или падает — отправляем новое сообщение с элементами
        """
        # Получаем chat_id (как раньше)
        chat_id = getattr(message, 'chat_id', None)
        if chat_id is None:
            chat_id = await self.await_chat_id(message)
        if chat_id is None:
            await log_critical_error(Exception("await_chat_id timeout"), message, self.client)
            return

        notify = kwargs.pop("notify", False)

        try:
            msg_id = getattr(message, "id", None)
            print(f"📝 Пытаемся отредактировать сообщение {msg_id} в чате {chat_id}")

            if markdown:
                # Парсим markdown в clean_text + элементы (UTF-16 индексы)
                from pymax.markdown_parser import get_markdown_parser
                parser = get_markdown_parser()
                clean_text, elements = parser.parse(text)
                print(f"📝 Markdown парсинг (edit): '{text}' -> '{clean_text}' с {len(elements)} элементами")
                print(f"🔍 Элементы: {elements}")

                # 1) Редактирование с элементами
                try:
                    result = await self.client.edit_message(
                        chat_id=chat_id,
                        message_id=msg_id,
                        text=clean_text,
                        elements=elements,
                        **kwargs
                    )
                except TypeError as te:
                    # Клиент, вероятно, не принимает elements — попробуем без него
                    print(f"⚠️ client.edit_message не поддерживает elements (TypeError): {te}; пробуем edit без элементов")
                    try:
                        result = await self.client.edit_message(
                            chat_id=chat_id,
                            message_id=msg_id,
                            text=clean_text,
                            **kwargs
                        )
                    except Exception as e2:
                        print(f"⚠️ Редактирование (text only) тоже провалилось: {e2}")
                        result = None
                except Exception as e:
                    # Любая другая ошибка — логируем и считаем, что редактирование не удалось
                    print(f"⚠️ Ошибка при попытке edit_message с elements: {e}")
                    result = None

                # Если редактирование вернуло None => делаем fallback — отправляем новое сообщение с элементами
                if result is None:
                    print(f"⚠️ Редактирование не удалось или клиент не поддерживает elements — отправляем новое сообщение с элементами в чат {chat_id}")
                    return await self._send_message_with_elements(
                        chat_id=chat_id,
                        text=clean_text,
                        elements=elements,
                        notify=notify,
                        **kwargs
                    )

                print(f"✅ Сообщение успешно отредактировано (включая элементы при поддержке клиента)")
                return result

            else:
                # Обычное редактирование без markdown
                try:
                    result = await self.client.edit_message(chat_id=chat_id, message_id=message.id, text=text, **kwargs)
                except Exception as e:
                    print(f"⚠️ Ошибка при обычном редактировании: {e}")
                    result = None

                if result is None:
                    print(f"⚠️ Редактирование не удалось, отправляем новое обычное сообщение в чат {chat_id}")
                    return await self.client.send_message(chat_id=chat_id, text=text, notify=notify)
                print(f"✅ Сообщение успешно отредактировано")
                return result

        except Exception as e:
            # Общая обработка ошибок: логируем и пытаемся fallback-send
            print(f"❌ Ошибка при редактировании: {e}")
            import traceback
            print(f"🔍 DEBUG: Traceback: {traceback.format_exc()}")
            await log_critical_error(e, message, self.client, chat_id)

            # Fallback — если markdown, отправляем новое сообщение с элементами; иначе обычное сообщение
            if markdown:
                try:
                    from pymax.markdown_parser import get_markdown_parser
                    parser = get_markdown_parser()
                    clean_text, elements = parser.parse(text)
                    print(f"📤 Попытка отправить новое сообщение с форматированием после ошибки редактирования")
                    return await self._send_message_with_elements(
                        chat_id=chat_id,
                        text=clean_text,
                        elements=elements,
                        notify=notify,
                        **kwargs
                    )
                except Exception as e2:
                    print(f"❌ Ошибка при отправке fallback-сообщения с форматированием: {e2}")
                    print(f"🔍 DEBUG: Traceback: {traceback.format_exc()}")
                    return None
            else:
                try:
                    print(f"📤 Попытка отправить новое обычное сообщение после ошибки редактирования")
                    return await self.client.send_message(chat_id=chat_id, text=text, notify=notify)
                except Exception as e3:
                    print(f"❌ Ошибка при отправке fallback-plain сообщения: {e3}")
                    print(f"🔍 DEBUG: Traceback: {traceback.format_exc()}")
                    return None

    async def send(self, chat_id, text, markdown=False, attaches=None, **kwargs):
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
            return await self.client.send_message(text=text, chat_id=chat_id, notify=notify, **kwargs)
    
    async def _send_message_with_elements(self, chat_id, text, elements, attaches=None, notify=False, **kwargs):
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
        if attaches is None:
            attaches = []
        message_payload = SendMessagePayloadMessage(
            text=text,
            cid=int(time.time() * 1000),
            elements=elements,
            attaches=attaches,
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
                clean_text, elements = parser.parse_to_max_format(text)
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
                # Отправляем сообщение с файлом
                return await self._send_message_with_file(chat_id, text, file_token, file_path.name, **kwargs)
            
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
                print(f"❌ Ошибка отправки файла с форматированием: {error}")
                return None
                
            print(f"✅ Файл с форматированием успешно отправлен")
            return data
            
        except Exception as e:
            print(f"❌ Ошибка при отправке файла с форматированием: {e}")
            import traceback
            print(f"🔍 DEBUG: Traceback: {traceback.format_exc()}")
            return None
    
    async def send_photo(self, chat_id, file_path, text="", markdown=False, **kwargs):
        """Отправляет фотографию в чат."""
        try:
            import aiofiles
            import aiohttp
            import tempfile
            import os
            from pathlib import Path
            from pymax.files import Photo
            from pymax.static import AttachType

            is_url = isinstance(file_path, str) and (file_path.startswith('http://') or file_path.startswith('https://'))
            temp_file = None
            if is_url:
                # Скачиваем файл во временную папку
                print(f"🌐 Скачиваем изображение из URL: {file_path}")
                async with aiohttp.ClientSession() as session:
                    async with session.get(file_path) as resp:
                        if resp.status != 200:
                            raise FileNotFoundError(f"Не удалось скачать файл по URL: {file_path}")
                        suffix = os.path.splitext(file_path)[-1] or '.jpg'
                        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                            temp_file = tmp.name
                            content = await resp.read()
                            tmp.write(content)
                file_path = Path(temp_file)
            else:
                file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"Файл {file_path} не найден")

            print(f"🔍 DEBUG: Отправляем фотографию {file_path.name} в чат {chat_id}")

            # Создаем объект Photo
            photo = Photo(path=str(file_path))

            # Валидируем фотографию
            photo_data = photo.validate_photo()
            if not photo_data:
                raise ValueError(f"Файл {file_path.name} не является валидной фотографией")

            print(f"✅ Фотография валидна: {photo_data[0]} ({photo_data[1]})")

            # Загружаем фотографию через PyMax
            attach = await self.client._upload_photo(photo)
            if not attach:
                raise Exception("Не удалось загрузить фотографию на сервер")

            print(f"✅ Фотография загружена на сервер")

            # Если включен markdown, парсим текст
            if markdown:
                from pymax.markdown_parser import markdown_parser
                clean_text, elements = markdown_parser.parse_to_max_format(text)
                print(f"📝 Markdown парсинг для фото: '{text}' -> '{clean_text}' с {len(elements)} элементами")
                
                # Отправляем сообщение с фотографией и элементами форматирования
                result = await self._send_photo_with_elements(
                    chat_id=chat_id,
                    text=clean_text,
                    elements=elements,
                    photo=photo,
                    notify=kwargs.get('notify', True)
                )
            else:
                # Отправляем сообщение с фотографией
                result = await self.client.send_message(
                    chat_id=chat_id,
                    text=text,
                    photo=photo,
                    notify=kwargs.get('notify', True)
                )
            # Удаляем временный файл, если был скачан
            if temp_file:
                try:
                    os.remove(temp_file)
                except Exception as e:
                    print(f"⚠️ Не удалось удалить временный файл: {temp_file} — {e}")
            return result

        except Exception as e:
            print(f"❌ Ошибка отправки фотографии: {e}")
            import traceback
            print(f"🔍 DEBUG: Traceback: {traceback.format_exc()}")
            return None
    
    async def _get_file_upload_url(self):
        """Получает URL для загрузки файла."""
        try:
            from pymax.static import Opcode
            from pymax.payloads import UploadPhotoPayload
            
            print("🔍 DEBUG: Запрашиваем URL для загрузки файла...")
            
            # Пробуем разные opcode для загрузки файлов
            opcodes_to_try = [
                (Opcode.FILE_UPLOAD, "FILE_UPLOAD"),
                (Opcode.PHOTO_UPLOAD, "PHOTO_UPLOAD"),  # Fallback к фото
                (Opcode.VIDEO_UPLOAD, "VIDEO_UPLOAD"),  # Fallback к видео
            ]
            
            for opcode, opcode_name in opcodes_to_try:
                print(f"🔍 DEBUG: Пробуем {opcode_name} (opcode {opcode})...")
                
                try:
                    # Используем тот же payload, что и для фото
                    payload = UploadPhotoPayload().model_dump(by_alias=True)
                    data = await self.client._send_and_wait(
                        opcode=opcode,
                        payload=payload,
                        timeout=10.0
                    )
                    
                    print(f"🔍 DEBUG: Ответ от сервера ({opcode_name}): {data}")
                    
                    if error := data.get("payload", {}).get("error"):
                        print(f"❌ Ошибка получения URL загрузки ({opcode_name}): {error}")
                        continue
                        
                    # Проверяем разные варианты структуры ответа
                    payload = data.get("payload", {})
                    
                    # Вариант 1: прямой url (как для фото)
                    upload_url = payload.get("url")
                    if upload_url:
                        print(f"✅ Получен URL для загрузки (прямой, {opcode_name}): {upload_url}")
                        return upload_url
                    
                    # Вариант 2: url в info массиве
                    info = payload.get("info", [])
                    if info and len(info) > 0:
                        upload_url = info[0].get("url")
                        if upload_url:
                            print(f"✅ Получен URL для загрузки (из info, {opcode_name}): {upload_url}")
                            # Сохраняем токен из info для дальнейшего использования
                            if "token" in info[0]:
                                self._last_upload_token = info[0]["token"]
                                print(f"🔍 DEBUG: Сохранен токен из info: {self._last_upload_token}")
                            return upload_url
                    
                    # Вариант 3: files в ответе (как для фото)
                    files = payload.get("files", {})
                    if files:
                        file_data = next(iter(files.values()), None)
                        if file_data and "url" in file_data:
                            upload_url = file_data["url"]
                            print(f"✅ Получен URL для загрузки (из files, {opcode_name}): {upload_url}")
                            return upload_url
                    
                    print(f"❌ URL для загрузки не найден в ответе ({opcode_name})")
                    print(f"   Структура payload: {list(payload.keys())}")
                    if info:
                        print(f"   Структура info[0]: {list(info[0].keys()) if info[0] else 'пустой'}")
                    if files:
                        print(f"   Структура files: {list(files.keys())}")
                    
                    # Пробуем следующий opcode
                    continue
                    
                except Exception as e:
                    print(f"❌ Ошибка при попытке {opcode_name}: {e}")
                    continue
            
            print("❌ Все попытки получения URL загрузки не удались")
            return None
            
        except Exception as e:
            print(f"❌ Ошибка при получении URL загрузки: {e}")
            import traceback
            print(f"🔍 DEBUG: Traceback: {traceback.format_exc()}")
            return None
    
    async def _upload_file_to_server(self, upload_url, file_content, filename):
        """Загружает файл на сервер и возвращает токен."""
        try:
            import aiohttp
            import json
            
            print(f"🔍 DEBUG: Загружаем файл {filename} на сервер...")
            print(f"   URL: {upload_url}")
            print(f"   Размер: {len(file_content)} байт")
            
            form = aiohttp.FormData()
            form.add_field(
                name="file",
                value=file_content,
                filename=filename,
                content_type="text/plain"
            )
            
            async with aiohttp.ClientSession() as session:
                async with session.post(upload_url, data=form) as response:
                    print(f"🔍 DEBUG: Ответ сервера: HTTP {response.status}")
                    
                    if response.status == 200:
                        # Проверяем Content-Type ответа
                        content_type = response.headers.get('content-type', '').lower()
                        print(f"🔍 DEBUG: Content-Type ответа: {content_type}")
                        
                        # Пытаемся получить текст ответа
                        response_text = await response.text()
                        print(f"🔍 DEBUG: Текст ответа: {response_text[:200]}...")
                        
                        # Пытаемся декодировать как JSON только если это JSON
                        if 'application/json' in content_type or response_text.strip().startswith('{'):
                            try:
                                result = json.loads(response_text)
                                print(f"🔍 DEBUG: JSON ответ сервера: {result}")
                                
                                if "files" in result and result["files"]:
                                    file_data = next(iter(result["files"].values()))
                                    token = file_data.get("token")
                                    if token:
                                        print(f"✅ Получен токен файла: {token}")
                                        return token
                                    else:
                                        print("❌ Токен файла не найден в ответе")
                                        return None
                                else:
                                    print("❌ Файлы не найдены в ответе сервера")
                                    return None
                            except json.JSONDecodeError as json_err:
                                print(f"❌ Ошибка декодирования JSON: {json_err}")
                                print(f"   Ответ сервера: {response_text}")
                                return None
                        else:
                            # Если это не JSON, возможно это простой текст с токеном
                            print(f"🔍 DEBUG: Не JSON ответ, пытаемся извлечь токен из текста")
                            
                            # Ищем токен в тексте ответа (различные варианты)
                            if "token" in response_text.lower():
                                # Пытаемся найти токен в тексте
                                import re
                                token_match = re.search(r'"token":\s*"([^"]+)"', response_text)
                                if token_match:
                                    token = token_match.group(1)
                                    print(f"✅ Найден токен в тексте: {token}")
                                    return token
                            
                            # Если токен не найден, используем сохраненный токен или токен из URL загрузки
                            print(f"⚠️ Не удалось извлечь токен из ответа, используем сохраненный токен")
                            
                            # Сначала пробуем использовать сохраненный токен
                            if hasattr(self, '_last_upload_token') and self._last_upload_token:
                                print(f"✅ Используем сохраненный токен: {self._last_upload_token}")
                                return self._last_upload_token
                            
                            # Пытаемся извлечь токен из URL загрузки
                            import re
                            token_match = re.search(r'token=([^&]+)', upload_url)
                            if token_match:
                                token = token_match.group(1)
                                print(f"✅ Используем токен из URL: {token}")
                                return token
                            
                            # Также пробуем извлечь токен из исходного ответа сервера
                            if 'token' in response_text:
                                token_match = re.search(r'"token":\s*"([^"]+)"', response_text)
                                if token_match:
                                    token = token_match.group(1)
                                    print(f"✅ Используем токен из исходного ответа: {token}")
                                    return token
                            
                            # Fallback: используем fileId из URL
                            file_id_match = re.search(r'id=(\d+)', upload_url)
                            if file_id_match:
                                file_id = file_id_match.group(1)
                                print(f"⚠️ Fallback: используем fileId из URL: {file_id}")
                                return file_id
                            
                            print(f"❌ Не удалось получить токен или fileId")
                            return None
                    else:
                        response_text = await response.text()
                        print(f"❌ Ошибка загрузки файла: HTTP {response.status}")
                        print(f"   Ответ: {response_text}")
                        return None
                        
        except Exception as e:
            print(f"❌ Ошибка при загрузке файла: {e}")
            import traceback
            print(f"🔍 DEBUG: Traceback: {traceback.format_exc()}")
            return None
    
    async def _send_message_with_file(self, chat_id, text, file_token, filename, **kwargs):
        """Отправляет сообщение с файлом."""
        try:
            from pymax.static import Opcode
            from pymax.payloads import SendMessagePayload, SendMessagePayloadMessage
            import time
            
            print(f"🔍 DEBUG: Отправляем сообщение с файлом:")
            print(f"   Chat ID: {chat_id}")
            print(f"   Text: {text}")
            print(f"   File Token: {file_token}")
            print(f"   Filename: {filename}")
            
            # Создаем payload для сообщения с файлом
            # Проверяем, является ли file_token числом (fileId) или строкой (token)
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
            
            message_payload = SendMessagePayloadMessage(
                text=text,
                cid=int(time.time() * 1000),
                elements=[],
                attaches=[attach_data]
            )
            
            payload = SendMessagePayload(
                chat_id=chat_id,
                message=message_payload,
                notify=kwargs.get('notify', True)
            ).model_dump(by_alias=True)
            
            print(f"🔍 DEBUG: Payload для отправки: {payload}")
            
            data = await self.client._send_and_wait(
                opcode=Opcode.MSG_SEND,
                payload=payload
            )
            
            print(f"🔍 DEBUG: Ответ от сервера: {data}")
            
            if error := data.get("payload", {}).get("error"):
                print(f"❌ Ошибка отправки сообщения с файлом: {error}")
                
                # Если файл еще не готов, пробуем еще раз через некоторое время
                if error == "attachment.not.ready":
                    print(f"⏳ Файл еще не готов, ждем еще 3 секунды...")
                    import asyncio
                    await asyncio.sleep(3)
                    
                    # Пробуем отправить еще раз
                    print(f"🔄 Повторная попытка отправки...")
                    data = await self.client._send_and_wait(
                        opcode=Opcode.MSG_SEND,
                        payload=payload
                    )
                    
                    print(f"🔍 DEBUG: Ответ от сервера (повторная попытка): {data}")
                    
                    if error := data.get("payload", {}).get("error"):
                        print(f"❌ Ошибка при повторной попытке: {error}")
                        return None
                    else:
                        print(f"✅ Сообщение с файлом успешно отправлено (повторная попытка)")
                        return data
                else:
                    return None
                
            print(f"✅ Сообщение с файлом успешно отправлено")
            return data
            
        except Exception as e:
            print(f"❌ Ошибка при отправке сообщения с файлом: {e}")
            import traceback
            print(f"🔍 DEBUG: Traceback: {traceback.format_exc()}")
            return None

    async def reply(self, message, text, **kwargs):
        # Этот метод для ответа на ЧУЖИЕ сообщения, он работает правильно
        if self.last_known_chat_id:
            await self.send(self.last_known_chat_id, text, **kwargs)

    async def delete(self, message, for_me=False, **kwargs):
        # Используем chat_id из сообщения, если он есть
        chat_id = getattr(message, 'chat_id', None)
        if not chat_id:
            chat_id = await self.await_chat_id(message)
        if not chat_id:
            await log_critical_error(Exception("await_chat_id timeout"), message, self.client)
            return
        try:
            return await self.client.delete_message(chat_id=chat_id, message_ids=[message.id], for_me=for_me, **kwargs)
        except Exception as e:
            await log_critical_error(e, message, self.client, chat_id)
    
    async def get_file_url(self, file_id, token, message_id=None, chat_id=None):
        """Получает URL файла по file_id и token через WebSocket API."""
        try:
            print(f"🔍 DEBUG: Запрашиваем URL файла через WebSocket API:")
            print(f"   File ID: {file_id}")
            print(f"   Token: {token}")
            print(f"   Message ID: {message_id}")
            print(f"   Chat ID: {chat_id}")
            
            # Используем WebSocket API для получения URL файла
            from pymax.static import Opcode
            
            print("🔍 DEBUG: Отправляем запрос FILE_DOWNLOAD через WebSocket...")
            
            # Пробуем разные форматы payload для FILE_DOWNLOAD с messageId и chatId
            payloads_to_try = []
            
            if message_id and chat_id:
                payloads_to_try = [
                    {"fileId": int(file_id), "token": token, "messageId": str(message_id), "chatId": int(chat_id)},
                    {"fileId": str(file_id), "token": token, "messageId": str(message_id), "chatId": int(chat_id)},
                    {"id": int(file_id), "token": token, "messageId": str(message_id), "chatId": int(chat_id)},
                    {"id": str(file_id), "token": token, "messageId": str(message_id), "chatId": int(chat_id)},
                ]
            else:
                # Fallback без messageId и chatId
                payloads_to_try = [
                    {"fileId": int(file_id), "token": token},
                    {"fileId": str(file_id), "token": token},
                    {"id": int(file_id), "token": token},
                    {"id": str(file_id), "token": token},
                ]
            
            for i, payload in enumerate(payloads_to_try):
                print(f"🔍 DEBUG: Попытка {i+1}/{len(payloads_to_try)} - Payload: {payload}")
                
                try:
                    data = await self.client._send_and_wait(
                        opcode=Opcode.FILE_DOWNLOAD,
                        payload=payload,
                        timeout=10.0
                    )
                    
                    print(f"🔍 DEBUG: Ответ от сервера (попытка {i+1}): {data}")
                    
                    if error := data.get("payload", {}).get("error"):
                        print(f"❌ Ошибка получения URL файла (попытка {i+1}): {error}")
                        continue
                        
                    file_url = data.get("payload", {}).get("url")
                    if file_url:
                        print(f"✅ Получен URL файла (попытка {i+1}): {file_url}")
                        return file_url
                    else:
                        print(f"❌ URL файла не найден в ответе (попытка {i+1})")
                        continue
                        
                except Exception as e:
                    print(f"❌ Ошибка при попытке {i+1}: {e}")
                    continue
            
            print("❌ Все попытки получения URL через WebSocket не удались")
            
            # Fallback: генерируем URL напрямую
            print("🔍 DEBUG: Fallback - генерируем URL напрямую...")
            direct_url = f"https://files.oneme.ru/{file_id}/{token}"
            print(f"🔍 DEBUG: Сгенерированный URL: {direct_url}")
            
            # Проверим доступность URL
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    # Используем заголовки как в PyMax
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept': '*/*',
                        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
                        'Origin': 'https://web.max.ru',
                        'Referer': 'https://web.max.ru/',
                    }
                    
                    async with session.head(direct_url, headers=headers) as response:
                        if response.status == 200:
                            print(f"✅ Сгенерированный URL работает!")
                            return direct_url
                        else:
                            print(f"❌ Сгенерированный URL не работает: HTTP {response.status}")
            except Exception as e:
                print(f"❌ Ошибка при проверке URL: {e}")
            
            # Если ничего не работает, возвращаем URL (может работать для некоторых файлов)
            print("⚠️ Все проверки не удались, возвращаем URL")
            return direct_url
                
        except Exception as e:
            print(f"❌ Критическая ошибка при получении URL файла: {e}")
            import traceback
            print(f"🔍 DEBUG: Traceback: {traceback.format_exc()}")
            return None


    async def load_from_file(self, message):
        # Используем chat_id из сообщения, если он есть
        chat_id = getattr(message, 'chat_id', None)
        if not chat_id:
            chat_id = await self.await_chat_id(message)
        if not chat_id: return
        
        await self.client.edit_message(chat_id=chat_id, message_id=message.id, text="⏳ Обнаружен файл модуля...")
        attach = message.attaches[0]
        try:
            file_url = getattr(attach, 'url', None); file_name = getattr(attach, 'name', f"module.py")
            if not file_url: await self.client.edit_message(chat_id=chat_id, message_id=message.id, text="❌ Ошибка: Не удалось получить URL."); return
            if not file_name.endswith(".py"): await self.client.edit_message(chat_id=chat_id, message_id=message.id, text="❌ Ошибка: Файл должен быть .py"); return
            
            async with aiohttp.ClientSession() as session, session.get(file_url) as resp:
                if resp.status == 200:
                    from .loader import load_module
                    module_path = MODULES_DIR / file_name
                    async with aiofiles.open(module_path, mode='wb') as f: await f.write(await resp.read())
                    response = await load_module(module_path, self)
                    await self.client.edit_message(chat_id=chat_id, message_id=message.id, text=f"Вывод:\n{response}")
                else: await self.client.edit_message(chat_id=chat_id, message_id=message.id, text=f"❌ Ошибка скачивания: {resp.status}")
        except Exception as e:
            await log_critical_error(e, message, self.client, chat_id)
    
    async def get_user_name(self, user_id):
        """Получает имя пользователя по его ID."""
        try:
            if not user_id:
                return "Неизвестный пользователь"
            
            # Получаем пользователя из кеша или запрашиваем
            user = await self.client.get_user(user_id)
            if user and user.names:
                # Возвращаем первое доступное имя
                return user.names[0].name
            else:
                return f"Пользователь {user_id}"
        except Exception as e:
            print(f"❌ Ошибка получения имени пользователя {user_id}: {e}")
            return f"Пользователь {user_id}"
    
    async def get_user_info(self, user_id):
        """Получает полную информацию о пользователе по его ID."""
        try:
            if not user_id:
                return None
            
            user = await self.client.get_user(user_id)
            return user
        except Exception as e:
            print(f"❌ Ошибка получения информации о пользователе {user_id}: {e}")
            return None
    
    def get_sender_name(self, message):
        """Получает имя отправителя сообщения (синхронная версия)."""
        sender_id = getattr(message, 'sender', None)
        if not sender_id:
            return "Неизвестный пользователь"
        
        # Пытаемся получить из кеша
        user = self.client.get_cached_user(sender_id)
        if user and user.names:
            return user.names[0].name
        
        return f"Пользователь {sender_id}"

    async def set_reaction(self, message, reaction_id, reaction_type="EMOJI"):
        """Устанавливает реакцию на сообщение."""
        # Используем chat_id из сообщения, если он есть
        chat_id = getattr(message, 'chat_id', None)
        if not chat_id:
            chat_id = await self.await_chat_id(message)
        if not chat_id:
            await log_critical_error(Exception("await_chat_id timeout"), message, self.client)
            return False
        
        try:
            print(f"👍 Устанавливаем реакцию {reaction_id} на сообщение {message.id} в чате {chat_id}")
            result = await self.client.set_reaction(
                chat_id=chat_id,
                message_id=str(message.id),
                reaction_id=reaction_id,
                reaction_type=reaction_type
            )
            if result:
                print(f"✅ Реакция {reaction_id} успешно установлена")
            else:
                print(f"❌ Не удалось установить реакцию {reaction_id}")
            return result
        except Exception as e:
            print(f"❌ Ошибка при установке реакции: {e}")
            await log_critical_error(e, message, self.client, chat_id)
            return False