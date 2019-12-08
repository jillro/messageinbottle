import logging
import os

import boto3

from messenger import messenger_handler
from telegram import telegram_handler

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
