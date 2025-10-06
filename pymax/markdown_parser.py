import re
from typing import List, Dict, Any


class MarkdownElement:
    """Класс для представления элемента форматирования."""
    
    def __init__(self, element_type: str, from_pos: int, length: int, attributes: Dict[str, Any] = None):
        self.type = element_type
        self.from_pos = from_pos
        self.length = length
        self.attributes = attributes or {}


class MarkdownParser:
    """Парсер markdown для форматирования текста в Max."""
    
    def __init__(self):
        # Паттерны для различных типов форматирования
        self.patterns = {
            'STRONG': re.compile(r'\*\*(.*?)\*\*'),  # **жирный**
            'EMPHASIZED': re.compile(r'\*(.*?)\*'),  # *курсив*
            'UNDERLINE': re.compile(r'__(.*?)__'),   # __подчеркнутый__
            'STRIKETHROUGH': re.compile(r'~~(.*?)~~'), # ~~зачеркнутый~~
            'LINK': re.compile(r'\[([^\]]+)\]\(([^)]+)\)'), # [текст](url)
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
        
        # Собираем все совпадения со всех паттернов в исходном тексте
        all_matches = []
        
        # Сначала ссылки
        for match in self.patterns['LINK'].finditer(text):
            all_matches.append(('LINK', match))
        
        # Затем остальные элементы форматирования
        for element_type, pattern in self.patterns.items():
            if element_type != 'LINK':
                for match in pattern.finditer(text):
                    all_matches.append((element_type, match))
        
        # Сортируем по позиции начала (сначала обрабатываем те, что раньше в тексте)
        all_matches.sort(key=lambda x: x[1].start())
        
        # Обрабатываем совпадения в порядке их появления в тексте
        offset = 0
        for element_type, match in all_matches:
            # Вычисляем позицию в очищенном тексте
            start_pos = match.start() - offset
            content_length = len(match.group(1))
            
            # Пропускаем элементы с нулевой длиной
            if content_length == 0:
                continue
            
            if element_type == 'LINK':
                # Для ссылок используем текст ссылки как содержимое
                link_text = match.group(1)
                link_url = match.group(2)
                
                # Создаем элемент ссылки с атрибутами
                element = MarkdownElement(
                    element_type=element_type,
                    from_pos=start_pos,
                    length=content_length,
                    attributes={'url': link_url}
                )
                elements.append(element)
                
                # Заменяем markdown ссылку на текст ссылки
                clean_text = clean_text[:match.start() - offset] + link_text + clean_text[match.end() - offset:]
                offset += len(match.group(0)) - len(link_text)
            else:
                # Для остальных элементов форматирования
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
            
            # Добавляем атрибуты, если они есть (например, для ссылок)
            if element.attributes:
                max_element["attributes"] = element.attributes
            
            max_elements.append(max_element)
        
        return clean_text, max_elements


# Глобальный экземпляр парсера
markdown_parser = MarkdownParser()