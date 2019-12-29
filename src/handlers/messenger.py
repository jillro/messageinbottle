import hmac
import json
import logging
from typing import Optional

import requests
from requests import HTTPError

import models
from exceptions import ForbiddenError, EarlyResponseException
from handlers import BaseMessageHandler, BaseRequestHandler
from settings import FB_VERIFY_TOKEN, FB_APP_SECRET, FB_PAGE_TOKEN

logger = logging.getLogger(__name__)


def get_display_name(psid):
    return requests.get(
        f"https://graph.facebook.com/{psid}",
        params={"access_token": FB_PAGE_TOKEN, "fields": "first_name"},
    ).json()["first_name"]


class MessengerRequestHandler(BaseRequestHandler):
    def handle_subscribe_webhook(self):
        qs = self.request["queryStringParameters"]

        if qs is not None and "hub.mode" in qs and "hub.verify_token" in qs:
            if (
                qs["hub.mode"] == "subscribe"
                and qs["hub.verify_token"] == FB_VERIFY_TOKEN
            ):
                e = EarlyResponseException("Messenger webhook verification success")
                e.body = qs["hub.challenge"]
                raise e
            else:
                raise ForbiddenError("Messenger webhook verification failure")

    def handle_signature_checking(self):
        expected_signature = str(self.request["headers"]["X-Hub-Signature"])
        signature = (
            "sha1="
            + hmac.new(
                FB_APP_SECRET.encode(),
                self.request["body"].encode("raw-unicode-escape"),
                "sha1",
            ).hexdigest()
        )

        if not hmac.compare_digest(expected_signature, signature):
            raise ForbiddenError(
                "Messenger webhook failed to authenticate : calculated signature was {}, header signature was {}.".format(
                    signature, expected_signature
                )
            )

    def handle(self, request):
        self.request = request
        self.handle_subscribe_webhook()
        self.handle_signature_checking()

        payload = json.loads(request["body"])

        for entry in payload["entry"]:
            MessengerMessageHandler().handle(entry)


class MessengerMessageHandler(BaseMessageHandler):
    def reply_message(self, text: str, buttons: Optional[list] = None, **kwargs):
        if self.bottles is not None:
            text = text + self.generate_status()

        if buttons is not None:
            message = {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "button",
                        "text": text,
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
            message = {"text": text}

        res = None
        try:
            res = requests.post(
                "https://graph.facebook.com/v2.6/me/messages",
                params={"access_token": FB_PAGE_TOKEN},
                json={
                    "recipient": {"id": self.message.raw["sender"]["id"]},
                    "message": message,
                },
            )
            res.raise_for_status()
        except HTTPError as e:
            if res is not None:
                logger.error(res.text)
            raise e

    def get_message(self, webhook_entry: dict) -> models.Message:
        if "messaging" not in webhook_entry:
            raise ValueError

        message = webhook_entry["messaging"][0]

        if "postback" in message:
            return models.ButtonCallback(
                user_id=models.User.generate_id(
                    app=models.APP_MESSENGER, app_id=message["sender"]["id"]
                ),
                sender_display_name=get_display_name(message["sender"]["id"]),
                text=message["postback"]["payload"],
                raw=message,
            )

        if "message" not in message:
            raise ValueError

        if "text" not in message["message"]:
            raise ValueError

        return models.Message(
            user_id=models.User.generate_id(
                app=models.APP_MESSENGER, app_id=message["sender"]["id"]
            ),
            sender_display_name=get_display_name(message["sender"]["id"]),
            text=message["message"]["text"],
            raw=message,
        )
