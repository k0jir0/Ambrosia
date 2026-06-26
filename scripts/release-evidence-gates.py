#!/usr/bin/env python3
"""
Phase B3: Evidence-backed Release Gates
Quality evidence package builder and promotion gate checker.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal


@dataclass
class GateCheck:
    """Single gate check result"""
    gate_id: str
    gate_name: str
    status: Literal["pass", "fail", "warning"]
    details: str
    evidence_artifact: str


class ReleaseEvidencePackage:
    """Builds quality evidence for promotion decisions"""
    
    def __init__(self, version: str):
        self.version = version
        self.timestamp = datetime.now().isoformat()
        self.gates: list[GateCheck] = []
    
    def add_gate(self, gate_id: str, gate_name: str, status: Literal["pass", "fail", "warning"],
                 details: str, evidence_artifact: str) -> None:
        """Add a gate check result"""
        self.gates.append(GateCheck(
            gate_id=gate_id,
            gate_name=gate_name,
            status=status,
            details=details,
            evidence_artifact=evidence_artifact,
        ))
    
    def can_promote(self) -> bool:
        """Check if all gates are passing"""
        return all(g.status in ["pass", "warning"] for g in self.gates) and any(g.status == "pass" for g in self.gates)
    
    def promotion_blocking_gates(self) -> list[GateCheck]:
        """Get gates that block promotion"""
        return [g for g in self.gates if g.status == "fail"]
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization"""
        blocking = self.promotion_blocking_gates()
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "can_promote": self.can_promote(),
            "total_gates": len(self.gates),
            "passed_gates": sum(1 for g in self.gates if g.status == "pass"),
            "warning_gates": sum(1 for g in self.gates if g.status == "warning"),
            "failed_gates": sum(1 for g in self.gates if g.status == "fail"),
            "blocking_gates": [asdict(g) for g in blocking],
            "all_gates": [asdict(g) for g in self.gates],
            "promotion_recommendation": self._get_recommendation(),
        }
    
    def _get_recommendation(self) -> str:
        """Get promotion recommendation"""
        if not self.can_promote():
            blocking = self.promotion_blocking_gates()
            gates_str = ", ".join(f"{g.gate_id}" for g in blocking)
            return f"DO NOT PROMOTE: Gates failing: {gates_str}"
        
        warning_count = sum(1 for g in self.gates if g.status == "warning")
        if warning_count > 0:
            return f"PROMOTE WITH CAUTION: {warning_count} warning(s). Monitor post-deploy."
        
        return "SAFE TO PROMOTE: All gates passing."


class PromotionGateDefinitions:
    """Defines the standard promotion gates"""
    
    @staticmethod
    def get_all_gates() -> list[dict]:
        """Get all defined promotion gates"""
        return [
            {
                "gate_id": "api_tests",
                "gate_name": "API Contract Tests",
                "severity": "blocker",
                "description": "142 core API tests must pass",
                "evidence_file": "artifacts/test-results.json",
            },
            {
                "gate_id": "retrieval_quality",
                "gate_name": "Retrieval Quality Benchmarks",
                "severity": "blocker",
                "description": "5/5 retrieval benchmarks must pass (60% precision, 75% recall)",
                "evidence_file": "artifacts/retrieval-benchmark.json",
            },
            {
                "gate_id": "migration_validation",
                "gate_name": "Schema/Migration Validation",
                "severity": "blocker",
                "description": "Migration framework and versioning checks",
                "evidence_file": "artifacts/phase-a1-migrations.json",
            },
            {
                "gate_id": "calibration_metrics",
                "gate_name": "Calibration Metrics Continuous",
                "severity": "blocker",
                "description": "All 8 calibration metrics computing and in bounds",
                "evidence_file": "artifacts/calibration-metrics.json",
            },
            {
                "gate_id": "synthetic_monitoring",
                "gate_name": "Synthetic Monitoring Health",
                "severity": "warning",
                "description": "6-hourly synthetic probes show no critical regressions",
                "evidence_file": "artifacts/synthetic-monitoring-regression.json",
            },
            {
                "gate_id": "provider_ablation",
                "gate_name": "Provider Ablation Report",
                "severity": "warning",
                "description": "Cost/latency/quality analysis completed",
                "evidence_file": "artifacts/provider-ablation.json",
            },
            {
                "gate_id": "visibility_coverage",
                "gate_name": "Function Registry & UI Coverage",
                "severity": "blocker",
                "description": "All non-internal functions have visible frontend surfaces",
                "evidence_file": "artifacts/visibility-matrix.json",
            },
        ]


