import json
import os

isUnitTest = False if os.getenv("LAMBDA_TASK_ROOT") else True

if isUnitTest:
    from src.score import getScore
    from src.validation import validateScoreInput
else:
    from score import getScore
    from validation import validateScoreInput


def lambda_handler(event, context):
    """Sample pure Lambda function

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format

        Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format

    context: object, required
        Lambda Context runtime methods & attributes

        Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    Returns
    ------
    API Gateway Lambda Proxy Output Format: dict

        Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
    """

    error = validateScoreInput(event["body"])
    if error != None:
        return {
            "statusCode": 400,
            "body": "Bad Request. %s" % error,
        }

    score = getScore(json.loads(event["body"]))
    return {
        "statusCode": 200,
        "body": json.dumps(score),
    }
