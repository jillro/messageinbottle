import logging
from typing import Optional

import requests

import models
from requests import HTTPError
from senders.base import BaseSender
from settings import FB_PAGE_TOKEN

logger = logging.getLogger(__name__)


class MessengerSender(BaseSender):
    def send_message(
        self,
        message: models.SentMessage,
        markdown: bool = False,
        buttons: Optional[list] = None,
    ):
        recipient = str(message.user_id).replace(models.APP_MESSENGER + " ", "")
        reply_to_message_id = (
            message.reply_to.split(" ")[1]
            if isinstance(message.reply_to, str)
            else None
        )
        if buttons is not None:
            message_json = {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "button",
                        "text": message.text,
                        "buttons": [
                            {
                                "type": "postback",
                                "title": button.text,
                                "payload": button.payload,
                            }
                            for button in buttons
                        ],
                    },
                }
            }
        else:
            message_json = {"text": message.text}

        post_data = {
            "recipient": {"id": recipient},
            "message": message_json,
        }

        res = None
        try:
            res = requests.post(
                "https://graph.facebook.com/v2.6/me/messages",
                params={"access_token": FB_PAGE_TOKEN},
                json=post_data,
            )
            res.raise_for_status()
        except HTTPError as e:
            if res is not None:
                logger.error(res.text)
            raise e

        return (
            models.SentMessage.generate_id(
                app=models.APP_MESSENGER, app_id=res.json()["message_id"]
            ),
            post_data,
        )
