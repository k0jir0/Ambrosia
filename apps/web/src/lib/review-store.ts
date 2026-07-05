"use client";

import { useEffect, useMemo, useState } from "react";
import { ApiUnavailableError, createReview, getReview, listReviews } from "./api";
import { generateLocalReview } from "./review-generator";
import { sampleReviews } from "./sample-data";
import type { ThesisInput, TradeReview } from "./types";

const STORAGE_KEY = "ambrosia.reviews.v1";

function dedupeAndSort(reviews: TradeReview[]): TradeReview[] {
  const seen = new Map<string, TradeReview>();
  for (const review of reviews) {
    seen.set(review.id, review);
  }
  return Array.from(seen.values()).sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
}

function canUseStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export function getLocalReviews(): TradeReview[] {
  if (!canUseStorage()) return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as TradeReview[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveLocalReviews(reviews: TradeReview[]) {
  if (!canUseStorage()) return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(dedupeAndSort(reviews)));
}

export function upsertLocalReview(review: TradeReview) {
  const next = dedupeAndSort([review, ...getLocalReviews()]);
  saveLocalReviews(next);
  window.dispatchEvent(new CustomEvent("ambrosia:reviews-updated"));
}

export async function loadReviewArchive(): Promise<{ reviews: TradeReview[]; source: "api" | "local" | "sample" }> {
  try {
    const apiReviews = await listReviews();
    return {
      // When API is reachable, prefer canonical server data for a real-model dashboard.
      reviews: dedupeAndSort(apiReviews),
      source: "api"
    };
  } catch {
    const local = getLocalReviews();
    return {
      reviews: dedupeAndSort([...local, ...sampleReviews]),
      source: local.length > 0 ? "local" : "sample"
    };
  }
}

export async function createReviewRecord(input: ThesisInput, currentReviewCount: number): Promise<{ review: TradeReview; source: "api" | "local" }> {
  try {
    const review = await createReview(input);
    upsertLocalReview(review);
    return { review, source: "api" };
  } catch (error) {
    if (!(error instanceof ApiUnavailableError)) {
      // Preserve UX continuity for validation/network edge cases while keeping local audit detail.
    }
    const review = generateLocalReview(input, currentReviewCount);
    upsertLocalReview(review);
    return { review, source: "local" };
  }
}

export async function resolveReview(reviewId: string): Promise<TradeReview | null> {
  const localOrSample = dedupeAndSort([...getLocalReviews(), ...sampleReviews]).find((review) => review.id === reviewId);
  if (localOrSample) return localOrSample;

  try {
    return await getReview(reviewId);
  } catch {
    return null;
  }
}

export function useReviewArchive() {
  const [reviews, setReviews] = useState<TradeReview[]>([]);
  const [source, setSource] = useState<"api" | "local" | "sample">("api");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function refresh() {
      setLoading(true);
      const result = await loadReviewArchive();
      if (!cancelled) {
        setReviews(result.reviews);
        setSource(result.source);
        setLoading(false);
      }
    }

    function onUpdated() {
      void refresh();
    }

    void refresh();
    window.addEventListener("ambrosia:reviews-updated", onUpdated);
    window.addEventListener("storage", onUpdated);

    return () => {
      cancelled = true;
      window.removeEventListener("ambrosia:reviews-updated", onUpdated);
      window.removeEventListener("storage", onUpdated);
    };
  }, []);

  return useMemo(() => ({ reviews, source, loading }), [loading, reviews, source]);
}
