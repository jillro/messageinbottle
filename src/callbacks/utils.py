import messages
from interface import PostbackButton


def generate_status(handler):
    return messages.STATUS.format(bottles=handler.user.bottles)
