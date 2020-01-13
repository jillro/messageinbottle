import messages
import models
from callbacks.utils import generate_status


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

    if handler.message.text == "status":
        res = models.users_table.get_item(Key={"id": handler.message.user_id})
        handler.bottles = res["Item"]["bottles"]

        return handler.reply_message(generate_status(handler))

    if handler.message.text.startswith("sendbackbottle"):
        models.users_table.update_item(
            Key={"id": handler.message.text.split("/")[1]},
            UpdateExpression="SET bottles = bottles + :1",
            ExpressionAttributeValues={":1": 1},
        )
        return handler.reply_message("The bottle has been sent back! Thanks!")

    return handler.reply_message(
        f"Unkown command\n\n`{handler.message.text}`", markdown=True
    )
