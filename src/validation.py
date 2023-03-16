import json
from constants import (
    EXPECTED_PAYMENT_DAY_MAXIMUM,
    EXPECTED_PAYMENT_DAY_MINIMUM,
    EXPECTED_PAYMENT_AMOUNT_MINIMUM,
)
from score_types import ScoreInput
from dateutil import parser
import collections.abc


def validateScoreInput(input: ScoreInput):
    error = None
    inputObj = None
    try:
        inputObj = json.loads(input)
    except:
        return "Sorry, we were unable to parse your request. Ensure that you have the correct structure for the request as shown in our documentation (https://openfinance.africa/api/docs). You may also contact api@openfinance.africa for help."

    try:
        parser.isoparse(inputObj["paymentStartDate"])
    except Exception as e:
        return '"paymentStartDate" is invalid. The format should be full-date as defined by "RFC 3339, section 5.6" (https://tools.ietf.org/html/rfc3339#section-5.6). For example: "2023-03-08T07:15:32.42"'

    try:
        paymentEndDate = inputObj.get("paymentEndDate")
        if paymentEndDate:
            parser.isoparse(inputObj["paymentEndDate"])
    except Exception as e:
        return '"paymentEndDate" is invalid. The format should be full-date as defined by "RFC 3339, section 5.6" (https://tools.ietf.org/html/rfc3339#section-5.6). For example: "2023-03-08T07:15:32.42"'

    try:
        if type(inputObj["expectedPaymentDay"]) != int and (
            inputObj["expectedPaymentDay"] < EXPECTED_PAYMENT_DAY_MINIMUM
            or inputObj["expectedPaymentDay"] > EXPECTED_PAYMENT_DAY_MAXIMUM
        ):
            raise
    except Exception as e:
        print(e)
        return 'The value of "expectedPaymentDay" should be between 1 and 28.'

    try:
        if (
            type(inputObj["expectedPaymentAmount"]) != int
            and type(inputObj["expectedPaymentAmount"]) != float
        ) or inputObj["expectedPaymentAmount"] < EXPECTED_PAYMENT_AMOUNT_MINIMUM:
            raise
    except Exception as e:
        print(e)
        return 'The value of "expectedPaymentAmount" must be a number.'

    try:
        if not isinstance(inputObj["payments"], collections.abc.Sequence):
            raise
    except Exception as e:
        print(e)
        return 'The value of "payments" must be an array of Payment objects'

    return error
