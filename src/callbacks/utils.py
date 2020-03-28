import strings


def generate_status(handler):
    return strings.STATUS.format(balloons=handler.user.balloons)
