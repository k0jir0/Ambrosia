from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class DecisionState(str, Enum):
    pursue = "pursue"
    watch = "watch"
    reject = "reject"
    needs_more_data = "needs_more_data"


class ReviewStatus(str, Enum):
    intake = "intake"
    retrieval = "retrieval"
    adversarial_review = "adversarial_review"
    validation = "validation"
    tradeability = "tradeability"
    synthesis = "synthesis"
    decision_recorded = "decision_recorded"


class ThesisRequest(BaseModel):
    thesis: str = Field(min_length=8)
    ticker: str = "Unspecified"
    asset_class: str = "Unspecified"
    time_horizon: str = "Unspecified"
    intended_expression: str = "Expression requires review"
    source_pointer: str = ""


class Claim(BaseModel):
    id: str
    kind: Literal["sourced", "assumption", "inference", "contradiction", "unknown"]
    text: str
    evidence: str | None = None
    confidence: int = Field(ge=0, le=100)


class SourcePointer(BaseModel):
    id: str
    title: str
    sourceType: str
    timestamp: str
    permission: Literal["user_owned", "pointer_only", "public"]
    relevance: float = Field(ge=0, le=1)


class ValidationSpec(BaseModel):
    status: Literal["specified", "refused"]
    hypothesis: str
    nullHypothesis: str
    dataRequirements: list[str]
    protocol: str
    refusalReason: str | None = None


class TradeabilityQuestion(BaseModel):
    topic: str
    question: str
    severity: Literal["low", "medium", "high"]


class AuditEvent(BaseModel):
    id: str
    timestamp: str
    eventType: str
    detail: str


class HistoricalAnalogue(BaseModel):
    title: str
    similarity: str
    differences: str
    resolution: str


class TradeReview(BaseModel):
    id: str
    schemaVersion: str = "review.v1"
    workflowVersion: str = "adversarial-review.v1"
    title: str
    thesis: str
    ticker: str
    assetClass: str
    timeHorizon: str
    intendedExpression: str
    status: ReviewStatus
    decisionState: DecisionState | None
    confidence: int = Field(ge=0, le=100)
    trialCountImpact: int
    followUpDate: str
    createdAt: str
    claims: list[Claim]
    strongestCritique: str
    disconfirmingTest: str
    historicalAnalogue: HistoricalAnalogue
    validation: ValidationSpec
    tradeability: list[TradeabilityQuestion]
    sources: list[SourcePointer]
    audit: list[AuditEvent]


class DecisionUpdate(BaseModel):
    decision_state: DecisionState


class OutcomeUpdate(BaseModel):
    outcome: str
    outcome_date: str