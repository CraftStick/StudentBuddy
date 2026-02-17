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
        for lang_code in SUPPORTED_LANGUAGES.keys():
            locale_file = self.locales_dir / f"{lang_code}.json"
            if locale_file.exists():
                try:
                    with open(locale_file, 'r', encoding='utf-8') as f:
                        self.translations[lang_code] = json.load(f)
                    logger.info(f"Загружен язык: {lang_code}")
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
    
    def get_languages_list(self) -> Dict[str, str]:
        """
        Получить список поддерживаемых языков.
        
        Returns:
            Словарь {код: название}
        """
        return SUPPORTED_LANGUAGES.copy()


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
