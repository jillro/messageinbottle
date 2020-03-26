from dataclasses import dataclass, asdict as _base_asdict, field
from datetime import datetime, timezone
from typing import Any, Optional

import boto3

import settings

prefix = settings.TABLE_PREFIX

dynamodb = boto3.resource("dynamodb", region_name="eu-west-3")
bottles_table = dynamodb.Table(f"{prefix}bottles")
users_table = dynamodb.Table(f"{prefix}users")
bottles_seq_table = dynamodb.Table(f"{prefix}bottles_seq")
callbacks_table = dynamodb.Table(f"{prefix}callbacks")
conversations_table = dynamodb.Table(f"{prefix}conversations")

APP_TELEGRAM = "telegram"
APP_MESSENGER = "messenger"


@dataclass
class Question:
    name: str
    params: Optional[dict] = None


@dataclass
class User:
    @classmethod
    def generate_id(cls, app: str, app_id: Any):
        return f"{app} {app_id}"

    id: str
    created: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    bottles_updated: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    bottles: int = 5
    question: Optional[Question] = None
    first_bottle: bool = False

    def __post_init__(self):
        if isinstance(self.question, dict):
            self.question = Question(**self.question)
        if isinstance(self.created, str):
            self.created = datetime.fromisoformat(self.created)
        if isinstance(self.bottles_updated, str):
            self.bottles_updated = datetime.fromisoformat(self.bottles_updated)

    def __repr__(self):
        return f"<User id={self.id}>"

    def __str__(self):
        return self.id


def asddbdict(instance):
    return _base_asdict(
        instance,
        dict_factory=lambda tuples: {
            key: value.isoformat() if isinstance(value, datetime) else value
            for key, value in tuples
        },
    )
