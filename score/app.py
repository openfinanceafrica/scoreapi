import json
from typing import List
from datetime import timedelta, datetime

from common.score import PaymentStatus, Score, ScoreError, ScoreInput, ScoredMonth


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

    # try:
    #     ip = requests.get("http://checkip.amazonaws.com/")
    # except requests.RequestException as e:
    #     # Send some context about this error to Lambda Logs
    #     print(e)

    #     raise e

    validateInput(event)
    scoreInput = getScoreInputFromEvent(event)
    score = getScore(scoreInput)
    return {
        "statusCode": 200,
        "body": json.dumps(score),
    }


def validateInput(event):
    print('event:', event)
    return ''


def getScoreInputFromEvent(event):
    return ''


def getScore(scoreInput: ScoreInput) -> Score:
    paymentStartDate = datetime.fromisoformat(scoreInput['paymentStartDate'])
    start = paymentStartDate
    paymentEndDate = datetime.fromisoformat(scoreInput['paymentEndDate'])
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
    currentDate = datetime.fromisoformat(scoreInput['currentDate']) if scoreInput.get(
        'currentDate') else datetime.utcnow()

    # Nothing to show yet if the lease hasn't started yet
    if datetime.utcnow() < paymentStartDate and not scoreInput.get('scoreBeforeLeaseStart'):
        return {
            'overallScore': overallScore,
            'paidStreak': 0,
            'balance': 0,
            'overDueStreak': 0,
            'scoredMonths': scoredMonths,
            'expectedPaymentAmount': expectedPaymentAmount,
            'error': ScoreError.LEASE_NOT_STARTED.name
        }

    while start <= paymentEndDate and start <= currentDate:
        # "rentDay + 1" since the payments would be considered late after the
        # expected payment day
        if (expectedPaymentDay + 1) == start.day:
            expectedPayments += expectedPaymentAmount
            lastPaymentDate = None
            actualPayments = 0

            for payment in scoreInput['payments']:
                if datetime.fromisoformat(payment['date']) < start:
                    # todo: using payment.amount.toString() since actualPayments sum is being prefixed with 0 for some reason
                    actualPayments += payment['amount']
                else:
                    break

                lastPaymentDate = datetime.fromisoformat(payment['date'])

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
        status = PaymentStatus.OVERPAID

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
