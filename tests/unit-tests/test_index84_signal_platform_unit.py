from __future__ import annotations

import pytest
from fastapi import HTTPException

from services.api.app import index84_platform as platform


@pytest.fixture
def isolated_signal_state(monkeypatch):
    state_maps = [
        platform._features,
        platform._signals,
        platform._backtests,
        platform._signal_review_links,
        platform._signal_versions,
        platform._signal_validation_runs,
        platform._signal_policy_events,
        platform._scanner_promotions,
        platform._alpha_hypotheses,
    ]
    for state_map in state_maps:
        state_map.clear()
    monkeypatch.setattr(platform, "_persist_signal_state", lambda: None)
    yield
    for state_map in state_maps:
        state_map.clear()


def test_index84_stable_ids_and_endpoint_keys_are_deterministic(isolated_signal_state) -> None:
    first = platform._stable_id("signal", "SPY:momentum")
    second = platform._stable_id("signal", "SPY:momentum")
    other = platform._stable_id("signal", "QQQ:momentum")

    assert first == second
    assert first != other
    assert first.startswith("signal-")
    assert platform._endpoint_key("/signals") == "index84:/signals"


def test_execution_feasibility_blocks_large_or_expensive_orders(isolated_signal_state) -> None:
    small = platform._execution_feasibility_assessment("SPY", "buy", 10, 500)
    large = platform._execution_feasibility_assessment("XYZ", "buy", 2_000, 250)

    assert small["schemaVersion"] == "execution-feasibility.v1"
    assert small["ticker"] == "SPY"
    assert small["gate"] == "pass"
    assert small["reasons"] == ["within_warm_path_budget"]
    assert large["gate"] == "blocked"
    assert "notional_or_cost_limit_exceeded" in large["reasons"]


def test_signal_version_resolution_uses_active_version_and_validates_existence(isolated_signal_state) -> None:
    platform._signals["sig-1"] = {"signalId": "sig-1", "version": 2, "activeVersion": 2}
    platform._signal_versions["sig-1"] = [{"version": 1}, {"version": 2}]

    assert platform._resolve_signal_version("sig-1", None) == 2
    assert platform._resolve_signal_version("sig-1", 1) == 1

    with pytest.raises(HTTPException) as missing_version:
        platform._resolve_signal_version("sig-1", 3)
    with pytest.raises(HTTPException) as missing_signal:
        platform._resolve_signal_version("missing", None)

    assert missing_version.value.status_code == 404
    assert missing_signal.value.status_code == 404


def test_signal_review_link_lookup_prefers_latest_version(isolated_signal_state) -> None:
    platform._signal_review_links["link-1"] = {
        "linkId": "link-1",
        "signalId": "sig-1",
        "reviewId": "rev-1",
        "signalVersion": 1,
    }
    platform._signal_review_links["link-2"] = {
        "linkId": "link-2",
        "signalId": "sig-1",
        "reviewId": "rev-1",
        "signalVersion": 2,
    }

    latest = platform._find_signal_review_link("sig-1", "rev-1")
    explicit = platform._find_signal_review_link("sig-1", "rev-1", signal_version=1)
    missing = platform._find_signal_review_link("sig-1", "rev-1", signal_version=3)

    assert latest["linkId"] == "link-2"
    assert explicit["linkId"] == "link-1"
    assert missing is None


def test_required_validation_gates_and_signal_rollup(isolated_signal_state) -> None:
    signal = {
        "signalId": "sig-1",
        "version": 2,
        "activeVersion": 2,
        "status": "active_candidate",
        "validationGates": ["point_in_time", "costs", "walk_forward"],
        "latestDecisionState": "pursue",
        "latestOutcomeQuality": "O2",
        "lastReviewedAt": "2026-07-13T00:00:00Z",
    }
    platform._signals["sig-1"] = signal
    platform._signal_review_links["link-1"] = {
        "signalId": "sig-1",
        "reviewId": "rev-1",
        "signalVersion": 2,
        "reviewDecisionState": "pursue",
        "outcomeQuality": "O2",
        "lastOutcomeAt": "2026-07-20T00:00:00Z",
        "lastReviewedAt": "2026-07-19T00:00:00Z",
    }
    platform._signal_review_links["link-2"] = {
        "signalId": "sig-1",
        "reviewId": "rev-2",
        "signalVersion": 2,
        "reviewDecisionState": "reject",
        "overrideUsed": True,
    }
    platform._signal_validation_runs["sig-1"] = [
        {"signalId": "sig-1", "signalVersion": 2, "status": "passed", "completedAt": "2026-07-18T00:00:00Z"}
    ]

    gates_present, missing = platform._required_validation_gates_present(signal)
    rollup = platform._signal_rollup("sig-1")

    assert gates_present is True
    assert missing == []
    assert platform._required_validation_gates_present({"validationGates": ["costs"]}) == (
        False,
        ["point_in_time", "walk_forward"],
    )
    assert rollup["linkedDecisionCount"] == 2
    assert rollup["pursuedCount"] == 1
    assert rollup["rejectedCount"] == 1
    assert rollup["overrideCount"] == 1
    assert rollup["outcomeCount"] == 1
    assert rollup["latestValidationStatus"] == "passed"
