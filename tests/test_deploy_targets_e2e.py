from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Iterable

import pytest
import requests


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class DeployTarget:
    name: str
    web_url: str
    api_url: str | None


def _normalize_base(url: str) -> str:
    return url.rstrip("/")


def _build_targets() -> list[DeployTarget]:
    targets: list[DeployTarget] = []
    staging_web = _normalize_base(os.getenv("STAGING_WEB_URL", ""))
    staging_api = _normalize_base(os.getenv("STAGING_API_URL", ""))
    if staging_web:
        targets.append(DeployTarget(name="staging", web_url=staging_web, api_url=staging_api or None))

    production_web = _normalize_base(os.getenv("PRODUCTION_WEB_URL", ""))
    production_api = _normalize_base(os.getenv("PRODUCTION_API_URL", ""))
    if production_web:
        targets.append(DeployTarget(name="production", web_url=production_web, api_url=production_api or None))

    default_targets = "staging,production"
    if _env_flag("CI") and os.getenv("GITHUB_REF_NAME", "").strip().lower() == "staging":
        # Keep staging pipelines focused on staging health, not production availability.
        default_targets = "staging"

    selected = os.getenv("DEPLOY_TARGETS", default_targets)
    selected_names = {item.strip().lower() for item in selected.split(",") if item.strip()}
    return [target for target in targets if target.name in selected_names]


RUN_DEPLOY_E2E = _env_flag("RUN_DEPLOY_E2E")
TARGETS = _build_targets()


pytestmark = [
    pytest.mark.deployment,
    pytest.mark.integration,
    pytest.mark.smoke,
    pytest.mark.timeout(90),
]


@pytest.fixture(scope="session", autouse=True)
def _require_enable_flag() -> Iterable[None]:
    if not RUN_DEPLOY_E2E:
        pytest.skip("Set RUN_DEPLOY_E2E=true to run deploy-targeted e2e tests.")
    if not TARGETS:
        pytest.skip("No deploy targets selected. Check DEPLOY_TARGETS env var.")
    yield


def _request(method: str, url: str, **kwargs) -> requests.Response:
    timeout = float(os.getenv("DEPLOY_E2E_TIMEOUT_SECONDS", "20"))
    retries = max(1, int(os.getenv("DEPLOY_E2E_RETRIES", "3")))
    retry_delay = float(os.getenv("DEPLOY_E2E_RETRY_DELAY_SECONDS", "2"))
    headers = {"User-Agent": "ambrosia-deploy-e2e/1.0", **kwargs.pop("headers", {})}
    last_error: Exception | None = None
    last_response: requests.Response | None = None

    for attempt in range(1, retries + 1):
        try:
            response = requests.request(method=method, url=url, timeout=timeout, headers=headers, **kwargs)
            last_response = response
            if response.status_code < 500:
                return response
        except requests.Timeout as error:
            last_error = error

        if attempt < retries:
            time.sleep(retry_delay * attempt)

    if last_error is not None:
        raise last_error

    if last_response is not None:
        return last_response

    raise RuntimeError(f"No response received for {method} {url}")


@pytest.mark.parametrize("target", TARGETS, ids=[target.name for target in TARGETS])
def test_web_root_is_reachable(target: DeployTarget) -> None:
    response = _request("GET", f"{target.web_url}/")
    assert response.status_code == 200, f"{target.name} web root status={response.status_code}"
    assert "text/html" in response.headers.get("content-type", "")
    assert "Ambrosia" in response.text or "<html" in response.text.lower()


@pytest.mark.parametrize("target", TARGETS, ids=[target.name for target in TARGETS])
def test_api_health_is_reachable(target: DeployTarget) -> None:
    if not target.api_url:
        pytest.skip(f"{target.name} has no api url configured")
    response = _request("GET", f"{target.api_url}/health")
    assert response.status_code == 200, f"{target.name} api health status={response.status_code}"
    payload = response.json()
    assert payload.get("status") == "ok"
    assert payload.get("service") == "ambrosia-api"


def test_staging_index96_routes_are_live() -> None:
    staging = next((target for target in TARGETS if target.name == "staging"), None)
    if staging is None:
        pytest.skip("staging target not selected")

    for route in ["/market-scanner", "/markets/AAPL", "/alpha", "/signals"]:
        response = _request("GET", f"{staging.web_url}{route}")
        assert response.status_code == 200, f"staging route {route} status={response.status_code}"


def test_staging_api_exposes_signal_and_scanner_contracts() -> None:
    staging = next((target for target in TARGETS if target.name == "staging"), None)
    if staging is None:
        pytest.skip("staging target not selected")
    if not staging.api_url:
        pytest.skip("staging api url not configured")

    signals_response = _request("GET", f"{staging.api_url}/signals")
    assert signals_response.status_code == 200
    assert isinstance(signals_response.json(), list)

    scanner_response = _request(
        "POST",
        f"{staging.api_url}/scanner/run",
        json={"universe": ["AAPL", "MSFT", "SPY"], "maxCandidates": 3, "signalFilter": "all", "minVolume": 1.0},
    )
    assert scanner_response.status_code == 200
    payload = scanner_response.json()
    assert isinstance(payload.get("candidates"), list)
    assert payload.get("totalScanned", 0) >= 1
