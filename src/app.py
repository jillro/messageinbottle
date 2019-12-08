import hmac
import json
import logging
import os
from datetime import datetime, timezone

import boto3
import requests
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from requests import HTTPError

import messages

logger = logging.getLogger(__name__)

FB_VERIFY_TOKEN = os.environ.get("FB_VERIFY_TOKEN")
FB_APP_ID = os.environ.get("FB_APP_ID")
FB_APP_SECRET = os.environ.get("FB_APP_SECRET")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_API = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/"

dynamodb = boto3.resource("dynamodb", region_name="eu-west-3")
messages_table = dynamodb.Table("messageinabottle_messages")

OK_RESPONSE = {"statusCode": 200}
FORDIDDEN_RESPONSE = {"statusCode": 403}


def extract_and_sort_hashtags(text, default):
    tags = sorted(set(part[1:] for part in text.split() if part.startswith("#")))

    if len(tags) == 0:
        tags = default

    return " ".join(tags)


def reply_telegram_message(message, text, **kwargs):
    res = None
    try:
        res = requests.post(
            TELEGRAM_API + "sendMessage",
            data={
                "chat_id": message["chat"]["id"],
                "text": text,
                "reply_to_message_id": message["message_id"],
                **kwargs,
            },
        )
        res.raise_for_status()
    except HTTPError as e:
        if res is not None:
            logger.error(res.text)
        raise e


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


def lambda_handler(event, context):
    """AWS Lambda function

    :param event: API Gateway Lambda Proxy Input Format
    :param context: Lambda Context runtime methods and attributes
    :type event: dict
    :type context: object
    :return :API Gateway Lambda Proxy Output Format
    :rtype: dict

    Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format
    Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html
    Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
    """
    if event["resource"].startswith("/telegram"):
        return telegram_handler(event)

    if event["resource"].startswith("/facebook-messenger"):
        return messenger_handler(event)


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


def telegram_handler(event):
    update = json.loads(event["body"])

    if "message" not in update:
        return OK_RESPONSE

    message = update["message"]

    if "text" not in message:
        return OK_RESPONSE

    if message["text"] == "/start":
        reply_telegram_message(message, messages.WELCOME, parse_mode="Markdown")
        # reply_markup=json.dumps({
        #             "inline_keyboard": [[{"text": "Ok got it !", "callback_data": "/ok"}]],
        #         }))
        return OK_RESPONSE

    iso_datetime = datetime.now(timezone.utc).isoformat()

    tags = extract_and_sort_hashtags(message["text"], default=["world"])

    messages_table.put_item(
        Item={"tags": tags, "datetime": iso_datetime, "message": update["message"]}
    )

    response = messages_table.query(
        KeyConditionExpression=Key("tags").eq(tags) & Key("datetime").lt(iso_datetime),
        FilterExpression=Attr("sent_to").not_exists(),
        ScanIndexForward=False,
    )

    if len(response["Items"]) == 0:
        reply_telegram_message(message, messages.NO_MESSAGE_EVER)

        return OK_RESPONSE

    if message["from"]["id"] == response["Items"][0]["message"]["from"]["id"]:
        reply_telegram_message(message, messages.YOU_AGAIN)

        return OK_RESPONSE

    item = response["Items"][0]

    for item in response["Items"]:
        try:
            messages_table.update_item(
                Key={"tags": item["tags"], "datetime": item["datetime"]},
                UpdateExpression="set sent_to = :sent_to",
                ExpressionAttributeValues={":sent_to": message["from"]["id"]},
                ConditionExpression=Attr("sent_to").not_exists(),
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                continue
            raise e
        break

    text = (
        messages.MESSAGE_INTRO.format(item["message"]["from"]["first_name"])
        + item["message"]["text"]
    )
    reply_telegram_message(message, text, disable_web_page_preview=True)

    return OK_RESPONSE
