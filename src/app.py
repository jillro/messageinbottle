from exceptions import BeforeRecordError
from handlers import TelegramRequestHandler, MessengerRequestHandler


def lambda_handler(request, context):
    """AWS Lambda function

    :param request: API Gateway Lambda Proxy Input Format
    :param context: Lambda Context runtime methods and attributes
    :type request: dict
    :type context: object
    :return :API Gateway Lambda Proxy Output Format
    :rtype: dict

    Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format
    Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html
    Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
    """
    if request["resource"].startswith("/telegram"):
        try:
            TelegramRequestHandler().handle(request)
        except BeforeRecordError as e:
            return {"statusCode": e.status}

        return {"statusCode": 200}

    if request["resource"].startswith("/facebook-messenger"):
        try:
            MessengerRequestHandler().handle(request)
        except BeforeRecordError as e:
            return {"statusCode": e.status}

        return {"statusCode": 200}
