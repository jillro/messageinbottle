from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING
from urllib.parse import quote_plus

import backoff as backoff
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

import messages
import models
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


def text(handler: "BaseMessageHandler"):
    if handler.message.reply_to is not None:
        try:
            item = models.replies_table.update_item(
                Key={"id": handler.message.reply_to},
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
            sent_for = item["sent_for"]

            reply = send_message(
                models.SentMessage(
                    id=None,
                    user_id=sent_for,
                    text=messages.REPLY_INTRO.format(
                        handler.message.sender_display_name
                    )
                    + handler.message.text,
                    raw={},
                    reply_to=item["original_message_id"],
                )
            )

            return models.replies_table.put_item(
                Item={
                    "id": reply.id,
                    "sent_for": handler.message.user_id,
                    "original_message_id": handler.message.id,
                }
            )

    if not remove_bottle(handler):
        return handler.reply_message(messages.NO_MORE_BOTTLE)

    # update counter and store message
    handler.message.set_seq()
    models.messages_table.put_item(Item=models.asddbdict(handler.message))

    # if first message in channel, stop
    if handler.message.seq == 1:
        handler.reply_message(messages.NO_MESSAGE_EVER + generate_status(handler))
        return

    # get the previous one
    response = models.messages_table.get_item(
        Key={"tags": handler.message.tags, "seq": handler.message.seq - 1}
    )

    if "Item" not in response:
        response = poll_message(handler.message.tags, handler.message.seq)

    # if the previous one is from the same person, tell them
    if handler.message.user_id == response["Item"]["user_id"]:
        handler.reply_message(messages.YOU_AGAIN + generate_status(handler))
        return

    # update sent_to on previous item
    item = response["Item"]
    models.messages_table.update_item(
        Key={"tags": item["tags"], "seq": item["seq"]},
        UpdateExpression="SET sent_to = :sent_to",
        ExpressionAttributeValues={":sent_to": handler.message.user_id},
    )

    text = messages.MESSAGE_INTRO.format(item["sender_display_name"]) + item["text"]
    reply = handler.reply_message(
        text + generate_status(handler),
        buttons=[
            PostbackButton(text="⁉️ Help", payload="help"),
            PostbackButton(
                text="💙 Send back bottle",
                payload=f"sendbackbottle/{quote_plus(item['tags'])}/{item['seq']}",
            ),
            PostbackButton(text="🍾 How much bottle do I have ?", payload="status"),
        ],
    )

    models.replies_table.put_item(
        Item={
            "id": reply.id,
            "sent_for": item["user_id"],
            "original_message_id": item["id"],
        }
    )
