import type { CreateReviewInput, MobileDataset } from "./types";

const DATASET_CACHE_KEY = "ambrosia.mobile.datasetCache.v1";
const DRAFT_QUEUE_KEY = "ambrosia.mobile.draftQueue.v1";
const memoryStore = new Map<string, string>();

declare const require: (moduleName: string) => {
  default?: {
    getItem: (key: string) => Promise<string | null>;
    setItem: (key: string, value: string) => Promise<void>;
    removeItem: (key: string) => Promise<void>;
  };
};

export type FreshnessState = "live" | "cached" | "stale" | "fallback" | "queued";

export interface QueuedDraft {
  id: string;
  kind: "review";
  payload: CreateReviewInput;
  queuedAt: string;
  reason: string;
}

export async function readCachedDataset(): Promise<MobileDataset | null> {
  const raw = await safeGetItem(DATASET_CACHE_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as MobileDataset;
  } catch {
    await safeRemoveItem(DATASET_CACHE_KEY);
    return null;
  }
}

export async function writeCachedDataset(dataset: MobileDataset): Promise<void> {
  await safeSetItem(DATASET_CACHE_KEY, JSON.stringify(dataset));
}

export async function readQueuedDrafts(): Promise<QueuedDraft[]> {
  const raw = await safeGetItem(DRAFT_QUEUE_KEY);
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as QueuedDraft[]) : [];
  } catch {
    await safeRemoveItem(DRAFT_QUEUE_KEY);
    return [];
  }
}

export async function queueReviewDraft(payload: CreateReviewInput, reason: string): Promise<QueuedDraft> {
  const draft: QueuedDraft = {
    id: `draft-${Date.now()}`,
    kind: "review",
    payload,
    queuedAt: new Date().toISOString(),
    reason
  };
  const drafts = await readQueuedDrafts();
  await safeSetItem(DRAFT_QUEUE_KEY, JSON.stringify([draft, ...drafts]));
  return draft;
}

export async function removeQueuedDraft(draftId: string): Promise<void> {
  const drafts = await readQueuedDrafts();
  await safeSetItem(DRAFT_QUEUE_KEY, JSON.stringify(drafts.filter((draft) => draft.id !== draftId)));
}

async function safeGetItem(key: string): Promise<string | null> {
  const storage = getAsyncStorage();
  if (!storage) {
    return memoryStore.get(key) ?? null;
  }
  try {
    return await storage.getItem(key);
  } catch {
    return memoryStore.get(key) ?? null;
  }
}

async function safeSetItem(key: string, value: string): Promise<void> {
  memoryStore.set(key, value);
  const storage = getAsyncStorage();
  if (!storage) {
    return;
  }
  try {
    await storage.setItem(key, value);
  } catch {
    // Expo Go may not include this native module; memory keeps the session usable.
  }
}

async function safeRemoveItem(key: string): Promise<void> {
  memoryStore.delete(key);
  const storage = getAsyncStorage();
  if (!storage) {
    return;
  }
  try {
    await storage.removeItem(key);
  } catch {
    // See safeSetItem.
  }
}

function getAsyncStorage() {
  try {
    return require("@react-native-async-storage/async-storage").default ?? null;
  } catch {
    return null;
  }
}
