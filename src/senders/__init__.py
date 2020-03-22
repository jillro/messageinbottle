from typing import Optional

import models
from senders.messenger import MessengerSender
from senders.telegram import TelegramSender


def send_message(
    message: models.SentMessage, markdown: bool = False, buttons: Optional[list] = None
):
    senders = {
        models.APP_MESSENGER: MessengerSender,
        models.APP_TELEGRAM: TelegramSender,
    }
    _class = senders[message.user_id.split(" ")[0]]

    id, raw = _class().send_message(message, markdown, buttons)

    message.id = id
    message.raw = raw

    return message
