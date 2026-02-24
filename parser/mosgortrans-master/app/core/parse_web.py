import re
import time
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

try:
    from zoneinfo import ZoneInfo
    MOSCOW_TZ = ZoneInfo('Europe/Moscow')
except ImportError:
    from datetime import timezone
    MOSCOW_TZ = timezone(timedelta(hours=3))  # UTC+3 Москва

from playwright.sync_api import sync_playwright

from app.core.utils import logger

if TYPE_CHECKING:
    from playwright.sync_api import Page

# Ждём появления списка маршрутов (Яндекс подгружает динамически; на сервере дольше)
PAGE_WAIT_SECONDS = 15
PAGE_LOAD_TIMEOUT_MS = 25000
SELECTOR_SNIPPET = '.masstransit-vehicle-snippet-view'
SELECTOR_MAIN_TEXT = '.masstransit-vehicle-snippet-view__main-text'
SELECTOR_TIME_TEXT = '.masstransit-prognoses-view__title-text'
# Fallback: более мягкий селектор, если классы поменялись
FALLBACK_SNIPPET = '[class*="masstransit"][class*="vehicle"][class*="snippet"]'
FALLBACK_MAIN = '[class*="masstransit"][class*="vehicle"][class*="main"]'
FALLBACK_TIME = '[class*="masstransit"][class*="prognoses"][class*="title"]'


def _format_arrival_with_time(arrival_text: str) -> str:
    """Добавляет точное время (HH:MM) к строке вида «5 min», «через 5 мин» и т.п."""
    if not arrival_text or not (s := arrival_text.strip()):
        return arrival_text
    # Уже есть время вида 12:05 — не трогаем
    if re.match(r'^\d{1,2}:\d{2}\b', s):
        return arrival_text
    # «5 min», «14 min», «через 5 мин», «7 мин», «5 минут» (EN и RU)
    match = re.search(
        r'(?:через\s+)?(\d+)\s*(?:мину?т?(?:у|ы|)?|min(?:ute)?s?)\.?\s*',
        s,
        re.IGNORECASE,
    )
    if not match:
        return arrival_text
    minutes = int(match.group(1))
    now_moscow = datetime.now(MOSCOW_TZ)
    arrival_dt = now_moscow + timedelta(minutes=minutes)
    time_str = arrival_dt.strftime('%H:%M')
    return f'{s} ({time_str})'


def _normalize_bus_name(name: str) -> str:
    """Приводим к одному виду для сравнения: латинские буквы, нижний регистр, без пробелов."""
    s = name.strip().lower()
    s = re.sub(r'\s+', '', s)
    # Кириллические е и Е → латинская e
    for cyr in ('е', 'ё', 'Е', 'Ё'):
        s = s.replace(cyr, 'e')
    # Кириллическая с → латинская c (для с820 / c820)
    s = s.replace('с', 'c')
    # Кириллическая м → латинская m (для м19 / М19 / m19)
    s = s.replace('м', 'm')
    return s


def _find_arrival(bus_arrival: dict[str, str | None], bus_name: str) -> str | None:
    """Ищем время прибытия по названию маршрута с учётом разного написания (Е24 / e24)."""
    key_norm = _normalize_bus_name(bus_name)
    for key, value in bus_arrival.items():
        if _normalize_bus_name(key) == key_norm and value:
            return value
    return None


def _collect_from_snippets(
    page: "Page",
    bus_arrival: dict[str, str | None],
    snippet_selector: str,
    main_selector: str,
    time_selector: str,
) -> None:
    """Собирает маршруты и время из элементов на странице."""
    try:
        elements = page.locator(snippet_selector).all()
    except Exception:
        return
    for el in elements:
        try:
            bus_el = el.locator(main_selector).first
            time_el = el.locator(time_selector).first
            bus_text = bus_el.inner_text(timeout=2000).strip()
            if not bus_text:
                continue
            try:
                time_text = time_el.inner_text(timeout=2000).strip() or None
            except Exception:
                time_text = None
            bus_arrival[bus_text] = time_text
        except Exception:
            continue


class WebParser:
    @staticmethod
    @contextmanager
    def get_browser_context():
        """Контекстный менеджер: запускает Chromium (Playwright), отдаёт page, по выходу закрывает браузер."""
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-gpu',
                    '--disable-images',
                    '--disable-dev-shm-usage',
                ],
            )
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()
            page.set_default_timeout(PAGE_LOAD_TIMEOUT_MS)
            try:
                yield page
            finally:
                browser.close()

    @staticmethod
    def parse_yandex_maps(
        url: str,
        message: str,
        buses: list[str],
        page: "Page | None",
    ) -> str:
        if not page:
            logger.error('Web page (Playwright) is not configured')
            return 'Что-то пошло не так. :( Веб драйвер не сконфигурирован.'

        start = time.time()
        api_calls: list[str] = []

        def log_response(response):
            u = response.url.lower()
            if any(x in u for x in ('masstransit', 'vehicle', 'transport')):
                api_calls.append(response.url)

        page.on('response', log_response)

        try:
            page.goto(url, timeout=PAGE_LOAD_TIMEOUT_MS)
        except Exception as e:
            logger.warning(f'Ошибка загрузки страницы Яндекс.Карт: {e}')
            logger.info(f'Parse time: {time.time() - start:.1f}s')
            return (
                f'Автобусов {", ".join(buses)} не найдено.\n\n'
                f'Страница не загрузилась (таймаут или сеть). Открой вручную:\n{url}\n\nСмотри на карте :)'
            )

        bus_arrival: dict[str, str | None] = defaultdict(str)

        try:
            page.wait_for_selector(SELECTOR_SNIPPET, timeout=PAGE_WAIT_SECONDS * 1000)
            time.sleep(0.4)
        except Exception:
            logger.warning('Таймаут ожидания списка маршрутов на странице (элемент не появился)')
            time.sleep(0.5)

        _collect_from_snippets(
            page, bus_arrival,
            SELECTOR_SNIPPET, SELECTOR_MAIN_TEXT, SELECTOR_TIME_TEXT,
        )
        if not bus_arrival:
            _collect_from_snippets(
                page, bus_arrival,
                FALLBACK_SNIPPET, FALLBACK_MAIN, FALLBACK_TIME,
            )

        if api_calls:
            logger.debug(f'Yandex API calls: {api_calls[:3]}...')
        if bus_arrival:
            logger.debug(f'На странице найдены маршруты: {list(bus_arrival.keys())}')

        logger.info(f'Parse time: {time.time() - start:.1f}s')

        if not any(_find_arrival(bus_arrival, bus_name) for bus_name in buses):
            hint = ''
            if bus_arrival:
                hint = f'\nНа странице отображаются: {", ".join(bus_arrival.keys())}.'
            else:
                hint = f'\n\nМаршруты на странице не отобразились — открой ссылку вручную:\n{url}'
            return f'Автобусов {", ".join(buses)} не найдено.{hint}\n\nСмотри на карте :)'

        answer = f'{message}\n\n'
        for bus_name in buses:
            arrival_time = _find_arrival(bus_arrival, bus_name)
            if arrival_time:
                arrival_display = _format_arrival_with_time(arrival_time)
                answer += f'Автобус {bus_name} - {arrival_display}\n'
        return answer
