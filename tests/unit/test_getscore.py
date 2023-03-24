import json
import pytest
from src.score import getScore
from src.score_types import Score, ScoreInput, PaymentStatus

def test_full_score():
    input_data = ScoreInput(
        paymentStartDate="2021-01-01",
        paymentEndDate="2021-03-31",
        expectedPaymentDay=15,
        expectedPaymentAmount=500,
        payments=[
            {"date": "2021-01-15", "amount": 500},
            {"date": "2021-02-15", "amount": 500},
            {"date": "2021-03-15", "amount": 500},
        ],
        reference="test",
        scoreBeforeStartDate=False,
    )
    expected_output = Score(
        overallScore=1.0,
        paidStreak=3,
        overDueStreak=0,
        scoredMonths=[
            {
                "status": PaymentStatus.PAID.name,
                "score": 1.0,
                "dueDate": "2021-01-15T00:00:00+00:00",
                "balance": 0,
            },
            {
                "status": PaymentStatus.PAID.name,
                "score": 1.0,
                "dueDate": "2021-02-15T00:00:00+00:00",
                "balance": 0,
            },
            {
                "status": PaymentStatus.PAID.name,
                "score": 1.0,
                "dueDate": "2021-03-15T00:00:00+00:00",
                "balance": 0,
            },
        ],
        expectedPaymentAmount=500,
        balance=0,
    )
    assert getScore(input_data) == expected_output
