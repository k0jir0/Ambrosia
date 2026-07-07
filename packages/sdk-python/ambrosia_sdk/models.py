from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

JsonObject = dict[str, Any]


def _clean(payload: JsonObject) -> JsonObject:
    return {key: value for key, value in payload.items() if value is not None}


@dataclass(frozen=True)
class SignalCreate:
    name: str
    formula: str
    universe: list[str] = field(default_factory=lambda: ["SPY"])
    horizon: str = "20d"
    cost_model: str | None = None
    benchmark: str | None = None
    validation_gates: list[str] | None = None

    def to_payload(self) -> JsonObject:
        return _clean(
            {
                "name": self.name,
                "formula": self.formula,
                "universe": self.universe,
                "horizon": self.horizon,
                "costModel": self.cost_model,
                "benchmark": self.benchmark,
                "validationGates": self.validation_gates,
            }
        )


@dataclass(frozen=True)
class SignalDecisionWriteback:
    review_id: str
    decision_state: str
    decision_action: str | None = None
    decision_quality: str = "D2"
    override_used: bool = False
    rationale: str | None = None
    evidence_links: list[str] = field(default_factory=list)
    verifier_status: str | None = None
    review_date: str | None = None

    def to_payload(self) -> JsonObject:
        return _clean(
            {
                "reviewId": self.review_id,
                "decisionState": self.decision_state,
                "decisionAction": self.decision_action,
                "decisionQuality": self.decision_quality,
                "overrideUsed": self.override_used,
                "rationale": self.rationale,
                "evidenceLinks": self.evidence_links,
                "verifierStatus": self.verifier_status,
                "reviewDate": self.review_date,
            }
        )


@dataclass(frozen=True)
class SignalReviewLink:
    review_id: str
    hypothesis_id: str | None = None
    signal_version: int | None = None

    def to_payload(self) -> JsonObject:
        return _clean(
            {
                "reviewId": self.review_id,
                "hypothesisId": self.hypothesis_id,
                "signalVersion": self.signal_version,
            }
        )


@dataclass(frozen=True)
class SignalOutcomeWriteback:
    review_id: str
    outcome_quality: str
    last_reviewed_at: str | None = None

    def to_payload(self) -> JsonObject:
        return _clean(
            {
                "reviewId": self.review_id,
                "outcomeQuality": self.outcome_quality,
                "lastReviewedAt": self.last_reviewed_at,
            }
        )


@dataclass(frozen=True)
class AlphaHypothesisCreate:
    title: str
    signal_family: str
    thesis: str
    universe: list[str] = field(default_factory=lambda: ["SPY"])
    horizon: str = "20d"
    disconfirming_tests: list[str] = field(default_factory=list)

    def to_payload(self) -> JsonObject:
        return {
            "title": self.title,
            "signalFamily": self.signal_family,
            "thesis": self.thesis,
            "universe": self.universe,
            "horizon": self.horizon,
            "disconfirmingTests": self.disconfirming_tests,
        }


@dataclass(frozen=True)
class PaperTradeCreate:
    decision_id: str
    ticker: str
    quantity: float
    side: str = "buy"
    intended_price: float = 100.0

    def to_payload(self) -> JsonObject:
        return {
            "decisionId": self.decision_id,
            "ticker": self.ticker,
            "quantity": self.quantity,
            "side": self.side,
            "intendedPrice": self.intended_price,
        }
