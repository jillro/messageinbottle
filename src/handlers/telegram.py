import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone

import requests
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from requests import HTTPError

import messages
import models
from handlers import BaseHandler
from settings import TELEGRAM_API

logger = logging.getLogger(__name__)


class TelegramHandler(BaseHandler):
    def reply_message(self, text, **kwargs):
        res = None
        try:
            res = requests.post(
                TELEGRAM_API + "sendMessage",
                data={
                    "chat_id": self.message.user.id,
                    "text": text,
                    "reply_to_message_id": self.message.raw["message_id"],
                    **kwargs,
                },
            )
            res.raise_for_status()
        except HTTPError as e:
            if res is not None:
                logger.error(res.text)
            raise e

    def get_message(self, event):
        update = json.loads(event["body"])

        if "message" not in update:
            raise ValueError

        if "text" not in update["message"]:
            return self.OK_RESPONSE

        return models.Message(
            user=models.User(
                application=models.APP_TELEGRAM, id=update["message"]["from"]["id"]
            ),
            sender_display_name=update["message"]["from"]["first_name"],
            text=update["message"]["text"],
            raw=update["message"],
        )

    def handle(self, event):
        self.event = event
        self.message = self.get_message(event)

        if self.message.text == "/start":
            self.reply_message(messages.WELCOME, parse_mode="Markdown")

            return self.OK_RESPONSE

        iso_datetime = datetime.now(timezone.utc).isoformat()

        tags = self.extract_and_sort_hashtags(self.message.text, default=["world"])

        models.messages_table.put_item(
            Item={
                "tags": tags,
                "datetime": iso_datetime,
                "message": asdict(self.message),
            }
        )

        response = models.messages_table.query(
            KeyConditionExpression=Key("tags").eq(tags)
            & Key("datetime").lt(iso_datetime),
            FilterExpression=Attr("sent_to").not_exists(),
            ScanIndexForward=False,
        )

        if len(response["Items"]) == 0:
            self.reply_message(messages.NO_MESSAGE_EVER)

            return self.OK_RESPONSE

        if self.message.user == models.User(**response["Items"][0]["message"]["user"]):
            self.reply_message(messages.YOU_AGAIN)

            return self.OK_RESPONSE

        item = response["Items"][0]

        for item in response["Items"]:
            try:
                models.messages_table.update_item(
                    Key={"tags": item["tags"], "datetime": item["datetime"]},
                    UpdateExpression="set sent_to = :sent_to",
                    ExpressionAttributeValues={":sent_to": asdict(self.message.user)},
                    ConditionExpression=Attr("sent_to").not_exists(),
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    continue
                raise e
            break

        text = (
            messages.MESSAGE_INTRO.format(item["message"]["sender_display_name"])
            + item["message"]["text"]
        )
        self.reply_message(text, disable_web_page_preview=True)

        return self.OK_RESPONSE
