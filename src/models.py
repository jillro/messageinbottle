import boto3

dynamodb = boto3.resource("dynamodb", region_name="eu-west-3")
messages_table = dynamodb.Table("messageinabottle_messages")
