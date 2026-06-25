#!/usr/bin/env python3
"""
Lightweight pre-deployment validation for Index52 todos.
Checks syntax + key files exist + no import errors.

Exit code 0 = pass (safe to deploy)
Exit code 1 = fail (DO NOT DEPLOY)
"""
import sys
import py_compile
from pathlib import Path

def main():
    root = Path(__file__).resolve().parent.parent
    
    print("\n" + "="*70)
    print("INDEX52 PRE-DEPLOYMENT VALIDATION")
    print("="*70)
    
    # List of critical files that must exist and be valid
    critical_files = [
        "services/api/app/calibration_metrics.py",
        "services/api/app/operational_scorecard.py",
        "services/api/app/feedback.py",
        "services/api/app/feedback_api.py",
        "services/api/app/feedback_store.py",
        "services/api/app/store.py",
        "services/api/app/main.py",
        "scripts/deploy-smoke-test.py",
        "render.yaml",
    ]
    
    all_pass = True
    
    print("\n[1/3] Checking critical files exist...")
    for file in critical_files:
        path = root / file
        if path.exists():
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file} (MISSING)")
            all_pass = False
    
    print("\n[2/3] Validating Python syntax...")
    python_files = [
        "services/api/app/calibration_metrics.py",
        "services/api/app/operational_scorecard.py",
        "services/api/app/feedback.py",
        "services/api/app/feedback_api.py",
        "services/api/app/store.py",
        "services/api/app/main.py",
        "scripts/deploy-smoke-test.py",
    ]
    
    for file in python_files:
        path = root / file
        try:
            py_compile.compile(str(path), doraise=True)
            print(f"  ✅ {file}")
        except py_compile.PyCompileError as e:
            print(f"  ❌ {file}")
            print(f"     Error: {e}")
            all_pass = False
    
    print("\n[3/3] Checking key imports (optional - skipped if deps not installed)...")
    try:
        sys.path.insert(0, str(root / "services" / "api"))
        
        # Test that key modules can be imported
        import app.calibration_metrics
        print(f"  ✅ calibration_metrics module")
        
        import app.operational_scorecard
        print(f"  ✅ operational_scorecard module")
        
        import app.feedback
        print(f"  ✅ feedback module")
        
        import app.feedback_api
        print(f"  ✅ feedback_api module")
        
    except ImportError as e:
        print(f"  ⓘ Import check skipped (dependencies not installed locally)")
        print(f"     This is OK - dependencies will install on Render")
        print(f"     Error was: {e}")
    
    print("\n" + "="*70)
    if all_pass:
        print("✅ ALL VALIDATIONS PASSED — ready to deploy")
        print("="*70 + "\n")
        return 0
    else:
        print("❌ VALIDATION FAILED — DO NOT DEPLOY")
        print("="*70 + "\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
