from dataclasses import asdict
from datetime import datetime, timezone

from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

import messages
import models


class BaseHandler:
    OK_RESPONSE = {"statusCode": 200}
    FORDIDDEN_RESPONSE = {"statusCode": 403}

    def extract_and_sort_hashtags(self, text, default):
        tags = sorted(set(part[1:] for part in text.split() if part.startswith("#")))

        if len(tags) == 0:
            tags = default

        return " ".join(tags)

    def get_message(self, event: dict) -> models.Message:
        raise NotImplementedError

    def reply_message(self, text: str, markdown=False, disable_web_page_preview=False):
        raise NotImplementedError

    def is_hello_message(self) -> bool:
        raise NotImplementedError

    def handle(self, event):
        self.event = event
        self.message = self.get_message(event)

        if self.is_hello_message():
            self.reply_message(messages.WELCOME, markdown=True)
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
