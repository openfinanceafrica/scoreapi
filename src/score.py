from typing import List
from datetime import timedelta, datetime, timezone, time
from dateutil import parser
import os
import pytz

isUnitTest = False if os.getenv("LAMBDA_TASK_ROOT") else True

if isUnitTest:
    from src.score_types import (
        PaymentStatus,
        Score,
        ScoreError,
        ScoreInput,
        ScoredMonth,
    )
    from src.constants import (
        PREVIOUS_PAYMENTS_BONUS_MULTIPLIER,
        SCORE_MULTIPLIER,
        TIME_BONUS_AFTER_DUE_DATE_MULTIPLIER,
        TIME_BONUS_MULTIPLIER,
    )
else:
    from score_types import PaymentStatus, Score, ScoreError, ScoreInput, ScoredMonth
    from constants import (
        PREVIOUS_PAYMENTS_BONUS_MULTIPLIER,
        SCORE_MULTIPLIER,
        TIME_BONUS_AFTER_DUE_DATE_MULTIPLIER,
        TIME_BONUS_MULTIPLIER,
    )


def getScore(scoreInput: ScoreInput) -> Score:
    """Main function that calculates and returns a score

    Keyword arguments:
    ScoreInput -- This is an object that includes:
    1. A start and end date, the day of the month a payment is expected, and the amount expected.
    For example, a tenant may have a lease which starts on Jan 1 2024 (start) to Dec 31 2024 (end) and expected payment date of the 5th.
    2. A list of payments that have been made by the individual getting scored. This includes the date/time that the payment was made as well as the amount.
    See the definition on score_types.py to see all the fields available.
    """

    paymentStartDate = parser.isoparse(scoreInput["paymentStartDate"])
    start = paymentStartDate
    paymentEndDate = (
        parser.isoparse(scoreInput["paymentEndDate"])
        if scoreInput.get("paymentEndDate")
        else datetime.now(timezone.utc)
    )
    expectedPaymentDay = scoreInput["expectedPaymentDay"]
    expectedPaymentAmount = scoreInput["expectedPaymentAmount"]
    totalScore = 0
    totalExpectedPayments = 0
    scoredMonths: List[ScoredMonth] = []
    overallScore = 0
    paidStreak = 0
    longestPaidStreak = 0
    overDueStreak = 0
    longestOverDueStreak = 0
    balance = 0

    # We need to ensure that we are consistently using timezone aware dates so we don't get the error:
    # "can't compare offset-naive and offset-aware datetimes"
    # If timezone info isn't included in a date within the request the it's assumed to be UTC.
    # We do this in other places in this file as well.
    if (
        paymentStartDate.tzinfo is None
        or paymentStartDate.tzinfo.utcoffset(paymentStartDate) is None
    ):
        paymentStartDate = pytz.utc.localize(paymentStartDate)
        start = paymentStartDate
    if (
        paymentEndDate.tzinfo is None
        or paymentEndDate.tzinfo.utcoffset(paymentEndDate) is None
    ):
        paymentEndDate = pytz.utc.localize(paymentEndDate)

    # If paymentStartDate is still in the future and scoreBeforeStartDate isn't specified in the request,
    # we'll exit immediately. It's not necessarily an error but we want users to explicitly say whether
    # they want to score future dates.
    if datetime.now(timezone.utc) < paymentStartDate and not scoreInput.get(
        "scoreBeforeStartDate"
    ):
        return {
            "overallScore": overallScore,
            "paidStreak": 0,
            "balance": 0,
            "overDueStreak": 0,
            "scoredMonths": scoredMonths,
            "expectedPaymentAmount": expectedPaymentAmount,
            "error": ScoreError.START_DATE_IN_FUTURE.name,
        }
    
    while start <= paymentEndDate:
        # We want to do our calculation on expectedPaymentDay + 1 to allow
        # for payments made at the last minute of the expected payment day
        if expectedPaymentDay + 1 == start.day:
            # Since we've essentially fast forwarded a day, let's use current in place of start in this block
            current = start - timedelta(days=1)
            totalExpectedPayments += expectedPaymentAmount
            lastPaymentDate = None
            actualPayments = 0
            balancePaymentDateAfterDueDate = None
            actualPaymentsAfterDueDate = 0

            for payment in scoreInput["payments"]:
                date = parser.isoparse(payment["date"])
                if date.tzinfo is None or date.tzinfo.utcoffset(date) is None:
                    date = pytz.utc.localize(date)

                # Get the actual total payments made before or on the due date and also keep track of the
                # last payment date (the earlier the payment, the better if balance is paid off)
                currentMax = pytz.utc.localize(datetime.combine(current, time.max))
                if date <= currentMax:
                    actualPayments += int(payment["amount"])
                    lastPaymentDate = parser.isoparse(payment["date"])
                # Get the date when the balance was paid. The delta between the due date and the time the balance was
                # paid off will be a factor in scoring.
                else:
                    actualPaymentsAfterDueDate += int(payment["amount"])
                    if (
                        (actualPayments + actualPaymentsAfterDueDate)
                        - totalExpectedPayments
                    ) >= 0:
                        balancePaymentDateAfterDueDate = parser.isoparse(
                            payment["date"]
                        )
                        break

            scoredMonth = getScoredMonth(
                expectedPaymentAmount,
                actualPayments,
                totalExpectedPayments,
                current,
                lastPaymentDate,
                balancePaymentDateAfterDueDate,
            )

            scoredMonths.append(scoredMonth)
            totalScore += scoredMonth["score"]
            balance = scoredMonth["balance"]

        start = start + timedelta(days=1)

    for scoredMonth in scoredMonths:
        if (
            scoredMonth["status"] == PaymentStatus.PAID.name
            or scoredMonth["status"] == PaymentStatus.OVERPAID.name
        ):
            paidStreak += 1
            overDueStreak = 0

        if scoredMonth["status"] == PaymentStatus.OVERDUE.name:
            overDueStreak += 1
            paidStreak = 0

        if paidStreak > longestPaidStreak:
            longestPaidStreak = paidStreak

        if overDueStreak > longestOverDueStreak:
            longestOverDueStreak = overDueStreak

    # Limit overall score to 1
    if len(scoredMonths) > 0:
        overallScore = (
            1
            if round(totalScore / len(scoredMonths), 2) > 1
            else round(totalScore / len(scoredMonths), 2)
        )

    result = {
        "overallScore": overallScore,
        "balance": balance,
        "paidStreak": longestPaidStreak,
        "overDueStreak": longestOverDueStreak,
        "scoredMonths": scoredMonths,
        "expectedPaymentAmount": expectedPaymentAmount,
    }

    if len(scoredMonths) < 1:
        result["error"] = ScoreError.NO_SCORED_MONTHS.name

    return result


