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

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_API = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/"


dynamodb = boto3.resource("dynamodb", region_name="eu-west-3")
messages_table = dynamodb.Table("messageinabottle_messages")

OK_RESPONSE = {"statusCode": 200}


def extract_and_sort_hashtags(text, default):
    tags = sorted(set(part[1:] for part in text.split() if part.startswith("#")))

    if len(tags) == 0:
        tags = default

    return " ".join(tags)


def reply_message(message, text, **kwargs):
    res = None
    try:
        res = requests.post(
            TELEGRAM_API + "sendMessage",
            data={"chat_id": message["chat"]["id"], "text": text, **kwargs},
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

    update = json.loads(event["body"])

    if "message" not in update:
        return OK_RESPONSE

    message = update["message"]

    if "text" not in message:
        return OK_RESPONSE

    if message["text"] == "/start":
        reply_message(message, messages.WELCOME, parse_mode="Markdown")
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
        reply_message(message, messages.NO_MESSAGE_EVER)

        return OK_RESPONSE

    if message["from"]["id"] == response["Items"][0]["message"]["from"]["id"]:
        reply_message(message, messages.YOU_AGAIN)

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
    reply_message(message, text, disable_web_page_preview=True)

    return OK_RESPONSE
