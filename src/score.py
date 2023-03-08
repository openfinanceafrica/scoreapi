from typing import List
from datetime import timedelta, datetime, timezone
from score_types import PaymentStatus, Score, ScoreError, ScoreInput, ScoredMonth
from dateutil import parser


def getScore(scoreInput: ScoreInput) -> Score:
    paymentStartDate = parser.isoparse(scoreInput['paymentStartDate'])
    start = paymentStartDate
    paymentEndDate = parser.isoparse(scoreInput['paymentEndDate'])
    expectedPaymentDay = scoreInput['expectedPaymentDay']
    expectedPaymentAmount = scoreInput['expectedPaymentAmount']
    totalScore = 0
    expectedPayments = 0
    scoredMonths: List[ScoredMonth] = []
    overallScore = 0
    paidStreak = 0
    longestPaidStreak = 0
    overDueStreak = 0
    longestOverDueStreak = 0
    balance = 0
    currentDate = parser.isoparse(scoreInput['currentDate']) if scoreInput.get(
        'currentDate') else datetime.now(timezone.utc)

    # We need to ensure that we are consistently using timezone aware dates so we don't get the error:
    # "can't compare offset-naive and offset-aware datetimes"
    # If timezone info isn't included in a date within the request the it's assumed to be UTC.
    if paymentStartDate.tzinfo is None or paymentStartDate.tzinfo.utcoffset(paymentStartDate) is None:
        paymentStartDate = paymentStartDate.astimezone()
        start = paymentStartDate
    if paymentEndDate.tzinfo is None or paymentEndDate.tzinfo.utcoffset(paymentEndDate) is None:
        paymentEndDate = paymentEndDate.astimezone()
    if currentDate.tzinfo is None or currentDate.tzinfo.utcoffset(currentDate) is None:
        currentDate = currentDate.astimezone()

    # If paymentStartDate is still in the future and scoreBeforeStartDate isn't specified in the request,
    # we'll exit immediately. It's not necessarily an error but we want users to explicitly say whether
    # they want to score future dates.
    if datetime.now(timezone.utc) < paymentStartDate and not scoreInput.get('scoreBeforeStartDate'):
        return {
            'overallScore': overallScore,
            'paidStreak': 0,
            'balance': 0,
            'overDueStreak': 0,
            'scoredMonths': scoredMonths,
            'expectedPaymentAmount': expectedPaymentAmount,
            'error': ScoreError.START_DATE_IN_FUTURE.name
        }

    while start <= paymentEndDate and start <= currentDate:
        # "rentDay + 1" since the payments would be considered late after the
        # expected payment day
        if (expectedPaymentDay + 1) == start.day:
            expectedPayments += expectedPaymentAmount
            lastPaymentDate = None
            actualPayments = 0

            for payment in scoreInput['payments']:
                if parser.isoparse(payment['date']) < start:
                    # todo: using payment.amount.toString() since actualPayments sum is being prefixed with 0 for some reason
                    actualPayments += payment['amount']
                else:
                    break

                lastPaymentDate = parser.isoparse(payment['date'])

            scoredMonth = getScoredMonth(
                expectedPaymentAmount,
                actualPayments,
                expectedPayments,
                start - timedelta(days=1),
                lastPaymentDate
            )
            # print('s:', scoredMonth)

            scoredMonths.append(scoredMonth)
            totalScore += scoredMonth['score']
            balance = scoredMonth['balance']

        start = start + timedelta(days=1)

    for scoredMonth in scoredMonths:
        if scoredMonth['status'] == PaymentStatus.PAID.name or scoredMonth['status'] == PaymentStatus.OVERPAID.name:
            paidStreak += 1
            overDueStreak = 0

        if scoredMonth['status'] == PaymentStatus.OVERDUE.name:
            overDueStreak += 1
            paidStreak = 0

        if paidStreak > longestPaidStreak:
            longestPaidStreak = paidStreak

        if overDueStreak > longestOverDueStreak:
            longestOverDueStreak = overDueStreak

    # Limit overall score to 1
    if len(scoredMonths) > 0:
        overallScore = 1 if round(
            totalScore / len(scoredMonths), 2) > 1 else round(totalScore / len(scoredMonths), 2)

    result = {
        'overallScore': overallScore,
        'balance': balance,
        'paidStreak': longestPaidStreak,
        'overDueStreak': longestOverDueStreak,
        'scoredMonths': scoredMonths,
        'expectedPaymentAmount': expectedPaymentAmount,
    }

    if len(scoredMonths) < 1:
        result['error'] = ScoreError.NO_SCORED_MONTHS.name

    return result


def getScoredMonth(expectedPaymentAmount: int, amountPaid: int, expectedPayment: int, dueDate: datetime, lastPaymentDate: datetime) -> ScoredMonth:
    score = None
    fullOrPartialPaymentMade = True
    status = PaymentStatus.UNKNOWN.name

    balance = amountPaid - expectedPayment

    if not lastPaymentDate:
        return {score: 0, status: PaymentStatus.OVERDUE.name, dueDate: dueDate, balance: balance}

    timeBonus = 0
    if dueDate < lastPaymentDate:
        timeBonus = (dueDate.date() - lastPaymentDate.date()) * 0.01

    if balance == 0:
        score = 1
        score = score
        status = PaymentStatus.PAID.name

    if balance > 0:
        score = 1 + (balance / expectedPaymentAmount) * 0.01
        score = score
        status = PaymentStatus.OVERPAID.name

    if balance < 0:
        score = 0
        fullOrPartialPaymentMade = False
        status = PaymentStatus.OVERDUE.name

    if score == None:
        print('Score could not be calculated. Balance: %s' % balance)
        return {score: -1, status: PaymentStatus.UNKNOWN.name, dueDate: dueDate, balance: balance}

    if fullOrPartialPaymentMade:
        score = score + timeBonus

    # If the score is 0 we'll give credit for previous payments made
    if score == 0:
        overallPaymentsBonus = (amountPaid / expectedPayment) * 0.3
        score += overallPaymentsBonus

    score = round(score, 2)

    return {
        'score': score,
        'status': status,
        'dueDate': dueDate.isoformat(),
        'balance': balance
    }
