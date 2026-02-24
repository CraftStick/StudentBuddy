import asyncio
from concurrent.futures.thread import ThreadPoolExecutor
from dataclasses import dataclass

from aiogram import Bot, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import Dispatcher
from aiogram.utils.callback_data import CallbackData

from app.core.parse_web import WebParser
from app.settings import TELEGRAM_API_TOKEN

executor = ThreadPoolExecutor(10)


@dataclass
class TransportBot:
    bot: Bot = Bot(TELEGRAM_API_TOKEN)
    dispatcher: Dispatcher = Dispatcher(bot)
    dispatcher.middleware.setup(LoggingMiddleware())
    stations_cb: CallbackData = CallbackData('station', 'direction')

    @staticmethod
    @dispatcher.message_handler(commands=['chatid'])
    async def chat_id(message: types.Message) -> types.Message:
        return await TransportBot.bot.send_message(message.chat.id, message.chat.id)

    @staticmethod
    def get_keyboard() -> types.InlineKeyboardMarkup:
        """
        Generate keyboard with list of posts
        """
        markup = types.InlineKeyboardMarkup()

        markup.row(
            types.InlineKeyboardButton(
                'К колледжу',
                callback_data=TransportBot.stations_cb.new(direction='home->office'),
            ),
            types.InlineKeyboardButton(
                'К метро',
                callback_data=TransportBot.stations_cb.new(direction='office->home'),
            ),
        )
        return markup

    @staticmethod
    @dispatcher.callback_query_handler(stations_cb.filter(direction='home->office'))
    async def home_office(
        query: types.CallbackQuery, callback_data: dict[str, str]
    ) -> types.Message:
        # К колледжу: отбытие Метро Коломенская · 3A → прибытие Электромеханический колледж
        url = 'https://yandex.ru/maps/213/moscow/stops/stop__9643158/?ll=37.663089%2C55.676860&tab=overview&z=18'
        message = 'Метро Коломенская · 3A'
        buses = ['м19', 'с820']

        text = await TransportBot.get_buses_data(url=url, message=message, buses=buses)

        return await TransportBot.bot.send_message(
            query.message.chat.id, text, reply_markup=TransportBot.get_keyboard()
        )

    @staticmethod
    @dispatcher.callback_query_handler(stations_cb.filter(direction='office->home'))
    async def office_home(
        query: types.CallbackQuery, callback_data: dict[str, str]
    ) -> types.Message:
        # К метро: отбытие Коломенский проезд, 8 → прибытие Метро Коломенская · 1A
        url = 'https://yandex.ru/maps/213/moscow/stops/stop__9645789/?ll=37.648561%2C55.665797&tab=overview&z=20'
        message = 'Коломенский проезд, 8'
        buses = ['с820']

        text = await TransportBot.get_buses_data(url=url, message=message, buses=buses)

        return await TransportBot.bot.send_message(
            query.message.chat.id, text, reply_markup=TransportBot.get_keyboard()
        )

    @staticmethod
    @dispatcher.message_handler()
    async def echo(message: types.Message) -> types.Message:
        return await TransportBot.bot.send_message(
            message.chat.id,
            'Выбери остановку',
            reply_markup=TransportBot.get_keyboard(),
        )

    @staticmethod
    async def morning_bus_mailing(
        chat_ids: list[int] | None, show_keyboard: bool = False
    ) -> None:
        if not chat_ids:
            return None

        # Утренняя рассылка — к колледжу (Метро Коломенская · 3A)
        url = 'https://yandex.ru/maps/213/moscow/stops/stop__9643158/?ll=37.663089%2C55.676860&tab=overview&z=18'
        message = 'Метро Коломенская · 3A'
        buses = ['м19', 'с820']

        text = await TransportBot.get_buses_data(url=url, message=message, buses=buses)

        kwargs = {'reply_markup': TransportBot.get_keyboard()} if show_keyboard else {}

        await asyncio.gather(
            *[
                TransportBot.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=types.ParseMode.HTML,
                    **kwargs
                )
                for chat_id in chat_ids
            ]
        )

    @staticmethod
    async def get_buses_data(url: str, message: str, buses: list[str]) -> str:
        def _fetch(url: str, message: str, buses: list[str]) -> str:
            with WebParser.get_browser_context() as page:
                return WebParser.parse_yandex_maps(url=url, message=message, buses=buses, page=page)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(executor, _fetch, url, message, buses)