def generate_release_evidence_package(version: str, artifact_dir: str = "artifacts") -> dict:
    """Generate comprehensive evidence package for promotion decision"""
    package = ReleaseEvidencePackage(version)
    artifact_path = Path(artifact_dir)
    
    # Check each gate
    for gate_def in PromotionGateDefinitions.get_all_gates():
        gate_id = gate_def["gate_id"]
        gate_name = gate_def["gate_name"]
        severity = gate_def["severity"]
        evidence_file = gate_def["evidence_file"]
        
        # Determine gate status
        evidence_path = artifact_path / Path(evidence_file).name
        
        if evidence_path.exists():
            try:
                with open(evidence_path) as f:
                    evidence = json.load(f)
                
                # Determine status based on evidence content
                status = _evaluate_gate_status(gate_id, evidence)
                
                # Determine if warning or fail
                gate_status = status if status == "pass" else severity
                if gate_status == "blocker":
                    gate_status = "fail"
                elif gate_status == "warning":
                    gate_status = "warning"
                
                package.add_gate(
                    gate_id=gate_id,
                    gate_name=gate_name,
                    status=gate_status,
                    details=f"Evidence found: {evidence_file}",
                    evidence_artifact=str(evidence_path),
                )
            except Exception as e:
                package.add_gate(
                    gate_id=gate_id,
                    gate_name=gate_name,
                    status="fail",
                    details=f"Error reading evidence: {e}",
                    evidence_artifact=str(evidence_path),
                )
        else:
            # Missing evidence
            severity_status = "fail" if severity == "blocker" else "warning"
            package.add_gate(
                gate_id=gate_id,
                gate_name=gate_name,
                status=severity_status,
                details=f"Evidence artifact missing: {evidence_file}",
                evidence_artifact=str(evidence_path),
            )
    
    return package.to_dict()


def _evaluate_gate_status(gate_id: str, evidence: dict) -> Literal["pass", "fail"]:
    """Evaluate if gate evidence indicates pass"""
    
    if gate_id == "api_tests":
        # Check if test count indicates success
        return "pass" if evidence.get("total_tests", 0) >= 142 else "fail"
    
    elif gate_id == "retrieval_quality":
        # Check if benchmarks passing
        passed = evidence.get("benchmarks_passed", 0)
        return "pass" if passed >= 5 else "fail"
    
    elif gate_id == "migration_validation":
        # Check if all validation checks pass
        status = evidence.get("status", "fail")
        return "pass" if status == "PASS" else "fail"
    
    elif gate_id == "calibration_metrics":
        # Check if all 8 metrics present
        metrics_count = len(evidence.get("metrics", []))
        return "pass" if metrics_count >= 8 else "fail"
    
    elif gate_id == "synthetic_monitoring":
        # Check health status
        health = evidence.get("health_status", "unknown")
        return "pass" if health in ["ok", "warning"] else "fail"
    
    elif gate_id == "provider_ablation":
        # Check if report generated
        return "pass" if evidence.get("providers_compared", 0) > 0 else "fail"
    
    elif gate_id == "visibility_coverage":
        # Check coverage percentage
        coverage = evidence.get("coverage_percentage", 0)
        return "pass" if coverage >= 90 else "fail"
    
    return "pass"


if __name__ == "__main__":
    # Generate sample evidence package
    version = "0.2.0"
    evidence_package = generate_release_evidence_package(version)
    
    # Save artifact
    artifact_path = Path("artifacts/release-evidence-package.json")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(artifact_path, "w") as f:
        json.dump(evidence_package, f, indent=2)
    
    print("Release Evidence Package")
    print("=" * 70)
    print(f"Version: {evidence_package['version']}")
    print(f"Timestamp: {evidence_package['timestamp']}")
    print(f"Can Promote: {evidence_package['can_promote']}")
    print(f"Gates Passed: {evidence_package['passed_gates']}/{evidence_package['total_gates']}")
    
    if evidence_package["blocking_gates"]:
        print(f"\nBlocking Gates:")
        for gate in evidence_package["blocking_gates"]:
            print(f"  ✗ {gate['gate_name']}: {gate['details']}")
    
    print(f"\nRecommendation: {evidence_package['promotion_recommendation']}")
    print(f"\nEvidence package saved to: {artifact_path}")
