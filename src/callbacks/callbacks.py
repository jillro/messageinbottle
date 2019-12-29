from datetime import datetime, timezone, timedelta

from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

import messages
import models
from interface import PostbackButton


def command(handler):
    if handler.message.text == "help":
        return handler.reply_message(messages.BOTTLES_HELP)

    if handler.message.text == "start":
        models.users_table.put_item(
            Item=models.asddbdict(models.User(id=handler.message.user_id))
        )
        handler.bottles = 5
        return handler.reply_message(
            messages.WELCOME + generate_status(handler), markdown=True
        )

    if handler.message.text.startswith("sendbackbottle"):
        models.users_table.update_item(
            Key={"id": handler.message.text.split("/")[1]},
            UpdateExpression="SET bottles = bottles + :1",
            ExpressionAttributeValues={":1": 1},
        )
        return handler.reply_message("The bottle has been sent back! Thanks!")


def remove_bottle(handler):
    # take a bottle from the user
    # we first try to remove a bottle from the user by checking thay have more than 1
    # of not, we check if last time a bottle was removed was more than 12 hours ago
    # else, no more bottle

    now = datetime.now(timezone.utc)

    handler.bottles = 0

    try:
        handler.bottles = models.users_table.update_item(
            Key={"id": handler.message.user_id},
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
                Key={"id": handler.message.user_id},
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


def generate_status(handler):
    return messages.STATUS.format(bottles=handler.bottles)


def text(handler):
    if not remove_bottle(handler):
        return handler.reply_message(messages.NO_MORE_BOTTLE)

    # store message
    models.messages_table.put_item(Item=models.asddbdict(handler.message))

    # get another one
    response = models.messages_table.query(
        KeyConditionExpression=Key("tags").eq(handler.message.tags)
        & Key("datetime").lt(handler.message.datetime),
        FilterExpression=Attr("sent_to").not_exists(),
        ScanIndexForward=False,
    )

    if len(response["Items"]) == 0:
        handler.reply_message(messages.NO_MESSAGE_EVER + generate_status(handler))

        return

    if handler.message.user_id == response["Items"][0]["user_id"]:
        handler.reply_message(messages.YOU_AGAIN + generate_status(handler))

        return

    item = response["Items"][0]

    for item in response["Items"]:
        try:
            models.messages_table.update_item(
                Key={"tags": item["tags"], "datetime": item["datetime"]},
                UpdateExpression="set sent_to = :sent_to",
                ExpressionAttributeValues={":sent_to": handler.message.user_id},
                ConditionExpression=Attr("sent_to").not_exists(),
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                continue
            raise e
        break

    text = messages.MESSAGE_INTRO.format(item["sender_display_name"]) + item["text"]
    handler.reply_message(
        text + generate_status(handler),
        buttons=[
            PostbackButton(
                text="💙 Send back bottle", payload=f"sendbackbottle/{item['user_id']}"
            ),
            PostbackButton(text="⁉️ What does this mean?", payload="help"),
        ],
    )
