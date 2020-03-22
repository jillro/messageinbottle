import logging
from typing import Optional

import callbacks
import models
from senders import send_message

logger = logging.getLogger(__name__)


class BaseRequestHandler:
    def handle(self, request) -> None:
        raise NotImplementedError


class BaseMessageHandler:
    OK_RESPONSE = {"statusCode": 200}
    FORDIDDEN_RESPONSE = {"statusCode": 403}
    bottles = None
    message: models.IncomingMessage = None

    def get_message(self, event: dict) -> models.IncomingMessage:
        raise NotImplementedError

    def reply_message(
        self, text: str, markdown: bool = False, buttons: Optional[list] = None
    ) -> models.SentMessage:
        message = models.SentMessage(
            id=None, user_id=self.message.user_id, text=text, raw={}
        )

        send_message(message, markdown=markdown, buttons=buttons)

        return message

    def handle(self, event):
        self.event = event
        self.message = self.get_message(event)

        if isinstance(self.message, models.ButtonCallback) or isinstance(
            self.message, models.Command
        ):
            return callbacks.command(self)

        return callbacks.text(self)
