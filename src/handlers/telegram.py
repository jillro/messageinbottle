import json
import logging
from typing import Optional

import requests

import models
from handlers import BaseMessageHandler, BaseRequestHandler
from settings import TELEGRAM_API

logger = logging.getLogger(__name__)


def message_model_from_telegram(telegram_object):
    if "text" not in telegram_object:
        raise ValueError

    is_command = telegram_object["text"].startswith("/")
    _class = models.Command if is_command else models.IncomingMessage

    reply_to = (
        models.Message.generate_id(
            app=models.APP_TELEGRAM,
            app_id=f"{telegram_object['reply_to_message']['chat']['id']} {telegram_object['reply_to_message']['message_id']}",
        )
        if "reply_to_message" in telegram_object
        else None
    )

    return _class(
        id=models.Message.generate_id(
            app=models.APP_TELEGRAM,
            app_id=f"{telegram_object['chat']['id']} {telegram_object['message_id']}",
        ),
        user_id=models.User.generate_id(
            app=models.APP_TELEGRAM, app_id=telegram_object["from"]["id"]
        ),
        sender_display_name=telegram_object["from"]["first_name"],
        text=telegram_object["text"][1:] if is_command else telegram_object["text"],
        raw=telegram_object,
        reply_to=reply_to,
    )


class TelegramRequestHandler(BaseMessageHandler, BaseRequestHandler):
    def get_message(self) -> models.IncomingMessage:
        update = json.loads(self.event["body"])

        if "callback_query" in update:
            requests.post(
                TELEGRAM_API + "answerCallbackQuery",
                data={"callback_query_id": update["callback_query"]["id"]},
            )

            return models.ButtonCallback(
                id=None,
                user_id=models.User.generate_id(
                    app=models.APP_TELEGRAM,
                    app_id=update["callback_query"]["from"]["id"],
                ),
                sender_display_name=update["callback_query"]["from"]["first_name"],
                text=update["callback_query"]["data"],
                raw=update["callback_query"],
                original_message=message_model_from_telegram(
                    update["callback_query"]["message"]
                )
                if "message" in update["callback_query"]
                else None,
            )

        if "message" not in update:
            raise ValueError

        return message_model_from_telegram(update["message"])
