# 📚 Руководство по разработке модулей для Maxli

В этом документе описаны архитектура, внутренний протокол MAX и правила создания модулей для юзербота **Maxli** (на базе PyMax 2.3.1).

---

## 🚀 Основы создания модуля

Каждый модуль является классом, наследующим `loader.Module`:

```python
from pymax import Message
from maxli import loader, utils

@loader.tds
class MyModuleMod(loader.Module):
    """Описание модуля для .help"""

    strings = {
        "name": "MyModule",
        "hello": "👋 Привет, {name}!",
    }

    @loader.command()
    async def mycmd(self, message: Message):
        """<текст> — описание команды"""
        reply = await utils.get_reply(message)
        sender = utils.get_display_name(reply.sender if reply else message.sender)
        await utils.answer(message, self.strings["hello"].format(name=sender))
```

---

## 🎨 Форматирование в MAX

> ⚠️ **КРИТИЧЕСКОЕ ПРАВИЛО:** В MAX **НЕТ поддержки моноширинного текста через бэктики** (`` `text` `` или ```` ```code``` ````). Использование бэктиков ломает отображение!

Вместо бэктиков используйте:
1. **Жирный шрифт:** `**текст**`
2. **Курсив:** `_текст_`
3. **Цитаты MAX:** `> цитата` (или `utils.quote(text)`)
4. **Заголовки:** `utils.heading("Заголовок")`

---

## 🎙 Работа с голосовыми сообщениями (Voice)

В MAX голосовые сообщения приходят в объекте `message.attaches`:
- Класс аттача: `AudioAttachment`
- Поля: `audio_id`, `wave`, `duration`, `url`, `token`.
- Прямая ссылка `url` уже заполнена сервером. Если она пустая, получаем через:
  ```python
  res = await client.get_file_by_id(chat_id, message.id, audio_id)
  url = res.url
  ```

---

## 🎥 Работа с кружочками и видео (Video Notes & Video)

В MAX кружочки и видео устроены следующим образом:
1. **Вложение:** `VideoAttachment` (`video_id`, `token`, `video_type == 1` для кружочка).
2. **Получение видеопотока:** Сервер MAX требует опкод `Opcode.VIDEO_PLAY` с обязательной передачей `token`!
   ```python
   from pymax.protocol import Opcode

   payload = {
       "messageId": int(message.id),
       "chatId": int(chat_id),
       "videoId": int(video_id),
       "token": str(token),
   }
   resp = await client._app.invoke(Opcode.VIDEO_PLAY, payload)
   data = resp.payload if hasattr(resp, "payload") else resp

   # Извлекаем URL видео нужного разрешения:
   video_url = (
       data.get("MP4_720")
       or data.get("MP4_480")
       or data.get("MP4_360")
       or data.get("HLS")
       or data.get("url")
   )
   ```
3. **HLS Стриминг (`.m3u8`):** Если `video_url` ведет на плейлист `.m3u8`, скачиваем плейлист, парсим ссылки на `.ts` видеосегменты и объединяем их в единый байтовый поток перед отправкой в декодер/Groq Whisper.

---

## ⚠️ Редактирование медиа-сообщений в MAX

> В API MAX **запрещено редактировать сообщения, содержащие голосовые, кружочки или медиа-файлы** (`message.edit(...)` на них падает с ошибкой API).

Ответы на голосовые, видео или обработку медиа **ВСЕГДА отправляйте отдельным сообщением-ответом**:
```python
await client.send_message(chat_id, text, reply_to=message.id)
```

---

## 👥 Создание групп в MAX

Создание группы выполняется опкодом `Opcode.MSG_SEND` с `CONTROL` аттачем:
```python
from pymax.protocol import Opcode
import time

payload = {
    "message": {
        "cid": int(time.time() * 1000),
        "attaches": [
            {
                "_type": "CONTROL",
                "event": "new",
                "chatType": "CHAT",
                "title": "Название группы",
                "userIds": [], # пустой список для создания приватной группы
            }
        ],
    },
    "notify": True,
}
resp = await client._app.invoke(Opcode.MSG_SEND, payload)
data = resp.payload if hasattr(resp, "payload") else resp
chat_id = data["chat"]["id"]
```

---

## 👂 Вотчеры (Watchers)

Вотчер срабатывает на каждое входящее и исходящее сообщение:

```python
@loader.watcher()
async def my_watcher(self, message: Message):
    """Слушает сообщения"""
    chat_id = utils.get_chat_id(message) or 0
    # ваша логика обработки
```
