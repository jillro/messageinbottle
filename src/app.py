from messenger import MessengerHandler
from telegram import TelegramHandler


def lambda_handler(event, context):
    """AWS Lambda function

    :param event: API Gateway Lambda Proxy Input Format
    :param context: Lambda Context runtime methods and attributes
    :type event: dict
    :type context: object
    :return :API Gateway Lambda Proxy Output Format
    :rtype: dict

    Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format
    Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html
    Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
    """
    if event["resource"].startswith("/telegram"):
        return TelegramHandler().handle(event)

    if event["resource"].startswith("/facebook-messenger"):
        return MessengerHandler().handle(event)
