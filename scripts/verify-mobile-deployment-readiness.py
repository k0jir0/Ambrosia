#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOBILE_ROOT = ROOT / "apps" / "mobile"
APP_JSON = MOBILE_ROOT / "app.json"
EAS_JSON = MOBILE_ROOT / "eas.json"
REQUIRED_ASSETS = [
    MOBILE_ROOT / "assets" / "icon.png",
    MOBILE_ROOT / "assets" / "android-icon-foreground.png",
    MOBILE_ROOT / "assets" / "android-icon-background.png",
    MOBILE_ROOT / "assets" / "android-icon-monochrome.png",
    MOBILE_ROOT / "assets" / "splash-icon.png",
]


def main() -> int:
    errors: list[str] = []
    app = json.loads(APP_JSON.read_text(encoding="utf-8"))["expo"]
    eas = json.loads(EAS_JSON.read_text(encoding="utf-8"))

    expected = {
        "name": "Ambrosia",
        "slug": "ambrosia",
        "scheme": "ambrosia",
    }
    for key, value in expected.items():
        if app.get(key) != value:
            errors.append(f"expo.{key} must be {value!r}")

    if app.get("ios", {}).get("bundleIdentifier") != "com.ambrosia.mobile":
        errors.append("ios.bundleIdentifier must be com.ambrosia.mobile")
    if app.get("android", {}).get("package") != "com.ambrosia.mobile":
        errors.append("android.package must be com.ambrosia.mobile")
    if app.get("extra", {}).get("defaultApiUrl") != "http://127.0.0.1:8000":
        errors.append("extra.defaultApiUrl must remain local; production builds inject EXPO_PUBLIC_API_URL")
    if app.get("extra", {}).get("eas", {}).get("projectId") != "b69a95c2-84e0-429f-8781-e0227e374ed8":
        errors.append("extra.eas.projectId must match the connected Expo project")

    profiles = eas.get("build", {})
    for profile in ["development", "preview", "production"]:
        if profile not in profiles:
            errors.append(f"Missing EAS build profile: {profile}")

    for asset in REQUIRED_ASSETS:
        if not asset.exists() or asset.stat().st_size == 0:
            errors.append(f"Missing mobile asset: {asset.relative_to(ROOT)}")

    if errors:
        print("Mobile deployment readiness failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Mobile deployment readiness check passed.")
    print("- iOS bundle: com.ambrosia.mobile")
    print("- Android package: com.ambrosia.mobile")
    print("- EAS profiles: development, preview, production")
    print("- Production API: supplied by EXPO_PUBLIC_API_URL in the protected build environment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
