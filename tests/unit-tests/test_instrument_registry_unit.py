from __future__ import annotations

import pytest
from fastapi import HTTPException

from services.api.app import instrument_registry, main


def test_reserved_ticker_is_rejected_without_provider_call(monkeypatch) -> None:
    monkeypatch.setattr(instrument_registry, "resilient_urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()))
    result = instrument_registry.resolve_instrument("sample")
    assert result.status == "not_found"
    assert result.canonical_ticker is None


@pytest.mark.parametrize(
    ("resolution_status", "http_status"),
    [("not_found", 404), ("inactive", 404), ("unsupported", 404), ("ambiguous", 422), ("provider_unavailable", 503)],
)
def test_market_endpoint_resolution_status_mapping(monkeypatch, resolution_status, http_status) -> None:
    monkeypatch.setattr(
        main,
        "resolve_instrument",
        lambda ticker: instrument_registry.InstrumentResolution(ticker, resolution_status),
    )
    with pytest.raises(HTTPException) as raised:
        main._verified_market_ticker("FAKE")
    assert raised.value.status_code == http_status
