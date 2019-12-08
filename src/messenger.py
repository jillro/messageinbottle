import hmac
import json

import requests
from requests import HTTPError

from app import (
    FB_PAGE_TOKEN,
    logger,
    FB_VERIFY_TOKEN,
    FORDIDDEN_RESPONSE,
    FB_APP_SECRET,
    OK_RESPONSE,
)


def reply_messenger_message(message_event, text, **kwargs):
    res = None
    try:
        res = requests.post(
            "https://graph.facebook.com/v2.6/me/messages",
            params={"access_token": FB_PAGE_TOKEN},
            json={
                "recipient": {"id": message_event["sender"]["id"]},
                "message": {"text": text},
            },
        )
        res.raise_for_status()
    except HTTPError as e:
        if res is not None:
            logger.error(res.text)
        raise e


def messenger_handler(event):
    qs = event["queryStringParameters"]

    if qs is not None and "hub.mode" in qs and "hub.verify_token" in qs:
        if qs["hub.mode"] == "subscribe" and qs["hub.verify_token"] == FB_VERIFY_TOKEN:
            logger.info("Messenger webhook verification success")
            return {"statusCode": 200, "body": qs["hub.challenge"]}
        else:
            logger.error("Messenger webhook verification failure")
            return FORDIDDEN_RESPONSE

    expected_signature = str(event["headers"]["X-Hub-Signature"])
    signature = (
        "sha1="
        + hmac.new(
            FB_APP_SECRET.encode(), event["body"].encode("raw-unicode-escape"), "sha1"
        ).hexdigest()
    )

    if not hmac.compare_digest(expected_signature, signature):
        logger.error(
            "Messenger webhook failed to authenticate : calculated signature was {}, header signature was {}.".format(
                signature, expected_signature
            )
        )
        return FORDIDDEN_RESPONSE

    payload = json.loads(event["body"])

    for entry in payload["entry"]:
        message = entry["messaging"][0]
        if "message" not in message:
            logger.error("Webhook type not supported")
            continue
        reply_messenger_message(message, message["message"]["text"])

    return OK_RESPONSE
