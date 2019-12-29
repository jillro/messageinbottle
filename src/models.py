import secrets
from dataclasses import dataclass, asdict as _base_asdict, field
from datetime import datetime, timezone
from typing import Any, Optional

import boto3

dynamodb = boto3.resource("dynamodb", region_name="eu-west-3")
messages_table = dynamodb.Table("messageinabottle_messages")
users_table = dynamodb.Table("messageinabottle_users")

APP_TELEGRAM = "telegram"
APP_MESSENGER = "messenger"


@dataclass
class User:
    @classmethod
    def generate_id(cls, app: str, app_id: Any):
        return f"{app} {app_id}"

    id: str
    created: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    bottles: int = 5

    def __repr__(self):
        return f"<User id={self.id}>"

    def __str__(self):
        return self.id


@dataclass
class Message:
    tags: str = field(init=False)
    user_id: str
    sender_display_name: str
    text: str
    raw: dict
    datetime: str = field(
        default_factory=lambda: " ".join(
            [datetime.now(timezone.utc).isoformat(), secrets.token_urlsafe(6)]
        )
    )

    def __post_init__(self):
        self.tags = self.extract_and_sort_hashtags(default=["world"])

    def extract_and_sort_hashtags(self, default):
        tags = sorted(
            set(part[1:] for part in self.text.split() if part.startswith("#"))
        )

        if len(tags) == 0:
            tags = default

        return " ".join(tags)


@dataclass
class ButtonCallback(Message):
    original_message: Optional[Message] = None


def asddbdict(instance):
    return _base_asdict(
        instance,
        dict_factory=lambda tuples: {
            key: value.isoformat() if isinstance(value, datetime) else value
            for key, value in tuples
        },
    )
