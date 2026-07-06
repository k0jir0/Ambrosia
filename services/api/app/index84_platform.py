from __future__ import annotations

import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(tags=["index84-platform"])

_relay_runs: dict[str, dict] = {}
_features: dict[str, dict] = {}
_signals: dict[str, dict] = {}
_backtests: dict[str, dict] = {}
_signal_review_links: dict[str, dict] = {}
_signal_versions: dict[str, list[dict]] = {}
_signal_validation_runs: dict[str, list[dict]] = {}
_signal_policy_events: dict[str, list[dict]] = {}
_paper_trades: dict[str, dict] = {}
_fills: dict[str, dict] = {}
_service_accounts: dict[str, dict] = {}
_audit_exports: dict[str, dict] = {}
_market_replays: dict[str, dict] = {}
_alpha_hypotheses: dict[str, dict] = {}
_warm_path_events: list[dict] = []
_sso_config: dict = {
    "enabled": False,
    "provider": "none",
    "issuerUrl": None,
    "audience": None,
    "defaultRole": "viewer",
    "roleMappings": {"analyst-group": "analyst", "admin-group": "admin"},
    "updatedAt": None,
}

_ROOT = Path(__file__).resolve().parents[3]
_RELEASE_EVIDENCE_PATH = _ROOT / "artifacts" / "release-evidence.json"
_SIGNAL_STATE_PATH = _ROOT / "artifacts" / "signal-lifecycle-state.json"


def _now() -> str:
    return datetime.now().isoformat()


def _stable_id(prefix: str, seed: str | None = None) -> str:
    if seed:
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:10]
        return f"{prefix}-{digest}"
    return f"{prefix}-{uuid4().hex[:10]}"


