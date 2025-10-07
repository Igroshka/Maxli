import re
from typing import List, Dict, Any, Tuple


def utf16_index(s: str, char_index: int) -> int:
    """
    Переводит Python-индекс (count of code points) в UTF-16 code unit индекс.
    Использует 'utf-16-le' чтобы не добавлять BOM.
    """
    if char_index <= 0:
        return 0
    # bytes length / 2 == number of UTF-16 code units
    return len(s[:char_index].encode('utf-16-le')) // 2


def utf16_length(s: str) -> int:
    return len(s.encode('utf-16-le')) // 2


class MarkdownParser:
    """Надёжный парсер markdown -> (clean_text, elements) с UTF-16 индексами."""

    def __init__(self):
        self.patterns = [
            ("LINK", re.compile(r'\[([^\]]+?)\]\(([^)]+?)\)')),
            ("STRONG", re.compile(r'\*\*(.+?)\*\*')),
            ("UNDERLINE", re.compile(r'__(.+?)__')),
            ("STRIKETHROUGH", re.compile(r'~~(.+?)~~')),
            ("EMPHASIZED", re.compile(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)')),
        ]

    def _collect_matches(self, text: str):
        matches = []
        for t, p in self.patterns:
            for m in p.finditer(text):
                start, end = m.span()
                content = m.group(1)
                url = m.group(2) if t == "LINK" else None
                matches.append({
                    "type": t,
                    "start": start,
                    "end": end,
                    "orig_len": end - start,
                    "content_len": len(content),
                    "content": content,
                    "url": url,
                })
        return matches

    def _select_non_overlapping(self, matches: List[Dict[str, Any]]):
        matches_sorted = sorted(matches, key=lambda m: (m["start"], -m["orig_len"]))
        selected = []
        occupied_until = -1
        for m in matches_sorted:
            if m["start"] >= occupied_until:
                selected.append(m)
                occupied_until = m["end"]
        return selected

    def parse(self, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        if not text:
            return "", []

        matches = self._collect_matches(text)
        if not matches:
            return text, []

        selected = self._select_non_overlapping(matches)
        selected.sort(key=lambda m: m["start"])

        clean_parts = []
        elements: List[Dict[str, Any]] = []
        last = 0
        clean_pos_chars = 0  # позиция в чистом тексте (в Python-символах)

        for m in selected:
            start, end = m["start"], m["end"]

            # кусок между последним матчем и текущим
            if last <= start:
                middle = text[last:start]
                clean_parts.append(middle)
                clean_pos_chars += len(middle)

            # видимый контент
            content = m["content"]
            clean_parts.append(content)

            # ВНИМАНИЕ: сервер ждёт UTF-16 индексы -> переводим
            from_utf16 = utf16_index("".join(clean_parts), len("".join(clean_parts)) - len(content))
            length_utf16 = utf16_length(content)

            el = {"type": m["type"], "from": from_utf16, "length": length_utf16}
            if m["url"]:
                el["attributes"] = {"url": m["url"]}
            elements.append(el)

            clean_pos_chars += len(content)
            last = end

        # остаток
        tail = text[last:]
        clean_parts.append(tail)
        clean_text = "".join(clean_parts)

        # --- дополнительная проверка (для отладки; можно убрать в проде) ---
        # убедимся, что slice по utf16-позициям соответствует содержимому
        # Для этого мапим utf16->python (обратное преобразование) – легкая проверка:
        for el, m in zip(elements, selected):
            # преобразуем utf16 'from' в python-индекс: найдем smallest i s.t. utf16_index(clean_text, i) == el['from']
            target = el["from"]
            # бинарный поиск по python-индексу
            lo, hi = 0, len(clean_text)
            while lo < hi:
                mid = (lo + hi) // 2
                if utf16_index(clean_text, mid) < target:
                    lo = mid + 1
                else:
                    hi = mid
            py_from = lo
            py_len = 0
            # длина в UTF-16 -> найдем python length, увеличивая, пока utf16 length не совпадёт
            while utf16_index(clean_text, py_from + py_len) - utf16_index(clean_text, py_from) < el["length"]:
                py_len += 1
                if py_from + py_len > len(clean_text):
                    break
            slice_txt = clean_text[py_from:py_from+py_len]
            if slice_txt != m["content"]:
                # если не совпадает — сигнал для отладки
                raise AssertionError(f"Validation failed: expected '{m['content']}', got slice '{slice_txt}' (py_from={py_from}, py_len={py_len})")

        return clean_text, elements

    def parse_to_max_format(self, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        return self.parse(text)
