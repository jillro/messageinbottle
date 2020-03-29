from urllib.parse import unquote_plus
from uuid import uuid4

import backoff
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

import strings
import models
from layers.interface import PostbackButton


def dynamic(command):
    id = uuid4().hex
    models.callbacks_table.put_item(Item={"id": id, "path": command})
    return f":{id}"


@backoff.on_predicate(backoff.expo, base=2, factor=0.125, max_value=1, max_time=5)
def reverse(id):
    return models.callbacks_table.get_item(Key={"id": id}).get("Item", {}).get("path")


def command(handler):
    if handler.message.text.startswith(":"):
        handler.message.text = reverse(handler.message.text[1:])

    if handler.message.text == "help":
        return handler.reply_message(strings.BALLOONS_HELP)

    if handler.message.text == "start":
        return handler.reply_message(
            strings.WELCOME,
            markdown=True,
            buttons=[
                PostbackButton(text="📝🎈☁️ Write my first message", command="letsgo")
            ],
        )

    if handler.message.text == "letsgo":
        handler.set_question(models.Question("new_balloon"))
        return handler.reply_message(
            "Ok! Enter your first message. Remember you can use hashtags."
        )

    if handler.message.text == "new_balloon":
        handler.set_question(models.Question("new_balloon"))
        return handler.reply_message(
            "Ok! Enter your new message. Remember you can use hashtags."
        )

    if (
        handler.message.text.startswith("sendfreeballoon")
        and len(handler.message.text.split("/")) == 3
    ):
        (base, tags, seq) = handler.message.text.split("/")
        tags = unquote_plus(tags)
        seq = int(seq)
        try:
            user_id = models.balloons_table.update_item(
                Key={"tags": tags, "seq": seq},
                UpdateExpression="SET balloon_back = :1",
                ExpressionAttributeValues={":1": True},
                ConditionExpression=Attr("balloon_back").not_exists(),
                ReturnValues="ALL_NEW",
            )["Attributes"]["user_id"]
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return handler.reply_message("You have already gave a free balloon.")
            raise e
        else:
            models.users_table.update_item(
                Key={"id": user_id},
                UpdateExpression="SET balloons = balloons + :1",
                ExpressionAttributeValues={":1": 1},
            )

            return handler.reply_message("The balloon has been sent back! Thanks!")

    if handler.message.text.startswith("reply") and (
        len(handler.message.text.split("/")) in [2, 3]
    ):
        if len(handler.message.text.split("/")) == 3:
            (base, tags, seq) = handler.message.text.split("/")
            tags = unquote_plus(tags)
            seq = int(seq)
            sent_message_id = models.balloons_table.get_item(
                Key={"tags": tags, "seq": seq}
            )["Item"]["sent_message_id"]
        else:
            (base, reply_id) = handler.message.text.split("/")
            sent_message_id = models.conversations_table.get_item(Key={"id": reply_id})[
                "Item"
            ]["replied_back"]

        handler.set_question(models.Question("reply", {"reply_to": sent_message_id}))
        return handler.reply_message("Type your reply :")

    return handler.reply_message(
        f"Unkown command\n\n`{handler.message.text}`", markdown=True
    )