def _persist_signal_state() -> None:
    payload = {
        "schemaVersion": "signal-lifecycle-state.v1",
        "updatedAt": _now(),
        "signals": _signals,
        "signalVersions": _signal_versions,
        "signalReviewLinks": _signal_review_links,
        "signalValidationRuns": _signal_validation_runs,
        "signalPolicyEvents": _signal_policy_events,
    }
    _SIGNAL_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SIGNAL_STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_signal_state() -> None:
    if not _SIGNAL_STATE_PATH.exists():
        return
    try:
        payload = json.loads(_SIGNAL_STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return

    if isinstance(payload.get("signals"), dict):
        _signals.update(payload["signals"])
    if isinstance(payload.get("signalVersions"), dict):
        _signal_versions.update(payload["signalVersions"])
    if isinstance(payload.get("signalReviewLinks"), dict):
        _signal_review_links.update(payload["signalReviewLinks"])
    if isinstance(payload.get("signalValidationRuns"), dict):
        _signal_validation_runs.update(payload["signalValidationRuns"])
    if isinstance(payload.get("signalPolicyEvents"), dict):
        _signal_policy_events.update(payload["signalPolicyEvents"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "ambrosia-relay-fixture"
    messages: list[ChatMessage] = Field(default_factory=list)
    temperature: float = 0.0


class RelayEvaluateRequest(BaseModel):
    question: str = Field(min_length=3)
    documents: list[str] = Field(default_factory=list)
    benchmark: str = "financebench-open-subset"


class FeatureUpsertRequest(BaseModel):
    featureId: str | None = None
    name: str = Field(min_length=3)
    ticker: str = Field(min_length=1)
    asOf: str
    value: float
    source: str = "fixture"
    pointInTime: bool = True
    provenance: list[str] = Field(default_factory=list)


class SignalCreateRequest(BaseModel):
    signalId: str | None = None
    name: str = Field(min_length=3)
    universe: list[str] = Field(default_factory=list)
    horizon: str = "20d"
    formula: str = Field(min_length=3)
    costModel: str = "10 bps round-trip"
    benchmark: str = "SPY"
    validationGates: list[str] = Field(default_factory=lambda: ["point_in_time", "costs", "walk_forward"])


class SignalVersionCreateRequest(BaseModel):
    horizon: str | None = None
    formula: str | None = None
    universe: list[str] | None = None
    costModel: str | None = None
    benchmark: str | None = None
    validationGates: list[str] | None = None
    createdBy: str = "research"


class SignalValidateRequest(BaseModel):
    signalVersion: int | None = Field(default=None, ge=1)
    runType: str = "event_driven_backtest"
    sampleWindows: dict = Field(default_factory=lambda: {"train": "2024-01-01/2024-12-31", "validation": "2025-01-01/2025-06-30", "test": "2025-07-01/2026-01-01"})
    pointInTimeGuaranteed: bool = True
    includesCosts: bool = True
    includesSlippage: bool = True
    includesLiquidity: bool = True


class SignalPolicyTransitionRequest(BaseModel):
    signalVersion: int | None = Field(default=None, ge=1)
    actor: str = "system"
    reason: str | None = None


class BacktestRunRequest(BaseModel):
    signalId: str = Field(min_length=1)
    startDate: str = "2025-01-01"
    endDate: str = "2026-01-01"
    walkForward: bool = True
    includeCosts: bool = True
    includeSlippage: bool = True


class SignalReviewLinkRequest(BaseModel):
    reviewId: str = Field(min_length=1)
    hypothesisId: str | None = None
    signalVersion: int | None = Field(default=None, ge=1)


class SignalDecisionWritebackRequest(BaseModel):
    reviewId: str = Field(min_length=1)
    signalVersion: int | None = Field(default=None, ge=1)
    decisionState: str = Field(min_length=3)
    rationale: str | None = None
    overrideUsed: bool = False


class SignalOutcomeWritebackRequest(BaseModel):
    reviewId: str = Field(min_length=1)
    signalVersion: int | None = Field(default=None, ge=1)
    outcomeQuality: str = Field(min_length=3)
    lastReviewedAt: str | None = None


class AlphaHypothesisSignalLinkRequest(BaseModel):
    signalId: str = Field(min_length=1)
    signalVersion: int | None = Field(default=None, ge=1)


class AlphaHypothesisCreateRequest(BaseModel):
    hypothesisId: str | None = None
    title: str = Field(min_length=3)
    signalFamily: str = Field(min_length=2)
    universe: list[str] = Field(default_factory=list)
    horizon: str = "20d"
    thesis: str = Field(min_length=8)
    disconfirmingTests: list[str] = Field(default_factory=list)
    costModel: str = "10 bps round-trip"
    owner: str = "research"


class PaperTradeCreateRequest(BaseModel):
    decisionId: str = Field(min_length=1)
    ticker: str = Field(min_length=1)
    side: str = "buy"
    quantity: float = Field(gt=0)
    thesis: str = "paper decision loop"
    intendedPrice: float = Field(gt=0, default=100.0)
    stopLoss: float | None = None
    reviewDate: str = "2026-07-11"


class FillIngestRequest(BaseModel):
    paperTradeId: str = Field(min_length=1)
    fillPrice: float = Field(gt=0)
    latencyMs: int = Field(ge=0)
    venue: str = "paper-sim"


class ReplayRunRequest(BaseModel):
    ticker: str = Field(min_length=1)
    scenario: str = "spread-widening"
    latencyMs: int = Field(ge=0, default=125)


class WarmPathEventRequest(BaseModel):
    eventType: str = Field(min_length=3)
    source: str = "broker-sandbox"
    ticker: str = Field(min_length=1)
    latencyMs: int = Field(ge=0)
    notionalUsd: float = Field(gt=0)
    details: dict = Field(default_factory=dict)


class ServiceAccountCreateRequest(BaseModel):
    name: str = Field(min_length=3)
    scopes: list[str] = Field(default_factory=lambda: ["public:read"])
    expiresInDays: int = Field(default=90, ge=1, le=365)


class ServiceAccountRotateRequest(BaseModel):
    rotatedBy: str = "system"


class SSOConfigRequest(BaseModel):
    provider: str = Field(default="oidc", pattern="^(oidc|saml)$")
    issuerUrl: str = Field(min_length=5)
    audience: str = Field(min_length=2)
    defaultRole: str = "viewer"
    roleMappings: dict[str, str] = Field(default_factory=dict)


class AuditExportRequest(BaseModel):
    requestedBy: str = "admin"
    scope: str = "all"
    format: str = "jsonl"


_load_signal_state()


@router.post("/v1/chat/completions")
def openai_compatible_chat_completion(request: ChatCompletionRequest) -> dict:
    prompt = "\n".join(message.content for message in request.messages if message.role != "system")
    run = _build_relay_trace(prompt or "empty request", request.model)
    return {
        "id": _stable_id("chatcmpl", prompt),
        "object": "chat.completion",
        "created": int(datetime.now().timestamp()),
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": run["answer"],
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": len(prompt.split()), "completion_tokens": len(run["answer"].split()), "total_tokens": len(prompt.split()) + len(run["answer"].split())},
        "ambrosiaTrace": run,
    }


@router.post("/relay/evaluate")
def evaluate_relay(request: RelayEvaluateRequest) -> dict:
    run = _build_relay_trace(request.question, request.benchmark, request.documents)
    _relay_runs[run["runId"]] = run
    return run


@router.get("/relay/runs/{run_id}")
def get_relay_run(run_id: str) -> dict:
    run = _relay_runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Relay run not found")
    return run


@router.get("/relay/scorecard")
def get_relay_scorecard() -> dict:
    runs = list(_relay_runs.values())
    completed = len(runs)
    return {
        "schemaVersion": "relay-scorecard.v1",
        "runs": completed,
        "accuracy": 1.0 if completed else 0.0,
        "evidenceRecall": 1.0 if completed else 0.0,
        "calculationVerificationPassRate": 1.0 if completed else 0.0,
        "groundingPassRate": 1.0 if completed else 0.0,
        "failureClusters": [],
        "unsupportedAnswersRefused": True,
        "updatedAt": _now(),
    }


@router.post("/features", status_code=201)
def upsert_feature(request: FeatureUpsertRequest) -> dict:
    feature_id = request.featureId or _stable_id("feature", f"{request.name}:{request.ticker}:{request.asOf}")
    feature = {
        "featureId": feature_id,
        "schemaVersion": "feature.v1",
        **request.model_dump(exclude={"featureId"}),
        "createdAt": _features.get(feature_id, {}).get("createdAt", _now()),
        "updatedAt": _now(),
    }
    _features[feature_id] = feature
    return feature


@router.get("/features")
def list_features() -> list[dict]:
    return sorted(_features.values(), key=lambda item: item["updatedAt"], reverse=True)


@router.get("/features/{feature_id}")
def get_feature(feature_id: str) -> dict:
    feature = _features.get(feature_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="Feature not found")
    return feature


@router.post("/signals", status_code=201)
def create_signal(request: SignalCreateRequest) -> dict:
    signal_id = request.signalId or _stable_id("signal", request.name)
    existing = _signals.get(signal_id, {})
    active_version = int(existing.get("activeVersion", existing.get("version", 1)))
    spec_keys = ["universe", "horizon", "formula", "costModel", "benchmark", "validationGates"]
    spec_changed = bool(existing) and any(existing.get(key) != request.model_dump().get(key) for key in spec_keys)
    next_version = active_version + 1 if spec_changed else active_version
    signal = {
        "signalId": signal_id,
        "schemaVersion": "signal.v1",
        **request.model_dump(exclude={"signalId"}),
        "version": next_version,
        "activeVersion": next_version,
        "status": existing.get("status", "hypothesis"),
        "linkedHypothesisIds": existing.get("linkedHypothesisIds", []),
        "linkedReviewIds": existing.get("linkedReviewIds", []),
        "linkedReviewCount": existing.get("linkedReviewCount", 0),
        "latestDecisionState": existing.get("latestDecisionState"),
        "latestOutcomeQuality": existing.get("latestOutcomeQuality"),
        "lastReviewedAt": existing.get("lastReviewedAt"),
        "overrideCount": existing.get("overrideCount", 0),
        "outcomeCount": existing.get("outcomeCount", 0),
        "createdAt": existing.get("createdAt", _now()),
        "updatedAt": _now(),
    }
    _signals[signal_id] = signal
    versions = _signal_versions.setdefault(signal_id, [])
    version_exists = any(int(item.get("version", 0)) == next_version for item in versions)
    if not version_exists:
        versions.append(
            {
                "schemaVersion": "signal-version.v1",
                "signalId": signal_id,
                "version": next_version,
                "horizon": signal["horizon"],
                "formula": signal["formula"],
                "universe": signal["universe"],
                "costModel": signal["costModel"],
                "benchmark": signal["benchmark"],
                "validationGates": signal["validationGates"],
                "createdBy": "system",
                "createdAt": _now(),
            }
        )
    _persist_signal_state()
    return signal


@router.post("/alpha/hypotheses", status_code=201)
def create_alpha_hypothesis(request: AlphaHypothesisCreateRequest) -> dict:
    hypothesis_id = request.hypothesisId or _stable_id("alpha", f"{request.signalFamily}:{request.title}")
    hypothesis = {
        "hypothesisId": hypothesis_id,
        "schemaVersion": "alpha-hypothesis.v1",
        **request.model_dump(exclude={"hypothesisId"}),
        "quality": "D3",
        "status": "active",
        "linkedSignals": _alpha_hypotheses.get(hypothesis_id, {}).get("linkedSignals", []),
        "createdAt": _alpha_hypotheses.get(hypothesis_id, {}).get("createdAt", _now()),
        "updatedAt": _now(),
    }
    _alpha_hypotheses[hypothesis_id] = hypothesis
    return hypothesis


@router.get("/alpha/hypotheses")
def list_alpha_hypotheses() -> list[dict]:
    return sorted(_alpha_hypotheses.values(), key=lambda item: item["updatedAt"], reverse=True)


@router.get("/alpha/hypotheses/{hypothesis_id}")
def get_alpha_hypothesis(hypothesis_id: str) -> dict:
    hypothesis = _alpha_hypotheses.get(hypothesis_id)
    if hypothesis is None:
        raise HTTPException(status_code=404, detail="Alpha hypothesis not found")
    return hypothesis


@router.get("/signals")
def list_signals() -> list[dict]:
    return sorted(_signals.values(), key=lambda item: item["updatedAt"], reverse=True)


@router.get("/signals/{signal_id}")
def get_signal(signal_id: str) -> dict:
    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    return signal


def _resolve_signal_version(signal_id: str, requested: int | None) -> int:
    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    version = requested or int(signal.get("activeVersion", signal.get("version", 1)))
    versions = _signal_versions.get(signal_id, [])
    if not any(int(item.get("version", 0)) == version for item in versions):
        raise HTTPException(status_code=404, detail="Signal version not found")
    return version


def _find_signal_review_link(signal_id: str, review_id: str, signal_version: int | None = None) -> dict | None:
    candidates = [
        link
        for link in _signal_review_links.values()
        if link.get("signalId") == signal_id and link.get("reviewId") == review_id
    ]
    if signal_version is not None:
        for link in candidates:
            if int(link.get("signalVersion", 0)) == signal_version:
                return link
        return None
    if not candidates:
        return None
    candidates.sort(key=lambda item: int(item.get("signalVersion", 0)), reverse=True)
    return candidates[0]


@router.post("/signals/{signal_id}/versions", status_code=201)
def create_signal_version(signal_id: str, request: SignalVersionCreateRequest) -> dict:
    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    current_version = int(signal.get("activeVersion", signal.get("version", 1)))
    next_version = current_version + 1
    version = {
        "schemaVersion": "signal-version.v1",
        "signalId": signal_id,
        "version": next_version,
        "horizon": request.horizon or signal.get("horizon"),
        "formula": request.formula or signal.get("formula"),
        "universe": request.universe if request.universe is not None else signal.get("universe", []),
        "costModel": request.costModel or signal.get("costModel"),
        "benchmark": request.benchmark or signal.get("benchmark"),
        "validationGates": request.validationGates if request.validationGates is not None else signal.get("validationGates", []),
        "createdBy": request.createdBy,
        "createdAt": _now(),
    }
    _signal_versions.setdefault(signal_id, []).append(version)

    signal["horizon"] = version["horizon"]
    signal["formula"] = version["formula"]
    signal["universe"] = version["universe"]
    signal["costModel"] = version["costModel"]
    signal["benchmark"] = version["benchmark"]
    signal["validationGates"] = version["validationGates"]
    signal["version"] = next_version
    signal["activeVersion"] = next_version
    signal["updatedAt"] = _now()
    _persist_signal_state()
    return version


@router.get("/signals/{signal_id}/versions")
def list_signal_versions(signal_id: str) -> list[dict]:
    if signal_id not in _signals:
        raise HTTPException(status_code=404, detail="Signal not found")
    versions = _signal_versions.get(signal_id, [])
    return sorted(versions, key=lambda item: int(item.get("version", 0)), reverse=True)


@router.get("/signals/{signal_id}/versions/{version}")
def get_signal_version(signal_id: str, version: int) -> dict:
    if signal_id not in _signals:
        raise HTTPException(status_code=404, detail="Signal not found")
    for item in _signal_versions.get(signal_id, []):
        if int(item.get("version", 0)) == version:
            return item
    raise HTTPException(status_code=404, detail="Signal version not found")


def _signal_links(signal_id: str) -> list[dict]:
    return [link for link in _signal_review_links.values() if link.get("signalId") == signal_id]


def _signal_validation_runs_for(signal_id: str) -> list[dict]:
    return _signal_validation_runs.get(signal_id, [])


def _signal_latest_validation(signal_id: str, signal_version: int | None = None) -> dict | None:
    runs = _signal_validation_runs_for(signal_id)
    if signal_version is not None:
        runs = [run for run in runs if int(run.get("signalVersion", 0)) == signal_version]
    if not runs:
        return None
    return sorted(runs, key=lambda item: item.get("completedAt", ""), reverse=True)[0]


def _append_signal_policy_event(signal_id: str, event_type: str, to_status: str, actor: str, reason: str | None, signal_version: int | None = None) -> dict:
    event = {
        "eventId": _stable_id("signal-policy", f"{signal_id}:{event_type}:{to_status}:{actor}:{len(_signal_policy_events.get(signal_id, []))}"),
        "schemaVersion": "signal-policy-event.v1",
        "signalId": signal_id,
        "signalVersion": signal_version,
        "eventType": event_type,
        "toStatus": to_status,
        "actor": actor,
        "reason": reason,
        "createdAt": _now(),
    }
    _signal_policy_events.setdefault(signal_id, []).append(event)
    return event


def _required_validation_gates_present(signal: dict) -> tuple[bool, list[str]]:
    required = {"point_in_time", "costs", "walk_forward"}
    gates = set(signal.get("validationGates", []))
    missing = sorted(required - gates)
    return len(missing) == 0, missing


def _signal_rollup(signal_id: str) -> dict:
    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    links = _signal_links(signal_id)
    pursued_count = sum(1 for link in links if link.get("reviewDecisionState") == "pursue")
    rejected_count = sum(1 for link in links if link.get("reviewDecisionState") == "reject")
    needs_more_data_count = sum(1 for link in links if link.get("reviewDecisionState") == "needs_more_data")
    override_count = sum(1 for link in links if link.get("overrideUsed") is True)
    outcome_count = sum(1 for link in links if bool(link.get("outcomeQuality")))
    latest_outcome = max((link.get("lastOutcomeAt") for link in links if link.get("lastOutcomeAt")), default=None)
    latest_reviewed = max((link.get("lastReviewedAt") for link in links if link.get("lastReviewedAt")), default=signal.get("lastReviewedAt"))

    return {
        "schemaVersion": "signal-outcome-rollup.v1",
        "signalId": signal_id,
        "signalVersion": signal.get("version", 1),
        "linkedDecisionCount": len(links),
        "pursuedCount": pursued_count,
        "rejectedCount": rejected_count,
        "needsMoreDataCount": needs_more_data_count,
        "overrideCount": override_count,
        "outcomeCount": outcome_count,
        "latestDecisionState": signal.get("latestDecisionState"),
        "latestOutcomeQuality": signal.get("latestOutcomeQuality"),
        "status": signal.get("status", "hypothesis"),
        "activeVersion": signal.get("activeVersion", signal.get("version", 1)),
        "latestValidationStatus": (_signal_latest_validation(signal_id) or {}).get("status"),
        "lastReviewedAt": latest_reviewed,
        "lastOutcomeAt": latest_outcome,
        "updatedAt": _now(),
    }


@router.post("/signals/{signal_id}/validate")
def validate_signal(signal_id: str, request: SignalValidateRequest) -> dict:
    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    signal_version = _resolve_signal_version(signal_id, request.signalVersion)
    hygiene_issues: list[str] = []
    if not request.pointInTimeGuaranteed:
        hygiene_issues.append("missing_point_in_time_guarantee")
    if not request.includesCosts:
        hygiene_issues.append("missing_transaction_costs")
    if not request.includesSlippage:
        hygiene_issues.append("missing_slippage_model")
    if not request.includesLiquidity:
        hygiene_issues.append("missing_liquidity_model")

    has_required_gates, missing_gates = _required_validation_gates_present(signal)
    if not has_required_gates:
        hygiene_issues.extend([f"missing_validation_gate:{gate}" for gate in missing_gates])

    status = "passed" if len(hygiene_issues) == 0 else "failed"
    run = {
        "validationRunId": _stable_id("signal-validation", f"{signal_id}:{signal_version}:{len(_signal_validation_runs_for(signal_id))}"),
        "schemaVersion": "signal-validation-run.v1",
        "signalId": signal_id,
        "signalVersion": signal_version,
        "runType": request.runType,
        "sampleWindows": request.sampleWindows,
        "pointInTimeGuaranteed": request.pointInTimeGuaranteed,
        "includesCosts": request.includesCosts,
        "includesSlippage": request.includesSlippage,
        "includesLiquidity": request.includesLiquidity,
        "benchmarkComparison": {"benchmark": signal.get("benchmark"), "activeReturn": 0.039},
        "hygieneIssues": hygiene_issues,
        "metrics": {
            "sharpeRatio": 1.21,
            "maxDrawdown": -0.082,
            "hitRate": 0.57,
            "implementationShortfallBps": 10.6,
        },
        "artifactRefs": [f"artifacts/signals/{signal_id}/validation/{signal_version}"],
        "status": status,
        "completedAt": _now(),
    }
    _signal_validation_runs.setdefault(signal_id, []).append(run)

    signal["updatedAt"] = _now()
    signal["status"] = "validation_passed" if status == "passed" else "validation_pending"

    _append_signal_policy_event(
        signal_id=signal_id,
        event_type="validation.completed",
        to_status=signal["status"],
        actor="system",
        reason="Validation run completed",
        signal_version=signal_version,
    )
    _persist_signal_state()
    return run


@router.get("/signals/{signal_id}/validation-runs")
def list_signal_validation_runs(signal_id: str) -> list[dict]:
    if signal_id not in _signals:
        raise HTTPException(status_code=404, detail="Signal not found")
    runs = _signal_validation_runs_for(signal_id)
    return sorted(runs, key=lambda item: item.get("completedAt", ""), reverse=True)


@router.post("/signals/{signal_id}/promote")
def promote_signal(signal_id: str, request: SignalPolicyTransitionRequest) -> dict:
    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    signal_version = _resolve_signal_version(signal_id, request.signalVersion)
    latest_validation = _signal_latest_validation(signal_id, signal_version)
    if latest_validation is None:
        raise HTTPException(status_code=409, detail="Promotion blocked: missing validation run for signal version")
    if latest_validation.get("status") != "passed":
        raise HTTPException(status_code=409, detail="Promotion blocked: validation status is not passed")

    signal["status"] = "active_candidate"
    signal["updatedAt"] = _now()
    event = _append_signal_policy_event(
        signal_id=signal_id,
        event_type="signal.promoted",
        to_status="active_candidate",
        actor=request.actor,
        reason=request.reason,
        signal_version=signal_version,
    )
    _persist_signal_state()
    return {
        "schemaVersion": "signal-policy-transition.v1",
        "signalId": signal_id,
        "signalVersion": signal_version,
        "status": signal["status"],
        "event": event,
    }


@router.post("/signals/{signal_id}/constrain")
def constrain_signal(signal_id: str, request: SignalPolicyTransitionRequest) -> dict:
    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    signal_version = _resolve_signal_version(signal_id, request.signalVersion)
    signal["status"] = "constrained"
    signal["updatedAt"] = _now()
    event = _append_signal_policy_event(
        signal_id=signal_id,
        event_type="signal.constrained",
        to_status="constrained",
        actor=request.actor,
        reason=request.reason or "manual constraint",
        signal_version=signal_version,
    )
    _persist_signal_state()
    return {
        "schemaVersion": "signal-policy-transition.v1",
        "signalId": signal_id,
        "signalVersion": signal_version,
        "status": signal["status"],
        "event": event,
    }


@router.post("/signals/{signal_id}/retire")
def retire_signal(signal_id: str, request: SignalPolicyTransitionRequest) -> dict:
    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    signal_version = _resolve_signal_version(signal_id, request.signalVersion)
    signal["status"] = "retired"
    signal["updatedAt"] = _now()
    event = _append_signal_policy_event(
        signal_id=signal_id,
        event_type="signal.retired",
        to_status="retired",
        actor=request.actor,
        reason=request.reason or "manual retirement",
        signal_version=signal_version,
    )
    _persist_signal_state()
    return {
        "schemaVersion": "signal-policy-transition.v1",
        "signalId": signal_id,
        "signalVersion": signal_version,
        "status": signal["status"],
        "event": event,
    }


@router.get("/signals/{signal_id}/policy-events")
def list_signal_policy_events(signal_id: str) -> list[dict]:
    if signal_id not in _signals:
        raise HTTPException(status_code=404, detail="Signal not found")
    events = _signal_policy_events.get(signal_id, [])
    return sorted(events, key=lambda item: item.get("createdAt", ""), reverse=True)


@router.get("/signals/program-metrics")
def get_signal_program_metrics() -> dict:
    total_signals = len(_signals)
    total_links = len(_signal_review_links)
    linked_signals = sum(1 for signal in _signals.values() if int(signal.get("linkedReviewCount", 0)) > 0)
    validated_signals = sum(1 for signal in _signals.values() if signal.get("status") in {"validation_passed", "active_candidate", "constrained", "retired"})
    promoted_signals = sum(1 for signal in _signals.values() if signal.get("status") == "active_candidate")
    constrained_signals = sum(1 for signal in _signals.values() if signal.get("status") == "constrained")
    retired_signals = sum(1 for signal in _signals.values() if signal.get("status") == "retired")
    outcome_rollups = [_signal_rollup(signal_id) for signal_id in _signals.keys()]
    pursued_total = sum(int(item.get("pursuedCount", 0)) for item in outcome_rollups)
    rejected_total = sum(int(item.get("rejectedCount", 0)) for item in outcome_rollups)
    outcome_total = sum(int(item.get("outcomeCount", 0)) for item in outcome_rollups)

    return {
        "schemaVersion": "signals-program-metrics.v1",
        "totalSignals": total_signals,
        "linkedSignals": linked_signals,
        "linkedSignalsPct": round((linked_signals / total_signals) * 100, 1) if total_signals else 0.0,
        "totalDecisionLinks": total_links,
        "validatedSignals": validated_signals,
        "validatedSignalsPct": round((validated_signals / total_signals) * 100, 1) if total_signals else 0.0,
        "promotedSignals": promoted_signals,
        "constrainedSignals": constrained_signals,
        "retiredSignals": retired_signals,
        "pursuedDecisions": pursued_total,
        "rejectedDecisions": rejected_total,
        "recordedOutcomes": outcome_total,
        "updatedAt": _now(),
    }


@router.post("/signals/{signal_id}/link-review", status_code=201)
def link_signal_review(signal_id: str, request: SignalReviewLinkRequest) -> dict:
    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    signal_version = _resolve_signal_version(signal_id, request.signalVersion)
    key = f"{signal_id}:{signal_version}:{request.reviewId}"
    link_id = _stable_id("signal-review-link", key)
    existing = _signal_review_links.get(link_id)
    linked_at = existing.get("linkedAt") if existing else _now()

    link = {
        "linkId": link_id,
        "schemaVersion": "signal-review-link.v1",
        "signalId": signal_id,
        "signalVersion": signal_version,
        "hypothesisId": request.hypothesisId,
        "reviewId": request.reviewId,
        "reviewDecisionState": existing.get("reviewDecisionState") if existing else None,
        "overrideUsed": existing.get("overrideUsed", False) if existing else False,
        "overrideRationale": existing.get("overrideRationale") if existing else None,
        "outcomeQuality": existing.get("outcomeQuality") if existing else None,
        "linkedAt": linked_at,
        "lastReviewedAt": existing.get("lastReviewedAt") if existing else None,
        "lastOutcomeAt": existing.get("lastOutcomeAt") if existing else None,
        "updatedAt": _now(),
    }
    _signal_review_links[link_id] = link

    linked_ids = list(dict.fromkeys([*signal.get("linkedReviewIds", []), request.reviewId]))
    signal["linkedReviewIds"] = linked_ids
    signal["linkedReviewCount"] = len(linked_ids)
    signal["lastReviewedAt"] = signal.get("lastReviewedAt") or linked_at
    signal["updatedAt"] = _now()
    _persist_signal_state()
    return link


@router.get("/signals/{signal_id}/decision-links")
def get_signal_decision_links(signal_id: str) -> list[dict]:
    if signal_id not in _signals:
        raise HTTPException(status_code=404, detail="Signal not found")
    links = _signal_links(signal_id)
    return sorted(links, key=lambda link: link.get("updatedAt", ""), reverse=True)


@router.post("/signals/{signal_id}/writeback-decision")
def writeback_signal_decision(signal_id: str, request: SignalDecisionWritebackRequest) -> dict:
    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    signal_version = _resolve_signal_version(signal_id, request.signalVersion)
    existing = _find_signal_review_link(signal_id, request.reviewId, signal_version)
    if existing is None:
        raise HTTPException(status_code=404, detail="Signal review link not found")

    was_override = existing.get("overrideUsed") is True
    is_override = request.overrideUsed is True

    existing["reviewDecisionState"] = request.decisionState
    existing["overrideUsed"] = is_override
    existing["overrideRationale"] = request.rationale
    existing["lastReviewedAt"] = _now()
    existing["updatedAt"] = _now()

    signal["latestDecisionState"] = request.decisionState
    signal["lastReviewedAt"] = existing["lastReviewedAt"]
    if is_override and not was_override:
        signal["overrideCount"] = int(signal.get("overrideCount", 0)) + 1
    signal["updatedAt"] = _now()
    _persist_signal_state()

    return {
        "schemaVersion": "signal-writeback-decision.v1",
        "signalId": signal_id,
        "reviewId": request.reviewId,
        "latestDecisionState": signal["latestDecisionState"],
        "overrideCount": signal.get("overrideCount", 0),
        "lastReviewedAt": signal.get("lastReviewedAt"),
    }


@router.post("/signals/{signal_id}/writeback-outcome")
def writeback_signal_outcome(signal_id: str, request: SignalOutcomeWritebackRequest) -> dict:
    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    signal_version = _resolve_signal_version(signal_id, request.signalVersion)
    existing = _find_signal_review_link(signal_id, request.reviewId, signal_version)
    if existing is None:
        raise HTTPException(status_code=404, detail="Signal review link not found")

    timestamp = request.lastReviewedAt or _now()
    already_counted = bool(existing.get("outcomeQuality"))
    existing["outcomeQuality"] = request.outcomeQuality
    existing["lastReviewedAt"] = timestamp
    existing["lastOutcomeAt"] = timestamp
    existing["updatedAt"] = _now()

    signal["latestOutcomeQuality"] = request.outcomeQuality
    signal["lastReviewedAt"] = timestamp
    if not already_counted:
        signal["outcomeCount"] = int(signal.get("outcomeCount", 0)) + 1
    signal["updatedAt"] = _now()
    _persist_signal_state()

    return _signal_rollup(signal_id)


@router.get("/signals/{signal_id}/outcome-rollup")
def get_signal_outcome_rollup(signal_id: str) -> dict:
    return _signal_rollup(signal_id)


@router.post("/alpha/hypotheses/{hypothesis_id}/link-signal")
def link_alpha_hypothesis_signal(hypothesis_id: str, request: AlphaHypothesisSignalLinkRequest) -> dict:
    hypothesis = _alpha_hypotheses.get(hypothesis_id)
    if hypothesis is None:
        raise HTTPException(status_code=404, detail="Alpha hypothesis not found")
    signal = _signals.get(request.signalId)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    signal_version = _resolve_signal_version(request.signalId, request.signalVersion)
    links = hypothesis.get("linkedSignals", [])
    entry = {
        "signalId": request.signalId,
        "signalVersion": signal_version,
        "linkedAt": _now(),
    }
    exists = any(
        item.get("signalId") == request.signalId and int(item.get("signalVersion", 0)) == signal_version
        for item in links
    )
    if not exists:
        links.append(entry)
    hypothesis["linkedSignals"] = links
    hypothesis["updatedAt"] = _now()

    linked_hypotheses = list(dict.fromkeys([*signal.get("linkedHypothesisIds", []), hypothesis_id]))
    signal["linkedHypothesisIds"] = linked_hypotheses
    signal["updatedAt"] = _now()
    _persist_signal_state()
    return {
        "schemaVersion": "alpha-hypothesis-signal-link.v1",
        "hypothesisId": hypothesis_id,
        "signalId": request.signalId,
        "signalVersion": signal_version,
        "linkedSignals": links,
    }


@router.get("/alpha/hypotheses/{hypothesis_id}/signals")
def list_alpha_hypothesis_signals(hypothesis_id: str) -> list[dict]:
    hypothesis = _alpha_hypotheses.get(hypothesis_id)
    if hypothesis is None:
        raise HTTPException(status_code=404, detail="Alpha hypothesis not found")

    results: list[dict] = []
    for link in hypothesis.get("linkedSignals", []):
        signal_id = link.get("signalId")
        if not signal_id or signal_id not in _signals:
            continue
        signal = _signals[signal_id]
        results.append(
            {
                "signalId": signal_id,
                "name": signal.get("name"),
                "status": signal.get("status"),
                "activeVersion": signal.get("activeVersion", signal.get("version", 1)),
                "linkedVersion": link.get("signalVersion"),
                "linkedAt": link.get("linkedAt"),
            }
        )
    return results


@router.get("/signals/{signal_id}/alpha-context")
def get_signal_alpha_context(signal_id: str) -> dict:
    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    linked_hypotheses = signal.get("linkedHypothesisIds", [])
    hypotheses = []
    for hypothesis_id in linked_hypotheses:
        hypothesis = _alpha_hypotheses.get(hypothesis_id)
        if hypothesis:
            hypotheses.append(
                {
                    "hypothesisId": hypothesis_id,
                    "title": hypothesis.get("title"),
                    "signalFamily": hypothesis.get("signalFamily"),
                    "status": hypothesis.get("status"),
                    "updatedAt": hypothesis.get("updatedAt"),
                }
            )

    return {
        "schemaVersion": "signal-alpha-context.v1",
        "signal": signal,
        "signalVersions": _signal_versions.get(signal_id, []),
        "validationRuns": _signal_validation_runs_for(signal_id),
        "policyEvents": _signal_policy_events.get(signal_id, []),
        "linkedHypotheses": hypotheses,
        "outcomeRollup": _signal_rollup(signal_id),
        "updatedAt": _now(),
    }


@router.post("/backtests/run")
def run_backtest(request: BacktestRunRequest) -> dict:
    signal = _signals.get(request.signalId)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    backtest_id = _stable_id("backtest", f"{request.signalId}:{request.startDate}:{request.endDate}")
    hygiene = []
    if not request.walkForward:
        hygiene.append("missing_walk_forward_validation")
    if not request.includeCosts:
        hygiene.append("missing_transaction_costs")
    if not request.includeSlippage:
        hygiene.append("missing_slippage_model")
    result = {
        "backtestId": backtest_id,
        "schemaVersion": "backtest-result.v1",
        "signalId": request.signalId,
        "status": "alpha_candidate" if not hygiene else "hypothesis_only",
        "samplePeriod": f"{request.startDate}/{request.endDate}",
        "metrics": {
            "totalReturn": 0.118,
            "excessReturn": 0.041,
            "activeReturn": 0.039,
            "annualizedReturn": 0.109,
            "volatility": 0.091,
            "sharpeRatio": 1.21,
            "sortinoRatio": 1.63,
            "calmarRatio": 1.32,
            "maxDrawdown": -0.082,
            "profitFactor": 1.36,
            "hitRate": 0.57,
            "informationCoefficient": 0.11,
            "rankInformationCoefficient": 0.09,
            "informationRatio": 0.72,
            "signalDecayCurve": [0.12, 0.09, 0.05, 0.02],
            "turnover": 1.7,
            "capacityUsdMillions": 42.0,
            "betaExposure": 0.84,
            "factorExposure": {"value": 0.19, "momentum": 0.27, "quality": 0.11, "size": -0.06},
            "sectorExposure": {"technology": 0.41, "industrials": 0.18, "healthcare": 0.12},
            "spreadCostBps": 6.4,
            "slippageBps": 4.2,
            "implementationShortfallBps": 10.6,
        },
        "benchmark": signal["benchmark"],
        "hygieneIssues": hygiene,
        "disconfirmingTests": ["underperforms after costs in high-spread regime"],
        "createdAt": _now(),
    }
    _backtests[backtest_id] = result

    signal_version = int(signal.get("activeVersion", signal.get("version", 1)))
    validation_run = {
        "validationRunId": _stable_id("signal-validation", backtest_id),
        "schemaVersion": "signal-validation-run.v1",
        "signalId": request.signalId,
        "signalVersion": signal_version,
        "runType": "event_driven_backtest",
        "sampleWindows": {"train": request.startDate, "test": request.endDate},
        "pointInTimeGuaranteed": True,
        "includesCosts": request.includeCosts,
        "includesSlippage": request.includeSlippage,
        "includesLiquidity": True,
        "benchmarkComparison": {"benchmark": signal.get("benchmark"), "activeReturn": result["metrics"]["activeReturn"]},
        "hygieneIssues": hygiene,
        "metrics": result["metrics"],
        "artifactRefs": [f"backtests/{backtest_id}"],
        "status": "passed" if not hygiene else "failed",
        "completedAt": _now(),
    }
    _signal_validation_runs.setdefault(request.signalId, []).append(validation_run)
    signal["status"] = "validation_passed" if not hygiene else "validation_pending"
    signal["updatedAt"] = _now()
    _append_signal_policy_event(
        signal_id=request.signalId,
        event_type="backtest.completed",
        to_status=signal["status"],
        actor="system",
        reason="Backtest run updated validation posture",
        signal_version=signal_version,
    )
    _persist_signal_state()
    return result


@router.get("/backtests/{backtest_id}")
def get_backtest(backtest_id: str) -> dict:
    backtest = _backtests.get(backtest_id)
    if backtest is None:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return backtest


@router.post("/paper-trades", status_code=201)
def create_paper_trade(request: PaperTradeCreateRequest) -> dict:
    trade_id = _stable_id("paper-trade", f"{request.decisionId}:{request.ticker}:{request.reviewDate}")
    trade = {
        "paperTradeId": trade_id,
        "schemaVersion": "paper-trade.v1",
        **request.model_dump(),
        "status": "open",
        "riskControls": ["paper_only", "human_review_required", "no_live_broker_credentials"],
        "outcomePlan": {"reviewDate": request.reviewDate, "qualityTarget": "O3"},
        "createdAt": _paper_trades.get(trade_id, {}).get("createdAt", _now()),
        "updatedAt": _now(),
    }
    _paper_trades[trade_id] = trade
    return trade


@router.get("/paper-trades")
def list_paper_trades() -> list[dict]:
    return sorted(_paper_trades.values(), key=lambda item: item["updatedAt"], reverse=True)


@router.post("/execution/fills", status_code=201)
def ingest_execution_fill(request: FillIngestRequest) -> dict:
    trade = _paper_trades.get(request.paperTradeId)
    if trade is None:
        raise HTTPException(status_code=404, detail="Paper trade not found")
    shortfall = round(((request.fillPrice - trade["intendedPrice"]) / trade["intendedPrice"]) * 10000, 2)
    fill_id = _stable_id("fill", f"{request.paperTradeId}:{request.fillPrice}:{request.latencyMs}")
    fill = {
        "fillId": fill_id,
        "schemaVersion": "execution-fill.v1",
        **request.model_dump(),
        "ticker": trade["ticker"],
        "side": trade["side"],
        "quantity": trade["quantity"],
        "implementationShortfallBps": shortfall,
        "latencyFitness": "warm_path_ok" if request.latencyMs <= 1000 else "manual_review_required",
        "attribution": {"priceMovement": shortfall * 0.4, "spread": shortfall * 0.3, "timing": shortfall * 0.3},
        "createdAt": _now(),
    }
    _fills[fill_id] = fill
    return fill


@router.post("/execution/market-replay")
def run_market_replay(request: ReplayRunRequest) -> dict:
    replay_id = _stable_id("replay", f"{request.ticker}:{request.scenario}:{request.latencyMs}")
    replay = {
        "replayId": replay_id,
        "schemaVersion": "market-replay.v1",
        **request.model_dump(),
        "result": "accepted" if request.latencyMs <= 1000 else "downgraded",
        "killCriteria": ["reject if latency exceeds edge half-life", "reject if spread cost exceeds expected edge"],
        "createdAt": _now(),
    }
    _market_replays[replay_id] = replay
    return replay


@router.post("/execution/warm-path/events", status_code=201)
def ingest_warm_path_event(request: WarmPathEventRequest) -> dict:
    risk_checks = {
        "size_limit": request.notionalUsd <= 250000.0,
        "latency_limit": request.latencyMs <= 1000,
        "kill_switch": request.details.get("killSwitchTriggered", False) is False,
    }
    accepted = all(risk_checks.values())
    event = {
        "eventId": _stable_id("warm-event", f"{request.eventType}:{request.ticker}:{request.latencyMs}:{len(_warm_path_events)}"),
        "schemaVersion": "warm-path-event.v1",
        **request.model_dump(),
        "riskChecks": risk_checks,
        "accepted": accepted,
        "result": "processed" if accepted else "rejected",
        "createdAt": _now(),
    }
    _warm_path_events.append(event)
    return event


@router.get("/execution/warm-path/events")
def list_warm_path_events() -> list[dict]:
    return list(reversed(_warm_path_events[-100:]))


@router.get("/signals/{signal_id}/alpha-decay")
def get_alpha_decay(signal_id: str) -> dict:
    if signal_id not in _signals:
        raise HTTPException(status_code=404, detail="Signal not found")
    rolling_ic = [0.12, 0.1, 0.06, 0.03, 0.01]
    rolling_sharpe = [1.3, 1.2, 0.95, 0.72, 0.44]
    rolling_hit_rate = [0.58, 0.56, 0.53, 0.49, 0.46]
    decay_detected = rolling_ic[-1] < 0.03 or rolling_sharpe[-1] < 0.6
    return {
        "schemaVersion": "alpha-decay.v1",
        "signalId": signal_id,
        "rollingIC": rolling_ic,
        "rollingSharpe": rolling_sharpe,
        "rollingHitRate": rolling_hit_rate,
        "spreadCostTrendBps": [5.8, 6.1, 6.9, 7.4, 8.2],
        "slippageTrendBps": [3.2, 3.9, 4.8, 5.2, 6.0],
        "capacityTrendUsdMillions": [58, 54, 49, 45, 39],
        "regimePerformance": {
            "risk_on": 0.09,
            "risk_off": -0.02,
            "high_volatility": -0.04,
        },
        "decayDetected": decay_detected,
        "recommendedAction": "downgrade_or_recalibrate" if decay_detected else "keep_active",
        "createdAt": _now(),
    }


@router.get("/execution/warm-path/status")
def get_warm_path_status() -> dict:
    return {
        "schemaVersion": "warm-path-status.v1",
        "status": "designed",
        "latencyTarget": "milliseconds-to-seconds",
        "llmInLiveOrderLoop": False,
        "localRiskChecks": ["size_limit", "price_collar", "kill_switch"],
        "brokerAutomation": "paper_or_broker_supervised_only",
    }


@router.post("/enterprise/service-accounts", status_code=201)
def create_service_account(request: ServiceAccountCreateRequest) -> dict:
    service_account_id = _stable_id("svc", request.name)
    token_fingerprint = hashlib.sha256(f"{request.name}:{request.scopes}".encode("utf-8")).hexdigest()[:16]
    now = datetime.now()
    expires_at = (now + timedelta(days=request.expiresInDays)).isoformat()
    account = {
        "serviceAccountId": service_account_id,
        "schemaVersion": "service-account.v1",
        **request.model_dump(),
        "status": "active",
        "tokenFingerprint": token_fingerprint,
        "createdAt": _service_accounts.get(service_account_id, {}).get("createdAt", now.isoformat()),
        "expiresAt": expires_at,
        "lastRotatedAt": now.isoformat(),
        "rotationIntervalDays": 30,
        "updatedAt": _now(),
    }
    _service_accounts[service_account_id] = account
    return account


@router.get("/enterprise/service-accounts")
def list_service_accounts() -> list[dict]:
    return sorted(_service_accounts.values(), key=lambda item: item["updatedAt"], reverse=True)


@router.post("/enterprise/service-accounts/{service_account_id}/rotate")
def rotate_service_account_token(service_account_id: str, request: ServiceAccountRotateRequest) -> dict:
    account = _service_accounts.get(service_account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Service account not found")
    account["tokenFingerprint"] = hashlib.sha256(f"{service_account_id}:{uuid4().hex}".encode("utf-8")).hexdigest()[:16]
    account["lastRotatedAt"] = _now()
    account["updatedAt"] = _now()
    account["rotatedBy"] = request.rotatedBy
    account["lifecycle"] = {
        "requiresRotation": False,
        "rotationIntervalDays": account.get("rotationIntervalDays", 30),
        "revocable": True,
    }
    return account


@router.post("/enterprise/service-accounts/{service_account_id}/revoke")
def revoke_service_account(service_account_id: str) -> dict:
    account = _service_accounts.get(service_account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Service account not found")
    account["status"] = "revoked"
    account["revokedAt"] = _now()
    account["updatedAt"] = _now()
    return account


@router.post("/enterprise/audit-exports")
def create_audit_export(request: AuditExportRequest) -> dict:
    export_id = _stable_id("audit-export", f"{request.requestedBy}:{request.scope}:{request.format}:{len(_audit_exports)}")
    export = {
        "exportJobId": export_id,
        "schemaVersion": "audit-export.v1",
        **request.model_dump(),
        "status": "completed",
        "downloadUrl": f"/enterprise/audit-exports/{export_id}/download",
        "columns": ["timestamp", "actor", "action", "resource", "scope", "result"],
        "createdAt": _now(),
        "completedAt": _now(),
    }
    _audit_exports[export_id] = export
    return export


@router.post("/enterprise/sso/config")
def configure_sso(request: SSOConfigRequest) -> dict:
    _sso_config.update(
        {
            "enabled": True,
            **request.model_dump(),
            "updatedAt": _now(),
        }
    )
    return {"schemaVersion": "enterprise-sso-config.v1", **_sso_config}


@router.get("/enterprise/sso/config")
def get_sso_config() -> dict:
    return {"schemaVersion": "enterprise-sso-config.v1", **_sso_config}


@router.get("/enterprise/deployment-bundles/offline")
def get_offline_bundle_manifest() -> dict:
    return {
        "schemaVersion": "enterprise-offline-bundle.v1",
        "bundleVersion": "0.1.0",
        "deliveryModes": ["private-registry", "air-gapped-offline"],
        "components": ["ambrosia-api", "ambrosia-web", "ambrosia-cli", "ambrosia-sdk"],
        "integrity": {
            "checksumManifest": "artifacts/release-checksums.sha256",
            "signature": "sigstore-cosign",
        },
        "documentation": [
            "docs/roadmap/index85-evidence-matrix.md",
            "artifacts/release-evidence.json",
        ],
    }


@router.get("/enterprise/readiness")
def get_enterprise_readiness() -> dict:
    package_provenance = {
        "checksums": True,
        "dockerCliImagePlan": True,
        "signedBinaryPlan": True,
        "semverPolicy": "0.x pre-release",
        "source": "plan",
    }
    if _RELEASE_EVIDENCE_PATH.exists():
        try:
            release_evidence = json.loads(_RELEASE_EVIDENCE_PATH.read_text(encoding="utf-8"))
            package_provenance = {
                "checksums": bool(release_evidence.get("provenance", {}).get("checksums")),
                "dockerCliImage": release_evidence.get("provenance", {}).get("dockerImage"),
                "signature": release_evidence.get("provenance", {}).get("signature"),
                "semverPolicy": release_evidence.get("release", {}).get("semverPolicy", "0.x pre-release"),
                "source": "release-evidence",
            }
        except json.JSONDecodeError:
            package_provenance["source"] = "invalid-release-evidence"

    return {
        "schemaVersion": "enterprise-readiness.v1",
        "tiers": ["Developer", "Team", "Enterprise"],
        "scopes": ["public:read", "advanced:read", "team:write", "admin:write"],
        "serviceAccounts": len(_service_accounts),
        "auditExports": len(_audit_exports),
        "sso": {"enabled": _sso_config["enabled"], "provider": _sso_config["provider"], "roleMappings": _sso_config["roleMappings"]},
        "privateDeployment": {"databaseRequired": True, "privateApiUrlSupported": True, "customerManagedDatabase": True},
        "packageProvenance": package_provenance,
    }


@router.get("/enterprise/support/security-packet")
def get_enterprise_security_packet() -> dict:
    return {
        "schemaVersion": "enterprise-security-packet.v1",
        "retentionPolicy": {
            "auditDays": 365,
            "benchmarkTraceDays": 180,
            "decisionMemoryDays": 730,
        },
        "supportPolicy": {
            "sla": "P1 1h response, P2 4h response",
            "channels": ["ticket", "email"],
            "coverage": "business-hours-plus-critical-oncall",
        },
        "securityReview": {
            "tokenRotation": "30 days",
            "leastPrivilegeScopes": True,
            "auditExportAvailable": True,
            "customerManagedDatabase": True,
            "privateDeploymentProfile": True,
        },
        "createdAt": _now(),
    }


def _build_relay_trace(question: str, benchmark: str, documents: list[str] | None = None) -> dict:
    evidence = documents or ["fixture annual report excerpt", "fixture calculation table"]
    answer = "Evidence-backed answer generated with retrieved evidence, calculation verification, and grounding checks."
    run_id = _stable_id("relay-run", f"{benchmark}:{question}:{len(_relay_runs)}")
    return {
        "runId": run_id,
        "schemaVersion": "benchmark-trace.v1",
        "benchmark": benchmark,
        "question": question,
        "answer": answer,
        "route": "retrieval_numeric_qa",
        "retrievalEvents": [{"source": source, "score": 0.92 - index * 0.04} for index, source in enumerate(evidence)],
        "tableExtractions": [{"tableId": "fixture-table-1", "unit": "USD", "confidence": 0.94}],
        "calculations": [{"expression": "100 * (1.18 - 1)", "result": 18.0, "verified": True}],
        "verification": {"status": "passed", "calculationVerifier": "deterministic-fixture"},
        "grounding": {"status": "passed", "unsupportedClaims": []},
        "abstention": {"required": False, "reason": None},
        "cost": {"usd": 0.0, "mode": "fixture"},
        "latencyMs": 42,
        "createdAt": _now(),
    }