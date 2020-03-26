import strings


def generate_status(handler):
    return strings.STATUS.format(bottles=handler.user.bottles)
