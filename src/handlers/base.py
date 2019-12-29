import logging
from typing import Optional

import callbacks
import models

logger = logging.getLogger(__name__)


class BaseRequestHandler:
    def handle(self, request) -> None:
        raise NotImplementedError


class BaseMessageHandler:
    OK_RESPONSE = {"statusCode": 200}
    FORDIDDEN_RESPONSE = {"statusCode": 403}
    bottles = None

    def get_message(self, event: dict) -> models.Message:
        raise NotImplementedError

    def reply_message(
        self, text: str, markdown: bool = False, buttons: Optional[list] = None
    ):
        raise NotImplementedError

    def handle(self, event):
        self.event = event
        self.message = self.get_message(event)

        if isinstance(self.message, models.ButtonCallback) or isinstance(
            self.message, models.Command
        ):
            return callbacks.command(self)

        return callbacks.text(self)
