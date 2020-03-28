from dataclasses import dataclass, asdict as _base_asdict, field
from datetime import datetime, timezone
from typing import Any, Optional

import boto3

import settings

prefix = settings.TABLE_PREFIX

dynamodb = boto3.resource("dynamodb", region_name="eu-west-3")
existing_tables = boto3.client("dynamodb").list_tables()["TableNames"]


def get_or_create_table(table_name, primary_key=("id", "S"), sort_key=None):
    if table_name in existing_tables:
        return dynamodb.Table(table_name)

    attr_def = [{"AttributeName": primary_key[0], "AttributeType": primary_key[1]}]
    key_def = [{"AttributeName": primary_key[0], "KeyType": "HASH"}]

    if sort_key is not None:
        attr_def.append({"AttributeName": sort_key[0], "AttributeType": sort_key[1]})
        key_def.append({"AttributeName": sort_key[0], "KeyType": "RANGE"})

    dynamodb.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=attr_def,
        KeySchema=key_def,
    )

    return dynamodb.Table(table_name)


balloons_table = get_or_create_table(f"{prefix}balloons", ("tags", "S"), ("seq", "N"))
balloons_seq_table = get_or_create_table(f"{prefix}balloons_seq", ("tags", "S"))
callbacks_table = get_or_create_table(f"{prefix}callbacks")
users_table = get_or_create_table(f"{prefix}users")
conversations_table = get_or_create_table(f"{prefix}conversations")

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
    balloons_updated: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    balloons: int = 5
    question: Optional[Question] = None
    first_balloon: bool = False

    def __post_init__(self):
        if isinstance(self.question, dict):
            self.question = Question(**self.question)
        if isinstance(self.created, str):
            self.created = datetime.fromisoformat(self.created)
        if isinstance(self.balloons_updated, str):
            self.balloons_updated = datetime.fromisoformat(self.balloons_updated)

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
