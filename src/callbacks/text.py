from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING
from urllib.parse import quote_plus

import backoff as backoff
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

import messages
import models
from callbacks import buttons
from callbacks.utils import generate_status
from interface import PostbackButton
from senders import send_message

if TYPE_CHECKING:
    from handlers import BaseMessageHandler


def remove_bottle(handler: "BaseMessageHandler"):
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
            ReturnValues="UPDATED_NEW",  # TODO remove
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


@backoff.on_predicate(
    backoff.expo,
    lambda response: "Item" not in response,
    base=2,
    factor=0.125,
    max_value=1,
    max_time=5,
)
def poll_message(tags, seq):
    return models.messages_table.get_item(
        Key={"tags": tags, "seq": seq - 1}, ConsistentRead=True
    )


def reply_handler(handler: "BaseMessageHandler", reply_to):
    try:
        item = models.replies_table.update_item(
            Key={"id": reply_to},
            UpdateExpression="SET replied_back = :1",
            ExpressionAttributeValues={":1": True},
            ConditionExpression=Attr("replied_back").not_exists(),
            ReturnValues="ALL_NEW",
        )["Attributes"]
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return handler.reply_message("You can only reply once per message.")
        raise e
    else:
        if datetime.fromisoformat(item["datetime"]) + timedelta(
            hours=23, minutes=59
        ) < datetime.now(timezone.utc):
            return handler.reply_message("You had 24 hours to reply, sorry !")

        sent_for = item["sent_for"]

        reply = send_message(
            models.SentMessage(
                id=None,
                user_id=sent_for,
                text=messages.REPLY_INTRO.format(handler.message.sender_display_name)
                + handler.message.text,
                raw={},
                reply_to=item["original_message_id"],
            ),
            buttons=[
                PostbackButton(text=f"↩️ Reply", payload=f"reply/{item['id']}",),
                PostbackButton(text=" Send new bottle", payload=f"new_bottle"),
            ],
        )

        models.replies_table.update_item(
            Key={"id": reply_to},
            UpdateExpression="SET replied_back = :1",
            ExpressionAttributeValues={":1": reply.id},
        )

        return models.replies_table.put_item(
            Item={
                "id": reply.id,
                "datetime": handler.message.datetime,
                "sent_for": handler.message.user_id,
                "original_message_id": handler.message.id,
            }
        )


def new_bottle_handler(handler: "BaseMessageHandler"):
    if not remove_bottle(handler):
        return handler.reply_message(messages.NO_MORE_BOTTLE)

    # update counter and store message
    handler.message.set_seq()
    models.messages_table.put_item(Item=models.asddbdict(handler.message))

    # if first message in channel, stop
    if handler.message.seq == 1:
        handler.reply_message(
            messages.NO_MESSAGE_EVER + generate_status(handler),
            buttons=[buttons.new_bottle],
        )
        return

    # get the previous one
    response = models.messages_table.get_item(
        Key={"tags": handler.message.tags, "seq": handler.message.seq - 1}
    )

    if "Item" not in response:
        response = poll_message(handler.message.tags, handler.message.seq)

    item = response["Item"]

    # if the previous one is from the same person, tell them
    if handler.message.user_id == item["user_id"]:
        handler.reply_message(
            messages.YOU_AGAIN + generate_status(handler), buttons=[buttons.new_bottle],
        )
        return

    text = messages.MESSAGE_INTRO.format(item["sender_display_name"]) + item["text"]
    reply = handler.reply_message(
        text + generate_status(handler),
        buttons=[
            PostbackButton(
                text="💙 Give empty bottle back",
                payload=f"sendbackbottle/{quote_plus(item['tags'])}/{item['seq']}",
            ),
            PostbackButton(
                text=f"↩️ Start a conversation",
                payload=f"reply/{quote_plus(item['tags'])}/{item['seq']}",
            ),
            buttons.new_bottle,
        ],
    )

    # update sent_to on previous item
    models.messages_table.update_item(
        Key={"tags": item["tags"], "seq": item["seq"]},
        UpdateExpression="SET sent_message_id = :sent_message_id",
        ExpressionAttributeValues={":sent_message_id": reply.id},
    )

    models.replies_table.put_item(
        Item={
            "id": reply.id,
            "datetime": reply.datetime,
            "sent_for": item["user_id"],
            "original_message_id": item["id"],
        }
    )

    if not handler.user.first_bottle:
        handler.reply_message("Other help")
        models.users_table.update_item(
            Key={"id": handler.user.id},
            UpdateExpression="SET first_bottle = :True",
            ExpressionAttributeValues={":True": True},
        )


def default_handler(handler):
    if handler.user.first_bottle:
        handler.reply_message(
            "You must reply to a previous message or write a new message.",
            buttons=[
                PostbackButton(text="🍾🌊 Write a new message", payload=f"new_bottle"),
                PostbackButton(text="⁉️ Help", payload="help"),
            ],
        )
    else:
        handler.reply_message(
            "Not so quickly! Are you ready to write your first message?",
            buttons=[
                PostbackButton(text="🍾🌊 Write my first message", payload=f"new_bottle")
            ],
        )


text = {
    "reply": reply_handler,
    "new_bottle": new_bottle_handler,
    "default": default_handler,
    "default_reply_to": lambda handler: reply_handler(
        handler, handler.message.reply_to
    ),
}
