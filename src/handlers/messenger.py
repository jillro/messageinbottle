import hmac
import json
import logging

import requests
from requests import HTTPError

import models
from handlers import BaseHandler
from settings import FB_VERIFY_TOKEN, FB_APP_SECRET, FB_PAGE_TOKEN

logger = logging.getLogger(__name__)


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
        return False

    def get_message(self, event: dict) -> models.Message:
        payload = json.loads(event["body"])

        for entry in payload["entry"]:
            message = entry["messaging"][0]
            if "message" not in message:
                continue

            if "text" not in message["message"]:
                continue

            return models.Message(
                user=models.User(
                    application=models.APP_MESSENGER, id=message["sender"]["id"]
                ),
                sender_display_name="Unkown ?",
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
                logger.info("Messenger webhook verification success")
                return {"statusCode": 200, "body": qs["hub.challenge"]}
            else:
                logger.error("Messenger webhook verification failure")
                return self.FORDIDDEN_RESPONSE

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
            logger.error(
                "Messenger webhook failed to authenticate : calculated signature was {}, header signature was {}.".format(
                    signature, expected_signature
                )
            )
            return self.FORDIDDEN_RESPONSE

    def handle(self, event):
        res = self.handle_subscribe_webhook(event)
        if res is not None:
            return res

        res = self.handle_signature_checking(event)
        if res is not None:
            return res

        return super().handle(event)
