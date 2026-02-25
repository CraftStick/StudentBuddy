"""
Парсинг расписания с Яндекс.Карт через Playwright (Chromium).

Использует API Playwright по документации:
https://playwright.dev/python/docs/api/class-playwright
"""
import re
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

try:
    from zoneinfo import ZoneInfo
    MOSCOW_TZ = ZoneInfo('Europe/Moscow')
except ImportError:
    from datetime import timezone
    MOSCOW_TZ = timezone(timedelta(hours=3))  # UTC+3 Москва

from playwright.sync_api import (  # type: ignore[import-untyped]
    Playwright,
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

from app.core.utils import logger

if TYPE_CHECKING:
    from playwright.sync_api import Page  # type: ignore[import-untyped]

# Таймауты: Яндекс.Карты подгружают маршруты динамически
PAGE_LOAD_TIMEOUT_MS = 35000
NETWORK_IDLE_TIMEOUT_MS = 12000   # 12s — страница обычно «устаканивается» быстрее
WAIT_MASSTRANSIT_RESPONSE_MS = 20000
WAIT_AFTER_IDLE_SEC = 1.0         # короткая пауза после load, чтобы JS отрисовал панель
WAIT_TIMEOUT_MS = 55000          # ждём появления панели (часть остановок грузит дольше)

# Селекторы: появление панели маршрутов (несколько вариантов вёрстки Яндекса)
WAIT_SELECTOR = '[class*="vehicle"][class*="snippet"], [class*="route"][class*="card"]'
WAIT_SELECTORS = [
    WAIT_SELECTOR,
    '[class*="masstransit"]',
    '[class*="TransportPanel"]',
    '[class*="StopCard"]',
    '[class*="schedule"]',
    '[class*="RouteList"]',
    '[data-testid*="route"]',
    '[data-testid*="schedule"]',
]

# Сбор данных: точные классы и fallback
SELECTOR_SNIPPET = '.masstransit-vehicle-snippet-view'
SELECTOR_MAIN_TEXT = '.masstransit-vehicle-snippet-view__main-text'
SELECTOR_TIME_TEXT = '.masstransit-prognoses-view__title-text'
FALLBACK_SNIPPET = '[class*="masstransit"][class*="vehicle"][class*="snippet"]'
FALLBACK_MAIN = '[class*="masstransit"][class*="vehicle"][class*="main"]'
FALLBACK_TIME = '[class*="masstransit"][class*="prognoses"][class*="title"]'


def _format_arrival_with_time(arrival_text: str) -> str:
    """Добавляет точное время (HH:MM) к строке вида «5 min», «через 5 мин» и т.п."""
    if not arrival_text or not (s := arrival_text.strip()):
        return arrival_text
    if re.match(r'^\d{1,2}:\d{2}\b', s):
        return arrival_text
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
    return f'{s} ({arrival_dt.strftime("%H:%M")})'


def _normalize_bus_name(name: str) -> str:
    """Приводим к одному виду для сравнения: латиница, нижний регистр, без пробелов."""
    s = name.strip().lower()
    s = re.sub(r'\s+', '', s)
    for cyr in ('е', 'ё', 'Е', 'Ё'):
        s = s.replace(cyr, 'e')
    s = s.replace('с', 'c').replace('м', 'm')
    return s


def _find_arrival(bus_arrival: dict[str, str | None], bus_name: str) -> str | None:
    """Время прибытия по названию маршрута с учётом разного написания (Е24 / e24)."""
    key_norm = _normalize_bus_name(bus_name)
    for key, value in bus_arrival.items():
        if _normalize_bus_name(key) == key_norm and value:
            return value
    return None


def _wait_any_selector(page: "Page", timeout_ms: int) -> bool:
    """Ждёт появления любого из селекторов (Playwright auto-wait). Возвращает True при первом совпадении."""
    deadline = time.time() + (timeout_ms / 1000.0)
    for selector in WAIT_SELECTORS:
        remaining_ms = max(0, int((deadline - time.time()) * 1000))
        if remaining_ms <= 0:
            break
        try:
            page.locator(selector).first.wait_for(state="visible", timeout=remaining_ms)
            return True
        except PlaywrightTimeoutError:
            continue
    return False


def _wait_bus_text(page: "Page", buses: list[str], timeout_ms: int) -> bool:
    """Ждёт появления любого номера маршрута в тексте (устойчиво к смене вёрстки)."""
    if not buses:
        return False
    try:
        loc = page.get_by_text(re.escape(buses[0]), exact=False)
        for bus in buses[1:]:
            loc = loc.or_(page.get_by_text(re.escape(bus), exact=False))
        loc.first.wait_for(state="visible", timeout=timeout_ms)
        return True
    except PlaywrightTimeoutError:
        return False


def _collect_from_page_text(
    page: "Page",
    bus_arrival: dict[str, str | None],
    buses: list[str],
) -> None:
    """Fallback: парсим номера маршрутов и время из текста страницы."""
    try:
        text = page.locator("body").inner_text(timeout=12000)
    except PlaywrightTimeoutError:
        return
    time_pattern = re.compile(
        r"(?:через\s+)?(\d+)\s*(?:мину?т?(?:у|ы|)?|min(?:ute)?s?)\.?|(\d{1,2}:\d{2})",
        re.IGNORECASE,
    )
    lines = [s.strip() for s in text.replace("\r", "").split("\n")]
    for i, line_stripped in enumerate(lines):
        if not line_stripped:
            continue
        line_norm = _normalize_bus_name(line_stripped)
        for bus in buses:
            if _normalize_bus_name(bus) not in line_norm:
                continue
            match = time_pattern.search(line_stripped)
            if match:
                g1, g2 = match.group(1), match.group(2)
                time_str = (g1 and f"{g1} мин") or (g2 or "")
                if time_str:
                    bus_arrival[bus] = time_str.strip()
            elif i + 1 < len(lines):
                m = time_pattern.search(lines[i + 1])
                if m:
                    g1, g2 = m.group(1), m.group(2)
                    time_str = (g1 and f"{g1} мин") or (g2 or "")
                    if time_str:
                        bus_arrival[bus] = time_str.strip()
            break


def _collect_from_snippets(
    page: "Page",
    bus_arrival: dict[str, str | None],
    snippet_selector: str,
    main_selector: str,
    time_selector: str,
) -> None:
    """
    Собирает маршруты и время из DOM.
    Перед вызовом должен быть выполнен wait (список стабилен), иначе locator.all() даёт нестабильный результат.
    """
    try:
        snippet_locator = page.locator(snippet_selector)
        elements = snippet_locator.all()
    except PlaywrightTimeoutError:
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
            except PlaywrightTimeoutError:
                time_text = None
            bus_arrival[bus_text] = time_text
        except (PlaywrightTimeoutError, Exception):
            continue


def _launch_browser(playwright: Playwright):
    """
    Запуск Chromium по API Playwright (playwright.chromium → launch → new_context → new_page).
    https://playwright.dev/python/docs/api/class-playwright
    Возвращает (browser, context, page) для корректного закрытия (сначала context, затем browser).
    """
    chromium = playwright.chromium
    browser = chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-gpu",
            "--disable-images",
            "--disable-dev-shm-usage",
            "--single-process",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-sync",
            "--metrics-recording-only",
            "--mute-audio",
        ],
    )
    context = browser.new_context(
        ignore_https_errors=True,
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    )
    page = context.new_page()
    page.set_default_timeout(PAGE_LOAD_TIMEOUT_MS)
    return browser, context, page


