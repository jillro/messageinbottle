import json
import logging
from datetime import datetime, timezone

import requests
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from requests import HTTPError

import messages
from handlers import BaseHandler
from settings import TELEGRAM_API
from models import messages_table

logger = logging.getLogger(__name__)


class TelegramHandler(BaseHandler):
    def reply_message(self, message, text, **kwargs):
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

    def handle(self, event):
        update = json.loads(event["body"])

        if "message" not in update:
            return self.OK_RESPONSE

        message = update["message"]

        if "text" not in message:
            return self.OK_RESPONSE

        if message["text"] == "/start":
            self.reply_message(message, messages.WELCOME, parse_mode="Markdown")
            # reply_markup=json.dumps({
            #             "inline_keyboard": [[{"text": "Ok got it !", "callback_data": "/ok"}]],
            #         }))
            return self.OK_RESPONSE

        iso_datetime = datetime.now(timezone.utc).isoformat()

        tags = self.extract_and_sort_hashtags(message["text"], default=["world"])

        messages_table.put_item(
            Item={"tags": tags, "datetime": iso_datetime, "message": update["message"]}
        )

        response = messages_table.query(
            KeyConditionExpression=Key("tags").eq(tags)
            & Key("datetime").lt(iso_datetime),
            FilterExpression=Attr("sent_to").not_exists(),
            ScanIndexForward=False,
        )

        if len(response["Items"]) == 0:
            self.reply_message(message, messages.NO_MESSAGE_EVER)

            return self.OK_RESPONSE

        if message["from"]["id"] == response["Items"][0]["message"]["from"]["id"]:
            self.reply_message(message, messages.YOU_AGAIN)

            return self.OK_RESPONSE

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
        self.reply_message(message, text, disable_web_page_preview=True)

        return self.OK_RESPONSE
