from dataclasses import dataclass
from typing import Any

import boto3

dynamodb = boto3.resource("dynamodb", region_name="eu-west-3")
messages_table = dynamodb.Table("messageinabottle_messages")

APP_TELEGRAM = "telegram"
APP_MESSENGER = "messenger"


@dataclass
class User:
    application: str
    id: Any

    def __repr__(self):
        return f"<User {self.application}, id={self.id}>"


@dataclass
class Message:
    user: User
    sender_display_name: str
    text: str
    raw: dict