class WebParser:
    """Парсер Яндекс.Карт на базе Playwright (Chromium)."""

    @staticmethod
    @contextmanager
    def get_browser_context():
        """
        Контекстный менеджер: запускает Playwright, отдаёт Page, по выходу закрывает context и browser.
        Соответствует документации: run(playwright) → chromium.launch() → new_context() → new_page();
        закрытие: context.close() затем browser.close().
        """
        with sync_playwright() as playwright:
            browser, context, page = _launch_browser(playwright)
            try:
                yield page
            finally:
                try:
                    context.close()
                except Exception:
                    pass
                try:
                    browser.close()
                except Exception:
                    pass

    @staticmethod
    def parse_yandex_maps(
        url: str,
        message: str,
        buses: list[str],
        page: "Page | None",
    ) -> str:
        if not page:
            logger.error("Web page (Playwright) is not configured")
            return "Что-то пошло не так. :( Веб драйвер не сконфигурирован."

        start = time.time()
        api_calls: list[str] = []

        def on_response(response) -> None:
            u = response.url.lower()
            if any(x in u for x in ("masstransit", "vehicle", "transport")):
                api_calls.append(response.url)

        page.on("response", on_response)

        # Загрузка страницы и ожидание ответа masstransit (SPA)
        try:
            with page.expect_response(
                lambda r: "masstransit" in r.url and "chunks" in r.url,
                timeout=WAIT_MASSTRANSIT_RESPONSE_MS,
            ) as resp_info:
                page.goto(url, timeout=PAGE_LOAD_TIMEOUT_MS)
            try:
                resp_info.value
            except Exception:
                pass
        except PlaywrightTimeoutError:
            try:
                page.wait_for_load_state("load", timeout=5000)
            except PlaywrightTimeoutError:
                pass
        except Exception as e:
            logger.warning(f"Ошибка загрузки страницы Яндекс.Карт: {e}")
            logger.info(f"Parse time: {time.time() - start:.1f}s, page_load_error")
            return (
                f'Автобусов {", ".join(buses)} не найдено.\n\n'
                f"Страница не загрузилась (таймаут или сеть). Открой вручную:\n{url}\n\nСмотри на карте :)"
            )

        try:
            page.wait_for_load_state("load", timeout=15000)
        except PlaywrightTimeoutError:
            pass
        try:
            page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            pass
        time.sleep(WAIT_AFTER_IDLE_SEC)

        bus_arrival: dict[str, str | None] = {}

        if _wait_any_selector(page, WAIT_TIMEOUT_MS):
            time.sleep(0.4)
        elif _wait_bus_text(page, buses, 35000):
            time.sleep(0.3)
        else:
            logger.warning("Таймаут ожидания списка маршрутов (элемент не появился)")
            logger.info(f"Parse timeout: snippet/route not found within {WAIT_TIMEOUT_MS // 1000}s")
            time.sleep(0.5)

        # Сбор по DOM (приоритет селекторов и fallback по тексту)
        _collect_from_snippets(
            page, bus_arrival,
            SELECTOR_SNIPPET, SELECTOR_MAIN_TEXT, SELECTOR_TIME_TEXT,
        )
        if not bus_arrival:
            _collect_from_snippets(
                page, bus_arrival,
                WAIT_SELECTOR, SELECTOR_MAIN_TEXT, SELECTOR_TIME_TEXT,
            )
        if not bus_arrival:
            _collect_from_snippets(
                page, bus_arrival,
                FALLBACK_SNIPPET, FALLBACK_MAIN, FALLBACK_TIME,
            )
        if not bus_arrival:
            _collect_from_page_text(page, bus_arrival, buses)

        if api_calls:
            logger.debug(f"Yandex API calls: {api_calls[:3]}...")
        if bus_arrival:
            logger.debug(f"На странице найдены маршруты: {list(bus_arrival.keys())}")

        elapsed = time.time() - start
        logger.info(f"Parse time: {elapsed:.1f}s, routes_found: {len(bus_arrival)}")

        if not any(_find_arrival(bus_arrival, bus_name) for bus_name in buses):
            on_page = list(bus_arrival.keys()) if bus_arrival else "пусто"
            logger.warning(f"Маршруты не найдены: url={url}, buses={buses}, на_странице={on_page}")
            hint = ""
            if bus_arrival:
                hint = f'\nНа странице отображаются: {", ".join(bus_arrival.keys())}.'
            else:
                hint = f"\n\nМаршруты на странице не отобразились — открой ссылку вручную:\n{url}"
            return f'Автобусов {", ".join(buses)} не найдено.{hint}\n\nСмотри на карте :)'

        answer = f"{message}\n\n"
        for bus_name in buses:
            arrival_time = _find_arrival(bus_arrival, bus_name)
            if arrival_time:
                answer += f"Автобус {bus_name} - {_format_arrival_with_time(arrival_time)}\n"
        return answer
