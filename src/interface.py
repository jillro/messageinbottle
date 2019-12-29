from dataclasses import dataclass


@dataclass
class Button:
    text: str


@dataclass
class PostbackButton(Button):
    payload: str
