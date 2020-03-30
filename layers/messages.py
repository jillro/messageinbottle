from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any

from botocore.exceptions import ClientError

from models import balloons_seq_table


@dataclass
class Message:
    id: Optional[str]
    user_id: str
    text: str
    raw: dict
    datetime: str = field(
        init=False, default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @classmethod
    def generate_id(cls, app: str, app_id: Any):
        return f"{app} {app_id}"


@dataclass
class SentMessage(Message):
    reply_to: Optional[str] = None
    pass


@dataclass
class IncomingMessage(Message):
    tags: str = field(init=False)
    seq: Optional[int] = field(init=False)
    sender_display_name: str
    reply_to: Optional[str] = None

    def __post_init__(self):
        self.tags = self.extract_and_sort_hashtags(default=["world"])

    def set_seq(self):
        try:
            self.seq = balloons_seq_table.update_item(
                Key={"tags": self.tags},
                UpdateExpression="SET seq = if_not_exists (seq, :0) + :1, last_message_day = :last_message_day, last_message = :last_message",
                ExpressionAttributeValues={
                    ":0": 0,
                    ":1": 1,
                    ":last_message_day": datetime.fromisoformat(self.datetime)
                    .date()
                    .isoformat(),
                    ":last_message": self.datetime,
                },
                ReturnValues="UPDATED_NEW",
            )["Attributes"]["seq"]
        except ClientError as e:
            raise e

    def extract_and_sort_hashtags(self, default):
        tags = sorted(
            set(part[1:] for part in self.text.split() if part.startswith("#"))
        )

        if len(tags) == 0:
            tags = default

        return " ".join(tags)


@dataclass
class ButtonCallback(IncomingMessage):
    original_message: Optional[IncomingMessage] = None


@dataclass
class Command(IncomingMessage):
    pass
