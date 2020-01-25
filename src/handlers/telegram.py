import json
import logging
from typing import Optional

import requests
from requests import HTTPError

import models
from callbacks.command import dynamic
from handlers import BaseMessageHandler, BaseRequestHandler
from settings import TELEGRAM_API

logger = logging.getLogger(__name__)


def message_model_from_telegram(telegram_object):
    if "text" not in telegram_object:
        raise ValueError

    is_command = telegram_object["text"].startswith("/")
    _class = models.Command if is_command else models.Message

    return _class(
        user_id=models.User.generate_id(
            app=models.APP_TELEGRAM, app_id=telegram_object["from"]["id"]
        ),
        sender_display_name=telegram_object["from"]["first_name"],
        text=telegram_object["text"][1:] if is_command else telegram_object["text"],
        raw=telegram_object,
    )


class TelegramRequestHandler(BaseMessageHandler, BaseRequestHandler):
    def reply_message(
        self, text: str, markdown: bool = False, buttons: Optional[list] = None
    ):
        kwargs = {}
        if markdown:
            kwargs["parse_mode"] = "Markdown"

        if buttons is not None:
            kwargs["reply_markup"] = json.dumps(
                {
                    "inline_keyboard": [
                        [
                            {
                                "text": button.text,
                                "callback_data": button.payload
                                if len(button.payload) < 65
                                else dynamic(button.payload),
                            }
                        ]
                        for button in buttons
                    ]
                }
            )

        data = {
            "chat_id": self.message.raw["from"]["id"],
            "text": text,
            "disable_web_page_preview": True,
            **kwargs,
        }

        res = None
        try:
            res = requests.post(TELEGRAM_API + "sendMessage", data=data)
            res.raise_for_status()
        except HTTPError as e:
            if res is not None:
                logger.error(res.text)
            raise e

    def get_message(self, event: dict) -> models.Message:
        update = json.loads(event["body"])

        if "callback_query" in update:
            requests.post(
                TELEGRAM_API + "answerCallbackQuery",
                data={"callback_query_id": update["callback_query"]["id"]},
            )

            return models.ButtonCallback(
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
