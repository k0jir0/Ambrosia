from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.llm_catalog import WorkerCapabilities


WORKER_PATH = (
    Path(__file__).resolve().parents[3] / "packages" / "local-worker" / "ambrosia_local_worker.py"
)
SPEC = importlib.util.spec_from_file_location("ambrosia_local_worker", WORKER_PATH)
assert SPEC and SPEC.loader
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


def _specialist_output() -> dict:
    return {
        "schemaVersion": "specialist-output.v2",
        "role": "bear",
        "instructionReferences": ["I1", "I2", "I3", "I4"],
        "materialClaims": [],
        "calculationIntents": [],
        "missingEvidence": ["Independent evidence"],
        "falsifiableConditions": ["Measure against a predefined benchmark"],
        "alternativeHypotheses": ["The observation is temporary"],
        "roleConclusion": "The supplied evidence is insufficient.",
        "confidence": {
            "direction": "insufficient",
            "evidenceStrength": 0.1,
            "modelUncertainty": 0.9,
            "coverage": 0.2,
            "materiality": "medium",
        },
        "abstained": True,
        "abstentionReason": "Insufficient evidence",
    }


def test_run_stage_allocates_the_context_it_advertises(monkeypatch) -> None:
    captured = {}

    def fake_request(_url, **kwargs):
        captured.update(kwargs["body"])
        return {
            "done": True,
            "done_reason": "stop",
            "response": '{"summary":"bounded"}',
        }

    monkeypatch.setenv("OLLAMA_CONTEXT_LENGTH", "4096")
    monkeypatch.setattr(worker, "request_json", fake_request)

    output, metadata = worker.run_stage(
        "http://127.0.0.1:11434",
        "qwen3:8b-q4_K_M",
        "Return bounded JSON.",
        {"type": "object", "required": ["summary"], "properties": {"summary": {"type": "string"}}},
    )

    assert output["summary"] == "bounded"
    assert captured["options"]["num_ctx"] == 4096
    assert metadata["parameters"]["contextLength"] == 4096


def test_hardware_preflight_exercises_all_four_model_stages(monkeypatch) -> None:
    calls = []

    def fake_stage(_url, _model, _text, schema):
        calls.append(schema)
        output = {"findings": []} if schema is worker.VERIFIER_SCHEMA else _specialist_output()
        return output, {"totalDurationNs": 10}

    monkeypatch.setenv("OLLAMA_CONTEXT_LENGTH", "8192")
    monkeypatch.setattr(worker, "model_metadata", lambda *_: ("sha256:qualified", "0.32.9"))
    monkeypatch.setattr(worker, "run_stage", fake_stage)
    monkeypatch.setattr(
        worker,
        "loaded_model_state",
        lambda *_: {
            "contextLength": 8192,
            "sizeBytes": 5_200_000_000,
            "sizeVramBytes": 5_100_000_000,
        },
    )

    result = worker.qualify_model("http://127.0.0.1:11434", "qwen3:8b-q4_K_M")
    capabilities = worker.build_capabilities("qwen3:8b-q4_K_M", result)

    assert result["status"] == "passed"
    assert list(result["stageHashes"]) == ["analyst", "verifier", "repair", "finalVerifier"]
    assert len(calls) == 4
    assert capabilities["models"][0]["readiness"] == "preflighted"
    assert capabilities["models"][0]["contextLength"] == 8192


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("failed to allocate CUDA_Host buffer", "out_of_memory"),
        ("error loading model", "model_load_failed"),
        ("truncated output", "truncation"),
        ("schema failure", "schema_invalid"),
    ],
)
def test_failure_codes_are_bounded_and_observable(message: str, expected: str) -> None:
    assert worker.failure_code(RuntimeError(message)) == expected


def test_api_rejects_inventory_only_model_capabilities() -> None:
    with pytest.raises(ValidationError, match="hardware preflight"):
        WorkerCapabilities(
            workerVersion="ambrosia-local-worker.v2",
            ollamaVersion="0.32.9",
            models=[
                {
                    "name": "qwen3-coder:30b",
                    "digest": "sha256:inventory-only",
                    "contextLength": 8192,
                }
            ],
        )
