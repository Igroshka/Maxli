import re
from typing import List, Dict, Any


class MarkdownElement:
    """Класс для представления элемента форматирования."""
    
    def __init__(self, element_type: str, from_pos: int, length: int):
        self.type = element_type
        self.from_pos = from_pos
        self.length = length


class MarkdownParser:
    """Парсер markdown для форматирования текста в Max."""
    
    def __init__(self):
        # Паттерны для различных типов форматирования
        self.patterns = {
            'STRONG': re.compile(r'\*\*(.*?)\*\*'),  # **жирный**
            'EMPHASIZED': re.compile(r'\*(.*?)\*'),  # *курсив*
            'UNDERLINE': re.compile(r'__(.*?)__'),   # __подчеркнутый__
            'STRIKETHROUGH': re.compile(r'~~(.*?)~~'), # ~~зачеркнутый~~
        }
    
    def parse(self, text: str) -> tuple[str, List[MarkdownElement]]:
        """
        Парсит markdown текст и возвращает очищенный текст и элементы форматирования.
        
        Args:
            text (str): Исходный markdown текст
            
        Returns:
            tuple[str, List[MarkdownElement]]: Очищенный текст и список элементов форматирования
        """
        elements = []
        clean_text = text
        offset = 0
        
        # Обрабатываем каждый тип форматирования
        for element_type, pattern in self.patterns.items():
            matches = list(pattern.finditer(text))
            
            for match in matches:
                # Вычисляем позиции в очищенном тексте
                start_pos = match.start() - offset
                end_pos = match.end() - offset
                content_length = len(match.group(1))
                
                # Создаем элемент форматирования
                element = MarkdownElement(
                    element_type=element_type,
                    from_pos=start_pos,
                    length=content_length
                )
                elements.append(element)
                
                # Удаляем markdown разметку из текста
                clean_text = clean_text[:match.start() - offset] + match.group(1) + clean_text[match.end() - offset:]
                offset += len(match.group(0)) - len(match.group(1))
        
        # Сортируем элементы по позиции
        elements.sort(key=lambda x: x.from_pos)
        
        return clean_text, elements
    
    def parse_to_max_format(self, text: str) -> tuple[str, List[Dict[str, Any]]]:
        """
        Парсит markdown текст и возвращает в формате Max API.
        
        Args:
            text (str): Исходный markdown текст
            
        Returns:
            tuple[str, List[Dict[str, Any]]]: Очищенный текст и элементы в формате Max
        """
        clean_text, elements = self.parse(text)
        
        # Конвертируем элементы в формат Max API
        max_elements = []
        for element in elements:
            max_element = {
                "type": element.type,
                "from": element.from_pos,
                "length": element.length
            }
            max_elements.append(max_element)
        
        return clean_text, max_elements


# Глобальный экземпляр парсера
markdown_parser = MarkdownParser()