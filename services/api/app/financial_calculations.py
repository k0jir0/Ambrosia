"""Deterministic, auditable financial calculations for LLM-proposed intents."""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_EVEN
from .models import CalculationArtifact, CalculationIntent

def _path(value: object, path: str) -> object:
    current = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"Calculation path does not resolve: {path}")
        current = current[part]
    return current

def evaluate_calculation_intent(intent: CalculationIntent, evidence: list[dict]) -> CalculationArtifact:
    if len(intent.inputEvidenceIds) != len(intent.inputPaths):
        raise ValueError("Calculation evidence IDs and paths must have equal length")
    by_id = {str(item.get("evidenceId")): item for item in evidence}
    values: list[Decimal] = []
    for evidence_id, path in zip(intent.inputEvidenceIds, intent.inputPaths, strict=True):
        item = by_id.get(evidence_id)
        if not item or item.get("dataMode") in {"simulated", "user_asserted"}:
            raise ValueError("Calculation evidence is missing or inadmissible")
        values.append(Decimal(str(_path(item.get("content", {}), path))))
    op = intent.operation
    if op == "add": result, formula = sum(values, Decimal(0)), " + ".join(map(str, values))
    elif op in {"subtract", "percentage_point_change"} and len(values) == 2:
        result = values[0] - values[1] if op == "subtract" else values[1] - values[0]
        formula = f"{values[0]} - {values[1]}" if op == "subtract" else f"{values[1]} - {values[0]}"
    elif op in {"divide", "margin"} and len(values) == 2 and values[1] != 0:
        result, formula = values[0] / values[1], f"{values[0]} / {values[1]}"
    elif op == "percent_change" and len(values) == 2 and values[0] != 0:
        result = ((values[1] - values[0]) / abs(values[0])) * Decimal(100)
        formula = f"(({values[1]} - {values[0]}) / abs({values[0]})) * 100"
    else: raise ValueError("Invalid calculation operation or arity")
    rounding = "no_implicit_rounding"
    if intent.roundingDigits is not None:
        result = result.quantize(Decimal(1).scaleb(-intent.roundingDigits), rounding=ROUND_HALF_EVEN)
        rounding = f"bankers_rounding_{intent.roundingDigits}_digits"
    return CalculationArtifact(
        calculationId=intent.calculationId, operation=op, inputEvidenceIds=intent.inputEvidenceIds,
        rawValues=[float(value) for value in values], units=intent.units, scale=intent.scale,
        fiscalPeriods=intent.fiscalPeriods, formula=formula, result=float(result),
        roundingRule=rounding, validationStatus="passed",
    )
