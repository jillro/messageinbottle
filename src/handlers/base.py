import logging
from datetime import datetime, timezone, timedelta

from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

import messages
import models

logger = logging.getLogger(__name__)


class BaseRequestHandler:
    def handle(self, request) -> None:
        raise NotImplementedError


class BaseMessageHandler:
    OK_RESPONSE = {"statusCode": 200}
    FORDIDDEN_RESPONSE = {"statusCode": 403}

    def get_message(self, event: dict) -> models.Message:
        raise NotImplementedError

    def reply_message(self, text: str, markdown=False, disable_web_page_preview=False):
        raise NotImplementedError

    def is_hello_message(self) -> bool:
        raise NotImplementedError

    def remove_bottle(self):
        # take a bottle from the user
        # we first try to remove a bottle from the user by checking thay have more than 1
        # of not, we check if last time a bottle was removed was more than 12 hours ago
        # else, no more bottle

        now = datetime.now(timezone.utc)

        self.bottles = 0

        try:
            self.bottles = models.users_table.update_item(
                Key={"id": self.message.user_id},
                UpdateExpression="SET bottles = bottles - :1, bottles_updated = :now",
                ExpressionAttributeValues={":1": 1, ":now": now.isoformat()},
                ReturnValues="UPDATED_NEW",
                ConditionExpression=Attr("bottles").gt(0),
            )["Attributes"]["bottles"]
        except ClientError as e:
            if not e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise e

            try:
                models.users_table.update_item(
                    Key={"id": self.message.user_id},
                    UpdateExpression="SET bottles_updated = :now",
                    ExpressionAttributeValues={":now": now.isoformat()},
                    ConditionExpression=Attr("bottles_updated").lt(
                        (now - timedelta(hours=12)).isoformat()
                    ),
                )
            except ClientError as e:
                if not e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    raise e

                return False

        return True

    def generate_status(self):
        return messages.STATUS.format(bottles=self.bottles)

    def handle(self, event):
        self.event = event
        self.message = self.get_message(event)

        if self.is_hello_message():
            models.users_table.put_item(
                Item=models.asddbdict(models.User(id=self.message.user_id))
            )
            self.bottles = 5
            return self.reply_message(messages.WELCOME, markdown=True)

        if not self.remove_bottle():
            return self.reply_message(messages.NO_MORE_BOTTLE + self.generate_status())

        # store message
        models.messages_table.put_item(Item=models.asddbdict(self.message))

        # get another one
        response = models.messages_table.query(
            KeyConditionExpression=Key("tags").eq(self.message.tags)
            & Key("datetime").lt(self.message.datetime),
            FilterExpression=Attr("sent_to").not_exists(),
            ScanIndexForward=False,
        )

        if len(response["Items"]) == 0:
            self.reply_message(messages.NO_MESSAGE_EVER + self.generate_status())

            return

        if self.message.user_id == response["Items"][0]["user_id"]:
            self.reply_message(messages.YOU_AGAIN + self.generate_status())

            return

        item = response["Items"][0]

        for item in response["Items"]:
            try:
                models.messages_table.update_item(
                    Key={"tags": item["tags"], "datetime": item["datetime"]},
                    UpdateExpression="set sent_to = :sent_to",
                    ExpressionAttributeValues={":sent_to": self.message.user_id},
                    ConditionExpression=Attr("sent_to").not_exists(),
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    continue
                raise e
            break

        text = messages.MESSAGE_INTRO.format(item["sender_display_name"]) + item["text"]
        self.reply_message(text, disable_web_page_preview=True)
