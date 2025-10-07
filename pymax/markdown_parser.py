import re
from typing import List, Dict, Any, Tuple


class MarkdownElement:
    """Элемент форматирования markdown."""
    
    def __init__(self, element_type: str, from_pos: int, length: int, attributes: Dict[str, Any] = None):
        self.element_type = element_type
        self.from_pos = from_pos
        self.length = length
        self.attributes = attributes or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует элемент в словарь для API."""
        result = {
            'type': self.element_type,
            'from': self.from_pos,
            'length': self.length
        }
        if self.attributes:
            result['attributes'] = self.attributes
        return result


class MarkdownParser:
    """Парсер markdown текста в элементы форматирования Max API."""
    
    def __init__(self):
        self.patterns = {
            'STRONG': re.compile(r'\*\*(.*?)\*\*'),      # **жирный**
            'EMPHASIZED': re.compile(r'\*(.*?)\*'),       # *курсив*
            'UNDERLINE': re.compile(r'__(.*?)__'),        # __подчеркнутый__
            'STRIKETHROUGH': re.compile(r'~~(.*?)~~'),    # ~~зачеркнутый~~
            'LINK': re.compile(r'\[([^\]]+)\]\(([^)]+)\)'), # [текст](url)
        }
    
    def parse(self, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Парсит markdown текст и возвращает очищенный текст и элементы форматирования.
        
        Args:
            text (str): Исходный markdown текст
            
        Returns:
            Tuple[str, List[Dict]]: Очищенный текст и список элементов форматирования
        """
        if not text:
            return "", []
        
        elements = []
        clean_text = text
        
        # Собираем все совпадения
        all_matches = []
        
        for element_type, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                all_matches.append((element_type, match))
        
        # Сортируем по позиции начала
        all_matches.sort(key=lambda x: x[1].start())
        
        # Обрабатываем совпадения в обратном порядке, чтобы не сбивать позиции
        offset = 0
        for element_type, match in reversed(all_matches):
            start, end = match.span()
            content = match.group(1)
            
            if not content or len(content) == 0:
                continue
            
            # Вычисляем позицию в очищенном тексте
            from_pos = start - offset
            length = len(content)
            
            # Создаем элемент
            element = {
                'type': element_type,
                'from': from_pos,
                'length': length
            }
            
            # Добавляем атрибуты для ссылок
            if element_type == 'LINK':
                element['attributes'] = {'url': match.group(2)}
            
            elements.append(element)
            
            # Удаляем markdown из текста
            clean_text = clean_text[:start] + content + clean_text[end:]
            
            # Обновляем offset для следующих совпадений
            offset += (end - start) - len(content)
        
        # Сортируем элементы по позиции
        elements.sort(key=lambda x: x['from'])
        
        return clean_text, elements