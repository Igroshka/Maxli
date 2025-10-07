# -*- coding: utf-8 -*-
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
            ("ANIMOJI", re.compile(r'!\[([^\]]+?)\]\(([^)]+?)\)')),
            # LINK should not match when it's part of an ANIMOJI like ![...](...)
            ("LINK", re.compile(r'(?<!!)\[([^\]]+?)\]\(([^)]+?)\)')),
            ("STRONG", re.compile(r'\*\*(.+?)\*\*')),
            ("UNDERLINE", re.compile(r'__(.+?)__')),
            ("STRIKETHROUGH", re.compile(r'~~(.+?)~~')),
            ("EMPHASIZED", re.compile(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)')),
        ]

    def parse(self, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        if not text:
            return "", []

        matches = self._collect_matches(text)
        if not matches:
            return text, []

        selected = self._select_non_overlapping(matches)
        # selected is already sorted by start in _select_non_overlapping

        clean_text = ""
        elements: List[Dict[str, Any]] = []
        pos = 0
        for m in selected:
            # Добавляем текст между последней позицией и началом матча
            clean_text += text[pos:m["start"]]
            start_clean = len(clean_text)
            
            content = m["content"]
            clean_text += content

            elem = {
                "type": m["type"],
                "from": utf16_index(clean_text, start_clean),
                "length": utf16_length(content),
                "content": content
            }

            if m["type"] == "LINK":
                elem["attributes"] = {"url": m["url"]}
            elif m["type"] == "ANIMOJI":
                attributes = {}
                url_val = m["url"]
                if url_val and url_val.isdigit():
                    attributes["entityId"] = int(url_val)
                    attributes["animojiSetId"] = str(url_val)
                elif url_val:
                    attributes["animojiLottieUrl"] = url_val
                elem["attributes"] = attributes

            elements.append(elem)
            pos = m["end"]
        
        # Добавляем остаток текста после последнего матча
        clean_text += text[pos:]
        return clean_text, elements

    def parse_to_max_format(self, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Алиас для parse() для поддержки совместимости."""
        # Возвращаем формат, пригодный для отправки в серверный API.
        clean_text, elements = self.parse(text)

        mapped = []
        for e in elements:
            me = dict(e)
            t = me.get("type")
            # ANIMOJI -> EMOJI (сервер может ожидать именно такой тип)
            if t == "ANIMOJI":
                me["type"] = "EMOJI"
            else:
                # Приводим тип к верхнему регистру, чтобы соответствовать существующим примерам
                me["type"] = str(t).upper()
            mapped.append(me)

        return clean_text, mapped
    
    def _collect_matches(self, text: str):
        matches = []
        for t, p in self.patterns:
            for m in p.finditer(text):
                start, end = m.span()
                if t in ("LINK", "ANIMOJI"):
                    content = m.group(1)
                    url = m.group(2)
                else:
                    content = m.group(1)
                    url = None
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
        # Сортируем все матчи по начальной позиции
        sorted_matches = sorted(matches, key=lambda m: m["start"])
        
        selected = []
        last_end = -1
        
        i = 0
        while i < len(sorted_matches):
            m = sorted_matches[i]
            
            # Пропускаем все матчи, которые начинаются до конца предыдущего выбранного
            if m["start"] < last_end:
                i += 1
                continue

            # Ищем пересекающиеся матчи
            overlapping = [m]
            j = i + 1
            while j < len(sorted_matches) and sorted_matches[j]["start"] < m["end"]:
                overlapping.append(sorted_matches[j])
                j += 1
            
            # Выбираем лучший из пересекающихся
            best_match = self._choose_best_match(overlapping)
            selected.append(best_match)
            
            last_end = best_match["end"]
            # Перескакиваем через все обработанные (пересекающиеся) матчи
            i = j

        return selected

    def _choose_best_match(self, overlapping: List[Dict[str, Any]]):
        # Приоритет для ANIMOJI и LINK
        for m in overlapping:
            if m["type"] in ("ANIMOJI", "LINK"):
                return m
        # Если нет приоритетных, выбираем самый длинный
        return max(overlapping, key=lambda m: m["end"] - m["start"])


_markdown_parser = None


def get_markdown_parser():
    """Returns a singleton instance of MarkdownParser."""
    global _markdown_parser
    if _markdown_parser is None:
        _markdown_parser = MarkdownParser()
    return _markdown_parser