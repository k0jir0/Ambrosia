#!/usr/bin/env python3
"""
Pre-deploy schema validation — ensures no breaking changes to contracts.

This script validates that the current codebase hasn't introduced any
breaking changes to the 8 core contract gates. It's meant to run before
deployment to catch schema issues early.

Exit code 0 = pass (safe to deploy)
Exit code 1 = fail (contains breaking changes, DO NOT DEPLOY)
"""
from __future__ import annotations

import sys
import subprocess
import json
from pathlib import Path


def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and return True if successful."""
    print(f"\n{'='*70}")
    print(f"Validating: {description}")
    print(f"{'='*70}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        print(f"✓ PASS: {description}")
        return True
    except subprocess.CalledProcessError as e:
        if e.stderr:
            print(e.stderr)
        if e.stdout:
            print(e.stdout)
        print(f"✗ FAIL: {description}")
        print(f"Exit code: {e.returncode}")
        return False


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    api_dir = root / "services" / "api"
    
    print(f"\n{'#'*70}")
    print("# Pre-Deploy Schema Validation")
    print(f"# Root: {root}")
    print(f"{'#'*70}")

    all_pass = True

    # -----------------------------------------------------------------------
    # 1. Contract gate tests — must all pass
    # -----------------------------------------------------------------------
    print(f"\n{'-'*70}")
    print("PHASE 1: Contract Gate Tests (8 Core Functions)")
    print(f"{'-'*70}")
    
    contract_result = run_command(
        [sys.executable, "-m", "pytest", "services/api/tests/test_contract_gates.py", "-v"],
        "Contract gates validation"
    )
    all_pass = all_pass and contract_result

    # -----------------------------------------------------------------------
    # 2. Stack contract tests — monorepo consistency
    # -----------------------------------------------------------------------
    print(f"\n{'-'*70}")
    print("PHASE 2: Stack Contract Tests (Monorepo Consistency)")
    print(f"{'-'*70}")
    
    stack_result = run_command(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_stack_contract.py", "-v"],
        "Stack contracts validation"
    )
    all_pass = all_pass and stack_result

    # -----------------------------------------------------------------------
    # 3. API linting
    # -----------------------------------------------------------------------
    print(f"\n{'-'*70}")
    print("PHASE 3: Code Quality (Linting)")
    print(f"{'-'*70}")
    
    lint_result = run_command(
        [sys.executable, "-m", "pip", "install", "ruff"],
        "Ruff linter installation (pre-check)"
    )
    if lint_result:
        lint_result = run_command(
            [sys.executable, "-m", "ruff", "check", "app", "tests"],
            "API linting with Ruff"
        )
    all_pass = all_pass and lint_result

    # -----------------------------------------------------------------------
    # 4. Schema file validation
    # -----------------------------------------------------------------------
    print(f"\n{'-'*70}")
    print("PHASE 4: Schema Files Validation")
    print(f"{'-'*70}")
    
    schema_file = root / "packages" / "schemas" / "review.v1.json"
    if schema_file.exists():
        try:
            with open(schema_file, "r") as f:
                json.load(f)
            print(f"✓ PASS: Schema file is valid JSON: {schema_file}")
        except json.JSONDecodeError as e:
            print(f"✗ FAIL: Schema file is invalid JSON: {schema_file}")
            print(f"Error: {e}")
            all_pass = False
    else:
        print(f"ℹ INFO: Schema file not found: {schema_file} (skipping)")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print(f"\n{'='*70}")
    if all_pass:
        print("✓ ALL VALIDATIONS PASSED — safe to deploy")
        print(f"{'='*70}\n")
        return 0
    else:
        print("✗ SOME VALIDATIONS FAILED — DO NOT DEPLOY")
        print(f"{'='*70}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
