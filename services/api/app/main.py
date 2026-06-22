from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import DecisionUpdate, OutcomeUpdate, ThesisRequest, TradeReview
from .review_engine import generate_review
from .store import store

app = FastAPI(title="Ambrosia Trade Review API", version="0.1.0")

default_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
configured_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
allowed_origin_regex = os.getenv("ALLOWED_ORIGIN_REGEX", r"https://.*\.onrender\.com")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[*default_origins, *configured_origins],
    allow_origin_regex=allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ambrosia-api"}


@app.get("/reviews", response_model=list[TradeReview])
def list_reviews() -> list[TradeReview]:
    return store.list_reviews()


@app.post("/reviews", response_model=TradeReview)
def create_review(request: ThesisRequest) -> TradeReview:
    review = generate_review(request, store.next_trial_count)
    return store.save_review(review)


@app.get("/reviews/{review_id}", response_model=TradeReview)
def get_review(review_id: str) -> TradeReview:
    review = store.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@app.patch("/reviews/{review_id}/decision", response_model=TradeReview)
def record_decision(review_id: str, update: DecisionUpdate) -> TradeReview:
    review = store.record_decision(review_id, update.decision_state)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@app.post("/reviews/{review_id}/outcome", response_model=TradeReview)
def record_outcome(review_id: str, update: OutcomeUpdate) -> TradeReview:
    review = store.record_outcome(review_id, update)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@app.post("/webhooks/tradingview", response_model=TradeReview)
def tradingview_webhook(payload: dict[str, object]) -> TradeReview:
    thesis = str(payload.get("thesis") or payload.get("message") or payload.get("condition") or "TradingView alert requires review")
    request = ThesisRequest(
        thesis=thesis,
        ticker=str(payload.get("symbol") or payload.get("ticker") or "TradingView alert"),
        asset_class=str(payload.get("asset_class") or "Market alert"),
        time_horizon=str(payload.get("time_horizon") or payload.get("timeframe") or "Unspecified"),
        intended_expression=str(payload.get("intended_expression") or payload.get("related_instruments") or "Expression requires review"),
        source_pointer="TradingView webhook payload",
    )
    review = generate_review(request, store.next_trial_count)
    return store.save_review(review)


@app.get("/metrics")
def metrics() -> dict[str, int]:
    reviews = store.list_reviews()
    return {
        "reviews_created": len(reviews),
        "decisions_recorded": sum(1 for review in reviews if review.decisionState is not None),
        "rejected_or_deferred": sum(1 for review in reviews if review.decisionState in {"reject", "needs_more_data"}),
    }
