import json
import logging
from typing import Optional

import requests
from requests import HTTPError

import models
from callbacks.command import dynamic
from settings import TELEGRAM_API

logger = logging.getLogger(__name__)


class TelegramSender:
    def send_message(
        self,
        message: models.SentMessage,
        markdown: bool = False,
        buttons: Optional[list] = None,
    ):
        chat_id = str(message.user_id).replace(models.APP_TELEGRAM + " ", "")
        reply_to_message_id = (
            message.reply_to.split(" ")[2]
            if isinstance(message.reply_to, str)
            else None
        )

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
            "chat_id": chat_id,
            "text": message.text,
            "disable_web_page_preview": True,
            "reply_to_message_id": reply_to_message_id,
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

        result = res.json()["result"]

        return (
            models.SentMessage.generate_id(
                app=models.APP_TELEGRAM,
                app_id=f"{result['chat']['id']} {result['message_id']}",
            ),
            data,
        )
