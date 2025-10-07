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
            ("LINK", re.compile(r'\[([^\]]+?)\]\(([^)]+?)\)')),
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
        selected.sort(key=lambda m: m["start"])

        clean_parts = []
        elements: List[Dict[str, Any]] = []
        last = 0
        
        for m in selected:
            start, end = m["start"], m["end"]

            # кусок между последним матчем и текущим
            if last <= start:
                middle = text[last:start]
                clean_parts.append(middle)

            # видимый контент
            content = m["content"]
            clean_parts.append(content)

            # Используем from и length вместо start/end как ожидает сервер
            clean_text_so_far = "".join(clean_parts)
            from_index = len(clean_text_so_far) - len(content)  # Позиция начала контента
            
            elem = {
                "type": m["type"],
                "from": utf16_index(clean_text_so_far, from_index),
                "length": utf16_length(content),
                "content": content
            }

            if m["type"] == "LINK":
                elem["attributes"] = {"url": m["url"]}

            elements.append(elem)
            last = end

        # остаток после последнего матча
        if last < len(text):
            clean_parts.append(text[last:])

        return "".join(clean_parts), elements

    def parse_to_max_format(self, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Алиас для parse() для поддержки совместимости."""
        return self.parse(text)
    
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


_markdown_parser = None


def get_markdown_parser():
    """Returns a singleton instance of MarkdownParser."""
    global _markdown_parser
    if _markdown_parser is None:
        _markdown_parser = MarkdownParser()
    return _markdown_parser