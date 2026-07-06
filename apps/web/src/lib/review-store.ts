"use client";

import { useEffect, useMemo, useState } from "react";
import { ApiUnavailableError, createReview, getReview, listReviews } from "./api";
import { generateLocalReview } from "./review-generator";
import { sampleReviews } from "./sample-data";
import type { DecisionState, ThesisInput, TradeReview } from "./types";

const STORAGE_KEY = "ambrosia.reviews.v1";
const REVIEW_ALPHA_LINKS_KEY = "ambrosia.review-alpha-links.v1";
const ALPHA_WRITEBACK_KEY = "ambrosia.alpha-writeback.v1";

export type ReviewAlphaLink = {
  source: "alpha";
  objectType: "hypothesis" | "signal";
  hypothesisId?: string;
  signalId?: string;
  signalVersion?: number;
  title?: string;
  signalFamily?: string;
  formula?: string;
  ticker?: string;
  createdAt: string;
};

export type AlphaWritebackState = {
  objectKey: string;
  objectType: "hypothesis" | "signal";
  hypothesisId?: string;
  signalId?: string;
  linkedReviewIds: string[];
  latestDecisionState?: DecisionState;
  latestOutcomeQuality?: string;
  lastReviewedAt?: string;
  overrideCount: number;
  outcomeCount: number;
};

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

function getReviewAlphaLinksMap(): Record<string, ReviewAlphaLink> {
  if (!canUseStorage()) return {};
  try {
    const raw = window.localStorage.getItem(REVIEW_ALPHA_LINKS_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, ReviewAlphaLink>;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function saveReviewAlphaLinksMap(map: Record<string, ReviewAlphaLink>) {
  if (!canUseStorage()) return;
  window.localStorage.setItem(REVIEW_ALPHA_LINKS_KEY, JSON.stringify(map));
}

export function setReviewAlphaLink(reviewId: string, link: ReviewAlphaLink) {
  const map = getReviewAlphaLinksMap();
  map[reviewId] = link;
  saveReviewAlphaLinksMap(map);
  window.dispatchEvent(new CustomEvent("ambrosia:reviews-updated"));
}

export function getReviewAlphaLink(reviewId: string): ReviewAlphaLink | null {
  const map = getReviewAlphaLinksMap();
  return map[reviewId] ?? null;
}

export function listReviewAlphaLinks(): Record<string, ReviewAlphaLink> {
  return getReviewAlphaLinksMap();
}

function getAlphaWritebackMap(): Record<string, AlphaWritebackState> {
  if (!canUseStorage()) return {};
  try {
    const raw = window.localStorage.getItem(ALPHA_WRITEBACK_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, AlphaWritebackState>;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function saveAlphaWritebackMap(map: Record<string, AlphaWritebackState>) {
  if (!canUseStorage()) return;
  window.localStorage.setItem(ALPHA_WRITEBACK_KEY, JSON.stringify(map));
}

function alphaObjectKey(link: ReviewAlphaLink): string | null {
  const objectId = link.objectType === "hypothesis" ? link.hypothesisId : link.signalId;
  if (!objectId) return null;
  return `${link.objectType}:${objectId}`;
}

export function upsertAlphaWritebackForReview(
  reviewId: string,
  link: ReviewAlphaLink,
  patch: Partial<Pick<AlphaWritebackState, "latestDecisionState" | "latestOutcomeQuality" | "lastReviewedAt">> & {
    incrementOverrideCount?: boolean;
    incrementOutcomeCount?: boolean;
  }
) {
  const key = alphaObjectKey(link);
  if (!key) return;

  const map = getAlphaWritebackMap();
  const existing = map[key];
  const linkedReviewIds = existing?.linkedReviewIds ?? [];
  const nextLinkedReviewIds = linkedReviewIds.includes(reviewId) ? linkedReviewIds : [...linkedReviewIds, reviewId];

  map[key] = {
    objectKey: key,
    objectType: link.objectType,
    hypothesisId: link.hypothesisId,
    signalId: link.signalId,
    linkedReviewIds: nextLinkedReviewIds,
    latestDecisionState: patch.latestDecisionState ?? existing?.latestDecisionState,
    latestOutcomeQuality: patch.latestOutcomeQuality ?? existing?.latestOutcomeQuality,
    lastReviewedAt: patch.lastReviewedAt ?? existing?.lastReviewedAt,
    overrideCount: (existing?.overrideCount ?? 0) + (patch.incrementOverrideCount ? 1 : 0),
    outcomeCount: (existing?.outcomeCount ?? 0) + (patch.incrementOutcomeCount ? 1 : 0)
  };

  saveAlphaWritebackMap(map);
  window.dispatchEvent(new CustomEvent("ambrosia:reviews-updated"));
}

export function listAlphaWritebacks(): Record<string, AlphaWritebackState> {
  return getAlphaWritebackMap();
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
