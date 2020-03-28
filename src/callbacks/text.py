from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING
from urllib.parse import quote_plus

import backoff as backoff
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

import layers
import strings
import models
from callbacks import buttons
from callbacks.utils import generate_status
from layers.interface import PostbackButton
from layers.senders import send_message

if TYPE_CHECKING:
    from layers.handlers import BaseMessageHandler


def remove_balloon(handler: "BaseMessageHandler"):
    # take a balloon from the user
    # we first try to remove a balloon from the user by checking thay have more than 1
    # of not, we check if last time a balloon was removed was more than 12 hours ago
    # else, no more balloon

    now = datetime.now(timezone.utc)

    try:
        models.users_table.update_item(
            Key={"id": handler.message.user_id},
            UpdateExpression="SET balloons = balloons - :1, balloons_updated = :now",
            ExpressionAttributeValues={":1": 1, ":now": now.isoformat()},
            ConditionExpression=Attr("balloons").gt(0),
        )
        handler.user.balloons = handler.user.balloons - 1
        handler.user.balloons_updated = now
    except ClientError as e:
        if not e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise e

        accumulation_duration = now - handler.user.balloons_updated
        new_balloons = 0
        while accumulation_duration > timedelta(hours=1):
            accumulation_duration = accumulation_duration / 2
            new_balloons = new_balloons + 1

        if new_balloons == 0:
            return False

        models.users_table.update_item(
            Key={"id": handler.message.user_id},
            UpdateExpression="SET balloons = :balloons, balloons_updated = :now",
            ExpressionAttributeValues={
                ":balloons": new_balloons - 1,
                ":now": now.isoformat(),
            },
        )
        handler.user.balloons = new_balloons - 1
        handler.user.balloons_updated = now

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
    return models.balloons_table.get_item(
        Key={"tags": tags, "seq": seq - 1}, ConsistentRead=True
    )


def reply_handler(handler: "BaseMessageHandler", reply_to):
    try:
        item = models.conversations_table.update_item(
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
            layers.messages.SentMessage(
                id=None,
                user_id=sent_for,
                text=strings.REPLY_INTRO.format(handler.message.sender_display_name)
                + handler.message.text,
                raw={},
                reply_to=item["original_message_id"],
            ),
            buttons=[
                PostbackButton(text=f"↩️ Reply", command=f"reply/{item['id']}",),
                buttons.new_balloon,
            ],
        )

        models.conversations_table.update_item(
            Key={"id": reply_to},
            UpdateExpression="SET replied_back = :1",
            ExpressionAttributeValues={":1": reply.id},
        )

        return models.conversations_table.put_item(
            Item={
                "id": reply.id,
                "datetime": handler.message.datetime,
                "sent_for": handler.message.user_id,
                "original_message_id": handler.message.id,
            }
        )


def new_balloon_handler(handler: "BaseMessageHandler"):
    if len(handler.message.text) < 50:
        handler.set_question(models.Question("new_balloon"))
        return handler.reply_message(strings.TOO_SHORT)

    if not remove_balloon(handler):
        return handler.reply_message(strings.NO_MORE_balloon)

    # update counter and store message
    handler.message.set_seq()
    models.balloons_table.put_item(Item=models.asddbdict(handler.message))

    # if first message in channel, stop
    if handler.message.seq == 1:
        handler.reply_message(
            strings.NO_MESSAGE_EVER + generate_status(handler),
            buttons=[buttons.new_balloon],
        )
        return

    # get the previous one
    response = models.balloons_table.get_item(
        Key={"tags": handler.message.tags, "seq": handler.message.seq - 1}
    )

    if "Item" not in response:
        response = poll_message(handler.message.tags, handler.message.seq)

    item = response["Item"]

    # if the previous one is from the same person, tell them
    if handler.message.user_id == item["user_id"]:
        handler.reply_message(
            strings.YOU_AGAIN + generate_status(handler), buttons=[buttons.new_balloon],
        )
        return

    text = strings.MESSAGE_INTRO.format(item["sender_display_name"]) + item["text"]
    reply = handler.reply_message(
        text + generate_status(handler),
        buttons=[
            PostbackButton(
                text="💙 Give a free balloon",
                command=f"sendbackballoon/{quote_plus(item['tags'])}/{item['seq']}",
            ),
            PostbackButton(
                text=f"↩️ Start a conversation",
                command=f"reply/{quote_plus(item['tags'])}/{item['seq']}",
            ),
            buttons.new_balloon,
        ],
    )

    # update sent_to on previous item
    models.balloons_table.update_item(
        Key={"tags": item["tags"], "seq": item["seq"]},
        UpdateExpression="SET sent_message_id = :sent_message_id",
        ExpressionAttributeValues={":sent_message_id": reply.id},
    )

    models.conversations_table.put_item(
        Item={
            "id": reply.id,
            "datetime": reply.datetime,
            "sent_for": item["user_id"],
            "original_message_id": item["id"],
        }
    )

    if not handler.user.first_balloon:
        handler.reply_message(strings.BALLOONS_HELP)
        models.users_table.update_item(
            Key={"id": handler.user.id},
            UpdateExpression="SET first_balloon = :True",
            ExpressionAttributeValues={":True": True},
        )


def default_handler(handler):
    if handler.user.first_balloon:
        handler.reply_message(
            "You must reply to a previous message or write a new message.",
            buttons=[
                PostbackButton(text="🎈☁️ Write a new message", command=f"new_balloon"),
            ],
        )
    else:
        handler.reply_message(
            "Not so quickly! Are you ready to write your first message?",
            buttons=[
                PostbackButton(
                    text="🎈☁️ Write my first message", command=f"new_balloon"
                )
            ],
        )


text = {
    "reply": reply_handler,
    "new_balloon": new_balloon_handler,
    "default": default_handler,
    "default_reply_to": lambda handler: reply_handler(
        handler, handler.message.reply_to
    ),
}
