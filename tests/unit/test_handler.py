import json
import pytest
from src import app


@pytest.fixture()
def event_200():
    """Generates API GW Event"""

    return {
        "body": '{"paymentStartDate":"2017-07-21T17:32:28Z","paymentEndDate":"2018-07-21T17:32:28Z","expectedPaymentDay":1,"expectedPaymentAmount":5000,"payments":[{"amount":2000,"date":"2017-07-21T17:32:28Z"}]}',
    }


@pytest.fixture()
def event_400():
    """Generates API GW Event"""

    return {
        "body": "",
    }


def test_statusCode_200(event_200):
    ret = app.lambda_handler(event_200, "")
    assert ret["statusCode"] == 200


def test_statusCode_400(event_400):
    ret = app.lambda_handler(event_400, "")
    assert ret["statusCode"] == 400