def getScoredMonth(
    expectedPaymentAmount: int,
    amountPaid: int,
    totalExpectedPayments: int,
    dueDate: datetime,
    lastPaymentDate: datetime,
    balancePaymentDateAfterDueDate: datetime,
) -> ScoredMonth:
    """Calculates the score of an individual month

    Keyword arguments:
    expectedPaymentAmount -- The amount expected to be paid each month
    amountPaid -- The total amount/balance that has been paid so far
    totalExpectedPayments -- The total amount/balance that is expected to be paid by "dueDate"
    dueDate -- The date in the month that is derived from the day a payment is expected
    lastPaymentDate -- The date that the last payment was made before "dueDate"
    balancePaymentDateAfterDueDate -- The date after "dueDate" when the balance was paid (if payment was late)
    """

    score = None
    status = PaymentStatus.UNKNOWN.name

    balance = amountPaid - totalExpectedPayments
    if not lastPaymentDate and not balancePaymentDateAfterDueDate:
        return {
            "score": 0,
            "status": PaymentStatus.OVERDUE.name,
            "dueDate": dueDate.isoformat(),
            "balance": balance,
        }

    if (
        lastPaymentDate and (lastPaymentDate.tzinfo is None
        or lastPaymentDate.tzinfo.utcoffset(lastPaymentDate) is None)
    ):
        lastPaymentDate = pytz.utc.localize(lastPaymentDate)

    # Get a time bonus based on how early the payment was made before the due date
    timeBonus = 0
    if lastPaymentDate and lastPaymentDate < dueDate and balance >= 0:
        # need to use 'total_seconds' rather than 'days' for accuracy
        days = (dueDate - lastPaymentDate).total_seconds() / (24 * 60 * 60)
        timeBonus = round(days * TIME_BONUS_MULTIPLIER, 2)

    if balance == 0:
        score = 1
        score = score
        status = PaymentStatus.PAID.name

    if balance > 0:
        score = 1 + (balance / expectedPaymentAmount) * SCORE_MULTIPLIER
        score = score
        status = PaymentStatus.OVERPAID.name

    if balance < 0:
        score = 0
        status = PaymentStatus.OVERDUE.name
        # Get a time bonus based on how early the payment was made after the due date
        if balancePaymentDateAfterDueDate:
            # need to use 'total_seconds' rather than 'days' for accuracy
            days = (balancePaymentDateAfterDueDate - dueDate).total_seconds() / (
                24 * 60 * 60
            )
            timeBonus = round(1 - (days * TIME_BONUS_AFTER_DUE_DATE_MULTIPLIER), 2)
            if timeBonus < 0:
                timeBonus = 0

    if score == None:
        print("Score could not be calculated. Balance: %s" % balance)
        return {
            "score": -1,
            "status": PaymentStatus.UNKNOWN.name,
            "dueDate": dueDate.isoformat(),
            "balance": balance,
        }

    score = score + timeBonus

    # If the score is 0 we'll give credit for previous payments made
    if score == 0:
        overallPaymentsBonus = (
            amountPaid / totalExpectedPayments
        ) * PREVIOUS_PAYMENTS_BONUS_MULTIPLIER
        score += overallPaymentsBonus

    score = round(score, 2)

    return {
        "score": score,
        "status": status,
        "dueDate": dueDate.isoformat(),
        "balance": balance,
    }
