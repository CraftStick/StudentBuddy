import os
from unittest import mock

import pytest
from aiogram import Dispatcher, types
from faker import Faker

from app.core.bot import TransportBot
from app.core.parse_web import WebParser
from tests.conftest import FakeTelegram
from tests.data.factories import ChatFactory, UserFactory

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        bool(os.environ.get("SELENOIDTEST", False)) is False,
        reason="Selenoid test must be run with selenoid server",
    ),
]


async def test_selenoid_text(dispatcher_fixture: Dispatcher, faker: Faker) -> None:
    data = {
        'id': '1791303673263594560',
        'from': UserFactory()._asdict(),
        'message': {
            'message_id': faker.random_int(),
            'from': {
                'id': faker.random_int(),
                'is_bot': False,
                'first_name': 'balshbot_transport',
                'username': 'balshbot_transport_bot',
            },
            'chat': ChatFactory()._asdict(),
            'date': 1661692626,
            'text': 'Остановка Б. Академическая ул, д. 15\n\nАвтобус 300 - прибывает\nАвтобус Т19 - 7 мин',
            'reply_markup': {
                'inline_keyboard': [
                    [
                        {
                            'text': 'Дом -> Офис',
                            'callback_data': 'station:home->office',
                        },
                        {
                            'text': 'Офис -> Дом',
                            'callback_data': 'station:office->home',
                        },
                    ]
                ]
            },
        },
        'chat_instance': f'-{faker.random_int()}',
        'data': 'station:home->office',
    }
    TransportBot.bot = dispatcher_fixture.bot

    with mock.patch(
        'app.core.bot.TransportBot.bot.send_message',
        return_value=data['message']['chat'],
    ):
        async with FakeTelegram(message_data=data):
            call_back = types.CallbackQuery(**data)
            result = await TransportBot.home_office(query=call_back, callback_data={})
            assert result == data['message']['chat']


async def test_selenoid_parse_yandex() -> None:
    with WebParser.get_browser_context() as page:
        text = WebParser.parse_yandex_maps(
            page=page,
            url='https://yandex.ru/maps/213/moscow/stops/stop__9640740/?ll=37.527924%2C55.823470&tab=overview&z=21',
            message='Остановка Б. Академическая ул, д. 15',
            buses=[
                '300',
                'т19',
            ],
        )
    assert len(text) > 0
