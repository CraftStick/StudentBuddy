# -*- coding: utf-8 -*-
"""Система интернационализации (i18n) для мультиязычного бота."""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Поддерживаемые языки
SUPPORTED_LANGUAGES = {
    'ru': 'Русский 🇷🇺',
    'en': 'English 🇬🇧',
    'de': 'Deutsch 🇩🇪',
    'no': 'Norsk 🇳🇴',
    'sv': 'Svenska 🇸🇪',
    'fi': 'Suomi 🇫🇮',
}

DEFAULT_LANGUAGE = 'ru'


class I18n:
    """Класс для работы с переводами."""
    
    def __init__(self, locales_dir: str = "locales"):
        """
        Инициализация системы переводов.
        
        Args:
            locales_dir: Директория с файлами переводов
        """
        self.locales_dir = Path(locales_dir)
        self.translations: Dict[str, Dict[str, Any]] = {}
        self._load_translations()
    
    def _load_translations(self):
        """Загрузка всех файлов переводов из директории."""
        # Проверяем существование директории locales
        if not self.locales_dir.exists():
            logger.error(f"Директория переводов не найдена: {self.locales_dir}")
            logger.error("Создайте директорию locales с файлами переводов (ru.json, en.json и т.д.)")
            # Создаём пустой словарь для дефолтного языка
            self.translations[DEFAULT_LANGUAGE] = {}
            return
        
        if not self.locales_dir.is_dir():
            logger.error(f"Путь {self.locales_dir} существует, но не является директорией")
            self.translations[DEFAULT_LANGUAGE] = {}
            return
        
        for lang_code in SUPPORTED_LANGUAGES.keys():
            locale_file = self.locales_dir / f"{lang_code}.json"
            if locale_file.exists():
                try:
                    with open(locale_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Валидация: проверяем, что загружен словарь
                    if not isinstance(data, dict):
                        logger.error(f"Файл {locale_file} содержит некорректные данные (ожидается объект JSON)")
                        continue
                    
                    # Базовая проверка структуры: должны быть хотя бы некоторые ключи
                    if not data:
                        logger.warning(f"Файл {locale_file} пуст")
                    
                    self.translations[lang_code] = data
                    logger.info(f"Загружен язык: {lang_code} ({len(data)} ключей верхнего уровня)")
                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка парсинга JSON в {locale_file}: {e}")
                except Exception as e:
                    logger.error(f"Ошибка загрузки языка {lang_code}: {e}")
            else:
                logger.warning(f"Файл перевода не найден: {locale_file}")
    
    def get(self, lang: str, key: str, **kwargs) -> str:
        """
        Получить перевод для указанного ключа.
        
        Args:
            lang: Код языка (ru, en, de, no, sv, fi)
            key: Ключ перевода (например: "welcome.hello", "menu.schedule")
            **kwargs: Параметры для форматирования строки
            
        Returns:
            Переведённая и отформатированная строка
        """
        # Если язык не поддерживается, используем русский
        if lang not in SUPPORTED_LANGUAGES:
            lang = DEFAULT_LANGUAGE
        
        # Получаем словарь переводов для языка
        translations = self.translations.get(lang, self.translations.get(DEFAULT_LANGUAGE, {}))
        
        # Разбираем ключ (например: "welcome.hello" -> ["welcome", "hello"])
        keys = key.split('.')
        value = translations
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                value = None
                break
        
        # Если перевод не найден, пробуем русский язык
        if value is None and lang != DEFAULT_LANGUAGE:
            logger.warning(f"Перевод не найден: {lang}.{key}, используется {DEFAULT_LANGUAGE}")
            return self.get(DEFAULT_LANGUAGE, key, **kwargs)
        
        # Если и на русском нет - возвращаем ключ
        if value is None:
            logger.error(f"Перевод не найден даже на {DEFAULT_LANGUAGE}: {key}")
            return key
        
        # Форматируем строку с параметрами
        if kwargs:
            try:
                return value.format(**kwargs)
            except KeyError as e:
                logger.error(f"Ошибка форматирования перевода {key}: {e}")
                return value
        
        return value


# Глобальный экземпляр для использования в хендлерах
i18n = I18n()


def t(lang: str, key: str, **kwargs) -> str:
    """
    Короткая функция для получения перевода.
    
    Args:
        lang: Код языка
        key: Ключ перевода
        **kwargs: Параметры для форматирования
        
    Returns:
        Переведённая строка
    """
    return i18n.get(lang, key, **kwargs)
