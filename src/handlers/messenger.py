import hmac
import json
import logging

import requests
from requests import HTTPError

import models
from exceptions import ForbiddenError, EarlyResponseException
from handlers import BaseHandler
from settings import FB_VERIFY_TOKEN, FB_APP_SECRET, FB_PAGE_TOKEN

logger = logging.getLogger(__name__)


def get_display_name(psid):
    return requests.get(
        f"https://graph.facebook.com/{psid}",
        params={"access_token": FB_PAGE_TOKEN, "fields": "first_name"},
    ).json()["first_name"]


class MessengerHandler(BaseHandler):
    def reply_message(self, text, **kwargs):
        res = None
        try:
            res = requests.post(
                "https://graph.facebook.com/v2.6/me/messages",
                params={"access_token": FB_PAGE_TOKEN},
                json={
                    "recipient": {"id": self.message.user.id},
                    "message": {"text": text},
                },
            )
            res.raise_for_status()
        except HTTPError as e:
            if res is not None:
                logger.error(res.text)
            raise e

    def is_hello_message(self) -> bool:
        return (
            "postback" in self.message.raw
            and self.message.raw["postback"]["payload"] == "get_started"
        )

    def get_message(self, event: dict) -> models.Message:
        payload = json.loads(event["body"])

        for entry in payload["entry"]:
            message = entry["messaging"][0]

            if "postback" in message:
                return models.Message(
                    user=models.User(
                        application=models.APP_MESSENGER, id=message["sender"]["id"]
                    ),
                    sender_display_name=get_display_name(message["sender"]["id"]),
                    text=message["postback"]["title"],
                    raw=message,
                )

            if "message" not in message:
                continue

            if "text" not in message["message"]:
                continue

            return models.Message(
                user=models.User(
                    application=models.APP_MESSENGER, id=message["sender"]["id"]
                ),
                sender_display_name=get_display_name(message["sender"]["id"]),
                text=message["message"]["text"],
                raw=message,
            )

        raise ValueError

    def handle_subscribe_webhook(self, event):
        qs = event["queryStringParameters"]

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

    def handle_signature_checking(self, event):
        expected_signature = str(event["headers"]["X-Hub-Signature"])
        signature = (
            "sha1="
            + hmac.new(
                FB_APP_SECRET.encode(),
                event["body"].encode("raw-unicode-escape"),
                "sha1",
            ).hexdigest()
        )

        if not hmac.compare_digest(expected_signature, signature):
            raise ForbiddenError(
                "Messenger webhook failed to authenticate : calculated signature was {}, header signature was {}.".format(
                    signature, expected_signature
                )
            )

    def handle(self, event):
        self.handle_subscribe_webhook(event)
        self.handle_signature_checking(event)

        return super().handle(event)
