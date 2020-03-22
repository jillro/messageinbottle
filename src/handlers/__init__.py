from exceptions import EarlyResponseException, BeforeRecordError
from .base import BaseMessageHandler, BaseRequestHandler
from .messenger import MessengerRequestHandler
from .telegram import TelegramRequestHandler


def handle(request):
    _class = None

    if request["resource"].startswith("/telegram"):
        _class = TelegramRequestHandler

    if request["resource"].startswith("/facebook-messenger"):
        _class = MessengerRequestHandler

    try:
        _class().handle(request)
    except EarlyResponseException as e:
        return {"statusCode": e.status, "body": e.body}
    except BeforeRecordError as e:
        return {"statusCode": e.status}

    return {"statusCode": 200}
