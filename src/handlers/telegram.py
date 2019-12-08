import json
import logging

import requests
from requests import HTTPError

import models
from handlers import BaseHandler
from settings import TELEGRAM_API

logger = logging.getLogger(__name__)


class TelegramHandler(BaseHandler):
    def reply_message(self, text, markdown=False, **kwargs):
        if markdown:
            kwargs["parse_mode"] = "Markdown"

        res = None
        try:
            res = requests.post(
                TELEGRAM_API + "sendMessage",
                data={
                    "chat_id": self.message.user.id,
                    "text": text,
                    "reply_to_message_id": self.message.raw["message_id"],
                    **kwargs,
                },
            )
            res.raise_for_status()
        except HTTPError as e:
            if res is not None:
                logger.error(res.text)
            raise e

    def get_message(self, event: dict) -> models.Message:
        update = json.loads(event["body"])

        if "message" not in update:
            raise ValueError

        if "text" not in update["message"]:
            raise ValueError

        return models.Message(
            user=models.User(
                application=models.APP_TELEGRAM, id=update["message"]["from"]["id"]
            ),
            sender_display_name=update["message"]["from"]["first_name"],
            text=update["message"]["text"],
            raw=update["message"],
        )

    def is_hello_message(self) -> bool:
        return self.message.text == "/start"
