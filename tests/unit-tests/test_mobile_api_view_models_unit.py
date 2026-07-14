from __future__ import annotations

from services.api.app.mobile_api import (
    _review_hard_blocks,
    _review_next_action,
    _review_risk_gate,
    _review_runbook,
    _review_signal_writeback_hint,
    _review_summary,
)
from services.api.app.models import DecisionState, ThesisRequest
from services.api.app.review_engine import generate_review


def _review():
    return generate_review(
        ThesisRequest(
            thesis="SPY breadth is improving after a defensive rotation.",
            ticker="SPY",
            asset_class="US equities",
            time_horizon="1-4 weeks",
            intended_expression="Long SPY",
            source_pointer="scanner:SPY:momentum_up:2026-07-13T00:00:00Z",
        ),
        trial_count=2,
    )


def test_review_summary_keeps_mobile_shape_compact() -> None:
    review = _review()
    summary = _review_summary(review)

    assert summary["schemaVersion"] == "review.v1"
    assert summary["workflowVersion"] == "adversarial-review.v1"
    assert summary["ticker"] == "SPY"
    assert summary["status"] == "synthesis"
    assert summary["decisionState"] is None
    assert summary["claimCount"] == len(review.claims)
    assert summary["sourceCount"] == len(review.sources)
    assert summary["auditCount"] == len(review.audit)
    assert summary["validation"]["status"] == "specified"


def test_hard_blocks_next_action_and_risk_gate_reflect_tradeability_risk() -> None:
    review = _review()
    hard_blocks = _review_hard_blocks(review)
    risk_gate = _review_risk_gate(review, hard_blocks)

    assert hard_blocks == ["high_tradeability_question"]
    assert _review_next_action(review, hard_blocks) == "resolve_hard_blocks_before_pursue"
    assert risk_gate["status"] == "blocked"
    assert risk_gate["hardBlockCount"] == 1
    assert risk_gate["requiresServerConfirmation"] is True
    assert risk_gate["executionAuthority"] == "human_review_only"


def test_runbook_blocks_gate_stages_until_review_is_decision_ready() -> None:
    review = _review()
    runbook = _review_runbook(review, _review_hard_blocks(review))
    stage_status = {stage["id"]: stage["status"] for stage in runbook}

    assert stage_status["intake"] == "complete"
    assert stage_status["retrieval"] == "complete"
    assert stage_status["adversarial_review"] == "complete"
    assert stage_status["validation"] == "blocked"
    assert stage_status["tradeability"] == "blocked"
    assert stage_status["synthesis"] == "blocked"


def test_signal_writeback_requires_a_human_decision_and_no_hard_blocks() -> None:
    blocked_review = _review()
    blocked_hint = _review_signal_writeback_hint(blocked_review, _review_hard_blocks(blocked_review))

    ready_review = blocked_review.model_copy(
        update={
            "decisionState": DecisionState.pursue,
            "tradeability": [],
            "confidence": 72,
        }
    )
    ready_hint = _review_signal_writeback_hint(ready_review, _review_hard_blocks(ready_review))

    assert blocked_hint["canWriteDecision"] is False
    assert blocked_hint["status"] == "review_or_evidence_required"
    assert ready_hint["canWriteDecision"] is True
    assert ready_hint["status"] == "ready_to_link"
    assert ready_hint["executionReadiness"] == "paper_trade_ready"

