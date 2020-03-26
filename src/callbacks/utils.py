import messages


def generate_status(handler):
    return messages.STATUS.format(bottles=handler.user.bottles)
