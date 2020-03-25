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
    user: models.User = None
    message: models.IncomingMessage = None

    def get_message(self) -> models.IncomingMessage:
        raise NotImplementedError

    def get_user(self):
        res = models.users_table.get_item(Key={"id": self.message.user_id})
        if "Item" in res:
            user = models.User(**res["Item"])
        else:
            user = models.User(id=self.message.user_id)
            models.users_table.put_item(
                Item=models.asddbdict(models.User(id=self.message.user_id))
            )

        return user

    def reply_message(
        self, text: str, markdown: bool = False, buttons: Optional[list] = None
    ) -> models.SentMessage:
        message = models.SentMessage(
            id=None, user_id=self.message.user_id, text=text, raw={}
        )

        send_message(message, markdown=markdown, buttons=buttons)

        return message

    def set_question(self, question: models.Question):
        assert question.name in callbacks.text

        models.users_table.update_item(
            Key={"id": self.message.user_id},
            UpdateExpression="SET question = :question",
            ExpressionAttributeValues={":question": models.asddbdict(question)},
        )

    def handle(self, event):
        self.event = event
        self.message = self.get_message()
        self.user = self.get_user()

        if isinstance(self.message, models.ButtonCallback) or isinstance(
            self.message, models.Command
        ):
            return callbacks.command(self)

        if self.message.reply_to is not None:
            return callbacks.text["default_reply_to"](self)

        self.user = models.User(
            **models.users_table.update_item(
                Key={"id": self.user.id},
                UpdateExpression="SET question = :None",
                ExpressionAttributeValues={":None": None},
                ReturnValues="ALL_OLD",
            )["Attributes"]
        )

        if self.user.question is not None:
            return callbacks.text[self.user.question.name](
                self, **self.user.question.params
            )

        return callbacks.text["default"](self)
