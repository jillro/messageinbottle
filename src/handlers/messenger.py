import hmac
import json
import logging

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
    def get_message(self) -> models.IncomingMessage:
        webhook_entry = self.event
        if "messaging" not in webhook_entry:
            raise ValueError

        messaging_entry = webhook_entry["messaging"][0]

        if "postback" in messaging_entry:
            return models.ButtonCallback(
                id=None,
                user_id=models.User.generate_id(
                    app=models.APP_MESSENGER, app_id=messaging_entry["sender"]["id"]
                ),
                sender_display_name=get_display_name(messaging_entry["sender"]["id"]),
                text=messaging_entry["postback"]["payload"],
                raw=messaging_entry,
            )

        if "message" not in messaging_entry:
            logger.error(
                "Failed to parse Messenger payload {}", json.dumps(messaging_entry)
            )
            raise ValueError

        if "text" not in messaging_entry["message"]:
            logger.error(
                "Failed to parse Messenger payload {}", json.dumps(messaging_entry)
            )
            raise ValueError

        reply_to = (
            models.Message.generate_id(
                app=models.APP_MESSENGER,
                app_id=f"{messaging_entry['message']['reply_to']['mid']}",
            )
            if "reply_to" in messaging_entry["message"]
            else None
        )

        res = None
        try:
            res = requests.post(
                "https://graph.facebook.com/v2.6/me/messages",
                params={"access_token": FB_PAGE_TOKEN},
                json={
                    "recipient": {"id": messaging_entry["sender"]["id"]},
                    "sender_action": "mark_seen",
                },
            )
            res.raise_for_status()
        except HTTPError as e:
            if res is not None:
                logger.error(res.text)
            raise e

        return models.IncomingMessage(
            id=models.IncomingMessage.generate_id(
                app=models.APP_MESSENGER, app_id=messaging_entry["message"]["mid"]
            ),
            user_id=models.User.generate_id(
                app=models.APP_MESSENGER, app_id=messaging_entry["sender"]["id"]
            ),
            sender_display_name=get_display_name(messaging_entry["sender"]["id"]),
            text=messaging_entry["message"]["text"],
            raw=messaging_entry,
            reply_to=reply_to,
        )
