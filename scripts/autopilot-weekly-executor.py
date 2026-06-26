#!/usr/bin/env python3
"""
Ambrosia 100% Autopilot Orchestrator
Executes weekly validation checklist to maintain path to 100% completion

Schedule: Every Friday 5:00 PM UTC (after business hours, before weekend)
Execution time: ~15-20 minutes
Output: Updated artifacts/ + status commit to git

Phases:
- Phase A (92% → 100%): Weeks 1-2 - Production validation
- Phase B (88% → 100%): Weeks 2-4 - CI/CD integration 
- Phase C (89% → 100%): Weeks 5-7 - UI integration
- Phase D (92% → 100%): Weeks 7-9 - RBAC enforcement
- Phase E (95% → 100%): Weeks 10-11 - Execution loop
"""

import subprocess
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"

# Phase-specific validation scripts (in execution order)
VALIDATION_SCRIPTS = [
    ("verify-phase-a1-migrations.py", "Phase A1: Persistence & Migrations"),
    ("verify-retrieval-quality.py", "Phase A2: Retrieval Quality Metrics"),
    ("verify-scorecard-runtime.py", "Phase A3: Calibration & Scorecard"),
    ("generate-provider-ablation.py", "Phase B1: Provider Ablation Analysis"),
    ("synthetic-monitor.py", "Phase B2: Synthetic Monitoring"),
    ("release-evidence-gates.py", "Phase B3: Evidence-backed Release Gates"),
    ("verify-visibility-matrix.py", "Phase B4: Function Registry & Visibility"),
    ("verify-permission-boundaries.py", "Phase D1-D2: RBAC & Permission Boundaries"),
    ("validate-index59-100-percent.py", "Overall: Index59 Roadmap Status"),
]

class AutopilotExecutor:
    def __init__(self):
        self.start_time = datetime.now()
        self.results = []
        self.failed_scripts = []
        self.status_artifact = {
            "timestamp": self.start_time.isoformat(),
            "phase": "autopilot_weekly_execution",
            "week": self._get_week_number(),
            "scripts_executed": 0,
            "scripts_passed": 0,
            "scripts_failed": 0,
            "execution_time_seconds": 0,
            "status": "running",
            "results": []
        }
    
    def _get_week_number(self):
        """Calculate week number relative to Phase A start (2026-06-25)"""
        phase_a_start = datetime(2026, 6, 25)
        weeks_elapsed = (datetime.now() - phase_a_start).days // 7
        return max(1, weeks_elapsed + 1)
    
    def execute_validation_script(self, script_name, description):
        """Execute a single validation script and capture results"""
        script_path = SCRIPTS_DIR / script_name
        
        if not script_path.exists():
            print(f"  ✗ {description} - SKIPPED (script not found)")
            return False
        
        try:
            print(f"  ➤ {description}...", end=" ", flush=True)
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=120
            )
            
            success = result.returncode == 0
            status = "✓ PASS" if success else "✗ FAIL"
            print(status)
            
            self.results.append({
                "script": script_name,
                "description": description,
                "status": "pass" if success else "fail",
                "returncode": result.returncode,
                "output_preview": result.stdout[:200] if result.stdout else "",
                "error_preview": result.stderr[:200] if result.stderr else ""
            })
            
            if not success:
                self.failed_scripts.append((script_name, description))
            
            return success
            
        except subprocess.TimeoutExpired:
            print("✗ TIMEOUT")
            self.failed_scripts.append((script_name, f"{description} (timeout)"))
            self.results.append({
                "script": script_name,
                "description": description,
                "status": "timeout",
                "error": "Script execution exceeded 120 seconds"
            })
            return False
        except Exception as e:
            print(f"✗ ERROR: {str(e)}")
            self.failed_scripts.append((script_name, description))
            self.results.append({
                "script": script_name,
                "description": description,
                "status": "error",
                "error": str(e)
            })
            return False
    
    def run(self):
        """Execute full autopilot sequence"""
        print("\n" + "="*80)
        print("AMBROSIA 100% AUTOPILOT - WEEKLY EXECUTION")
        print("="*80)
        print(f"Timestamp: {self.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Week: {self._get_week_number()}")
        print(f"Roadmap: INDEX59 → 100% Completion")
        print("="*80)
        print()
        
        # Execute all validation scripts
        print("PHASE VALIDATION SEQUENCE:")
        print()
        
        passed_count = 0
        for script_name, description in VALIDATION_SCRIPTS:
            if self.execute_validation_script(script_name, description):
                passed_count += 1
            self.status_artifact["scripts_executed"] += 1
        
        # Calculate statistics
        self.status_artifact["scripts_passed"] = passed_count
        self.status_artifact["scripts_failed"] = len(self.failed_scripts)
        self.status_artifact["results"] = self.results
        
        end_time = datetime.now()
        execution_seconds = (end_time - self.start_time).total_seconds()
        self.status_artifact["execution_time_seconds"] = execution_seconds
        
        # Determine overall status
        if len(self.failed_scripts) == 0:
            self.status_artifact["status"] = "success"
            status_emoji = "✓"
        elif len(self.failed_scripts) <= 2:
            self.status_artifact["status"] = "warning"
            status_emoji = "⚠"
        else:
            self.status_artifact["status"] = "failure"
            status_emoji = "✗"
        
        # Print summary
        print()
        print("="*80)
        print(f"AUTOPILOT EXECUTION SUMMARY {status_emoji}")
        print("="*80)
        print(f"Scripts executed: {self.status_artifact['scripts_executed']}")
        print(f"Scripts passed:   {self.status_artifact['scripts_passed']}")
        print(f"Scripts failed:   {self.status_artifact['scripts_failed']}")
        print(f"Execution time:   {execution_seconds:.1f} seconds")
        print()
        
        if self.failed_scripts:
            print("FAILURES:")
            for script, desc in self.failed_scripts:
                print(f"  ✗ {desc} ({script})")
            print()
        
        # Save status artifact
        artifact_path = ARTIFACTS_DIR / "autopilot-weekly-status.json"
        artifact_path.write_text(json.dumps(self.status_artifact, indent=2))
        print(f"Status artifact saved: artifacts/autopilot-weekly-status.json")
        print()
        
        # Suggest next action
        if self.status_artifact["status"] == "success":
            print("✓ AUTOPILOT SEQUENCE COMPLETE - ALL PHASES VALIDATED")
            print()
            print("NEXT STEPS:")
            print("  1. Review updated artifacts/ directory")
            print("  2. Commit status to git: git add artifacts/ && git commit -m 'chore: Weekly autopilot [Week {}'".format(self._get_week_number()))
            print("  3. Check overall completion: cat artifacts/index59-100-percent-completion.json | jq .overall_completion_pct")
            print()
        else:
            print("⚠ AUTOPILOT SEQUENCE COMPLETED WITH ISSUES")
            print()
            print("REMEDIATION STEPS:")
            for script, desc in self.failed_scripts:
                print(f"  • Investigate: {script} - {desc}")
            print()
        
        print("="*80)
        return 0 if self.status_artifact["status"] != "failure" else 1

if __name__ == "__main__":
    executor = AutopilotExecutor()
    sys.exit(executor.run())
