from typing import Optional, TypedDict, List
from enum import Enum


class PaymentStatus(Enum):
    PAID = "PAID"
    PAID_PARTIALLY = "PAID_PARTIALLY"
    OVERPAID = "OVERPAID"
    PAID_LATE = "PAID_LATE"
    OVERDUE = "OVERDUE"
    UPCOMING = "UPCOMING"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"


class ScoredMonth(TypedDict):
    status: PaymentStatus
    score: int
    dueDate: str
    balance: int


class Payment(TypedDict):
    date: str
    amount: int


class ScoreInput(TypedDict):
    paymentStartDate: str
    paymentEndDate: Optional[str]
    expectedPaymentDay: int
    expectedPaymentAmount: int
    payments: List[Payment]
    reference: Optional[str]
    scoreBeforeStartDate: Optional[bool]


class ScoreError(Enum):
    START_DATE_IN_FUTURE = "START_DATE_IN_FUTURE"
    NO_SCORED_MONTHS = "NO_SCORED_MONTHS"


class Score(TypedDict):
    overallScore: int
    paidStreak: int
    overDueStreak: int
    scoredMonths: List[ScoredMonth]
    expectedPaymentAmount: int
    balance: int
    error: Optional[ScoreError]
