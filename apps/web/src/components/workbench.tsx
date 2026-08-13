"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Activity, ArrowRight, Beaker, CheckCircle2, Circle, Clock3, Download, RefreshCw, ShieldCheck, SlidersHorizontal } from "lucide-react";
import {
  attachResearchObjectReference,
  createAlphaHypothesis,
  createAgentOperation,
  admitAgentOperationProposal,
  cancelAgentOperation,
  continueAgentOperation,
  fallbackAgentOperation,
  createPacket,
  createSignal,
  derivePacketConfidence,
  evaluatePacketRisk,
  selectiveIntegratePacket,
  generateReport as generatePacketReport,
  generateReportDiff,
  getApiBaseUrl,
  getAgentOperation,
  getAgentOperationProposal,
  getDeploymentCapabilities,
  getProviderStatus,
  getMarketSnapshot,
  getMarketTechnicals,
  getPacket,
  getSentiment,
  preparePacketBacktest,
  linkAlphaHypothesisSignal,
  linkSignalReview,
  listResearchObjectReferences,
  recordDecision,
  recordPacketDecision,
  recordPacketOutcome,
  recordProductEvent,
  refreshPacketMetrics,
  rollbackAgentOperationProposal,
  runPacketAgents,
  writebackSignalDecision,
  writebackSignalOutcome,
  type AgentOperation,
  ApiRequestError,
  ApiProblemError,
  type AdmissionRequest,
  type OllamaModelPolicy,
  type OllamaWorkerReadiness,
  type PacketMutationProposal,
  type ResearchObjectReference,
  TERMINAL_AGENT_OPERATION_STATES
} from "@/lib/api";
import {
  getLocalReviews,
  getReviewAlphaLink,
  listAlphaWritebacks,
  listReviewAlphaLinks,
  loadReviewArchive,
  resolveReview,
  setReviewAlphaLink,
  upsertAlphaWritebackForReview,
  upsertLocalReview,
  type ReviewAlphaLink
} from "@/lib/review-store";
import { sampleReviews } from "@/lib/sample-data";
import { isFeatureEnabled } from "@/lib/route-availability";
import type {
  AuditEvent,
  Claim,
  DecisionPacket,
  DecisionState,
  MarketSnapshot,
  ProviderMode,
  ReportArtifact,
  ReportDiff,
  ReviewStatus,
  SentimentData,
  SourcePointer,
  TechnicalIndicators,
  TradeReview
} from "@/lib/types";
import { Badge, Panel, cn } from "./ui";

type ActionResult = "ok" | "queued" | "blocked" | "fallback" | "skipped";
type ReportGenerationResult = { result: ActionResult; report: ReportArtifact | null };
type RunbookStepId = "intake" | "market" | "agents" | "risk" | "confidence" | "decision" | "outcome" | "report";
type RunbookStatus = "idle" | "running" | "manual_required" | "complete" | "failed";
type RunbookStepResult = ActionResult | "manual_required";

type LiveMarketData = {
  snapshot: MarketSnapshot | null;
  technicals: TechnicalIndicators | null;
  sentiment: SentimentData | null;
  ticker: string;
  fetchedAt: string;
};

type RunbookRunState = {
  status: RunbookStatus;
  currentStepId: RunbookStepId | null;
  message: string;
  startedAt?: string;
  completedAt?: string;
  error?: string;
};

type RunbookStep = {
  id: RunbookStepId;
  label: string;
  done: boolean;
  detail: string;
  actionLabel: string;
  endpoint: string;
  artifact: string;
  auditEvents: string[];
  latestAudit: AuditEvent | null;
  manualGate?: string;
};

type WorkflowStage = {
  status: ReviewStatus;
  label: string;
  summary: string;
};

type AlphaDecaySnapshot = {
  signalId: string;
  decayDetected: boolean;
  recommendedAction: string;
};
type SignalDecisionAction = "BUY" | "SELL" | "HOLD" | "HEDGE" | "RISK_ADJUST" | "BLOCK" | "RETIRE";

type SignalExecutionReadiness = "not_executable" | "paper_trade_ready" | "execution_candidate" | "execution_blocked";

const statusLabels: Record<ReviewStatus, string> = {
  intake: "Intake",
  retrieval: "Retrieval",
  adversarial_review: "Adversarial critique",
  validation: "Validation gate",
  tradeability: "Tradeability",
  synthesis: "Synthesis",
  decision_recorded: "Decision recorded"
};

const statusOrder: ReviewStatus[] = ["intake", "retrieval", "adversarial_review", "validation", "tradeability", "synthesis", "decision_recorded"];
const expectedAgentRoles = ["marketData", "technical", "sentiment", "interMarket", "fundamental", "quant", "bull", "bear", "risk", "pmSynthesis"];
const providerModes: ProviderMode[] = ["hybrid", "ollama", "hosted", "deterministic"];

const decisionLabels: Record<DecisionState, string> = {
  pursue: "Pursue",
  watch: "Watch",
  reject: "Reject",
  needs_more_data: "Needs more data"
};

const signalDecisionActions: Record<DecisionState, SignalDecisionAction> = {
  pursue: "BUY",
  watch: "HOLD",
  needs_more_data: "HOLD",
  reject: "BLOCK"
};

const signalDecisionActionOptions: Array<{ action: SignalDecisionAction; label: string; summary: string }> = [
  { action: "BUY", label: "Buy", summary: "Add or initiate long exposure." },
  { action: "SELL", label: "Sell", summary: "Exit, reduce, or express a short/avoid stance." },
  { action: "HOLD", label: "Hold", summary: "Maintain posture and monitor." },
  { action: "HEDGE", label: "Hedge", summary: "Offset a defined exposure without rejecting the thesis." },
  { action: "RISK_ADJUST", label: "Risk adjust", summary: "Resize, constrain, or request tighter controls." },
  { action: "BLOCK", label: "Block", summary: "Prevent action until required evidence or gates clear." },
  { action: "RETIRE", label: "Retire", summary: "Remove a decayed or failed signal from active use." }
];

function readinessRemediation(readiness: OllamaWorkerReadiness | null): string {
  const reason = readiness?.reasonCode ?? "worker_offline";
  if (reason === "no_enrolled_worker") {
    return "Create a local worker credential in Admin, install the worker beside Ollama, then rerun preflight.";
  }
  if (reason === "worker_revoked") {
    return "The worker credential was revoked. Rotate or create a new credential in Admin and restart the worker.";
  }
  if (reason === "digest_mismatch") {
    return "Worker is online but does not advertise the selected model digest. Pull the approved model digest or change model policy.";
  }
  if (reason === "preflight_incomplete") {
    return "Worker found, but preflight is incomplete. Run the worker diagnose/preflight sequence and retry.";
  }
  if (reason === "model_policy_ambiguous") {
    return "No unambiguous default model policy is configured. Select a policy digest or configure a default digest.";
  }
  if (reason === "tenant_identity_required") {
    return "Sign in to an organization account so worker readiness can be evaluated for the tenant.";
  }
  if (reason === "ready") {
    return "Worker is ready.";
  }
  return "Worker is enrolled but not fresh. Keep Ollama and the local worker process running and connected.";
}

function actionableApiError(error: unknown): string {
  if (error instanceof ApiProblemError) {
    const context = [
      error.problem.dependency ? `dependency=${error.problem.dependency}` : "",
      error.problem.operationId ? `operation=${error.problem.operationId}` : "",
      error.problem.packetId ? `packet=${error.problem.packetId}` : "",
      error.problem.requestId ? `request=${error.problem.requestId}` : "",
    ].filter(Boolean);
    const retry = error.problem.retryable ? " Retry is safe." : " Retry requires resolving this condition.";
    return `${error.problem.code}: ${error.message}.${context.length ? ` (${context.join("; ")})` : ""}${retry}`;
  }
  if (error instanceof ApiRequestError) {
    const request = error.requestId ? ` Request ${error.requestId}.` : "";
    const retry = error.retryable ? " Retry is safe." : " Retry requires resolving this condition.";
    return `${error.code}: ${error.message}.${request}${retry}`;
  }
  return error instanceof Error ? error.message : "Unknown request failure";
}

export function Workbench({ initialReviewId }: { initialReviewId?: string } = {}) {
  const governedReportExportEnabled = isFeatureEnabled("review-export");
  const [reviews, setReviews] = useState<TradeReview[]>(() => mergeReviews(getLocalReviews(), sampleReviews));
  const [packetIdsByReviewId, setPacketIdsByReviewId] = useState<Record<string, string>>({});
  const [activeId, setActiveId] = useState(() => {
    const initialReviews = mergeReviews(getLocalReviews(), sampleReviews);
    return initialReviewId && initialReviews.some((review) => review.id === initialReviewId) ? initialReviewId : initialReviews[0]?.id ?? "";
  });
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [activeAlphaLink, setActiveAlphaLink] = useState<ReviewAlphaLink | null>(null);
  const [researchReferences, setResearchReferences] = useState<ResearchObjectReference[]>([]);
  const [activeAlphaDecay, setActiveAlphaDecay] = useState<AlphaDecaySnapshot | null>(null);
  const [actionFeedback, setActionFeedback] = useState<{ tone: "neutral" | "good" | "warn"; message: string } | null>(null);
  const [liveMarketData, setLiveMarketData] = useState<LiveMarketData | null>(null);
  const [activePacketData, setActivePacketData] = useState<DecisionPacket | null>(null);
  const [reportArtifact, setReportArtifact] = useState<ReportArtifact | null>(null);
  const [reportDiff, setReportDiff] = useState<ReportDiff | null>(null);
  const [providerMode, setProviderMode] = useState<ProviderMode>("hybrid");
  const [ollamaModelPolicies, setOllamaModelPolicies] = useState<OllamaModelPolicy[]>([]);
  const [selectedOllamaDigest, setSelectedOllamaDigest] = useState("");
  const [ollamaWorkerReadiness, setOllamaWorkerReadiness] = useState<OllamaWorkerReadiness | null>(null);
  const [agentOperation, setAgentOperation] = useState<AgentOperation | null>(null);
  const [agentProposal, setAgentProposal] = useState<PacketMutationProposal | null>(null);
  const [runbookState, setRunbookState] = useState<RunbookRunState>({
    status: "idle",
    currentStepId: null,
    message: "Ready to run the next checkpoint."
  });
  const activeReview = reviews.find((review) => review.id === activeId) ?? reviews[0];

  useEffect(() => {
    let cancelled = false;
    Promise.all([getProviderStatus(), getDeploymentCapabilities()])
      .then(([status]) => {
        if (cancelled) return;
        setOllamaModelPolicies(status.ollamaModelPolicies);
        setOllamaWorkerReadiness(status.ollamaWorkerReadiness);
        setSelectedOllamaDigest((current) =>
          status.ollamaModelPolicies.some((policy) => policy.digest === current)
            ? current
            : (status.ollamaModelPolicies.find((policy) => policy.default)?.digest ?? status.ollamaModelPolicies[0]?.digest ?? "")
        );
      })
      .catch((error) => {
        if (!cancelled) {
          setOllamaModelPolicies([]);
          setSelectedOllamaDigest("");
          setOllamaWorkerReadiness(null);
          setActionFeedback({ tone: "warn", message: actionableApiError(error) });
        }
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!selectedOllamaDigest) return;
    let cancelled = false;
    const selectedPolicy = ollamaModelPolicies.find((policy) => policy.digest === selectedOllamaDigest);
    const requiredContextLength = selectedPolicy?.contextLength;
    getProviderStatus(selectedOllamaDigest, requiredContextLength)
      .then((status) => {
        if (!cancelled) setOllamaWorkerReadiness(status.ollamaWorkerReadiness);
      })
      .catch(() => {
        if (!cancelled) setOllamaWorkerReadiness(null);
      });
    return () => { cancelled = true; };
  }, [selectedOllamaDigest, ollamaModelPolicies]);

  useEffect(() => {
    let cancelled = false;
    loadReviewArchive()
      .then(async ({ reviews: archiveReviews }) => {
        if (cancelled) return;
        let nextReviews = archiveReviews.length > 0 ? archiveReviews : sampleReviews;
        if (initialReviewId && !nextReviews.some((review) => review.id === initialReviewId)) {
          const resolved = await resolveReview(initialReviewId);
          if (resolved) {
            nextReviews = mergeReviews([resolved], nextReviews);
          }
        }
        if (!cancelled) {
          setReviews(nextReviews);
          setActiveId((currentActiveId) => (initialReviewId && nextReviews.some((review) => review.id === initialReviewId) ? initialReviewId : (currentActiveId || nextReviews[0]?.id || "")));
        }
      })
      .catch(() => {
        // The review route remains usable with bundled sample reviews when the API is unavailable.
      });
    return () => {
      cancelled = true;
    };
  }, [initialReviewId]);

  useEffect(() => {
    let cancelled = false;
    setLiveMarketData(null);
    setActivePacketData(null);
    setAgentOperation(null);
    setAgentProposal(null);
    setReportArtifact(null);
    setReportDiff(null);
    const localLink = activeId ? getReviewAlphaLink(activeId) : null;
    setActiveAlphaLink(localLink);
    setResearchReferences([]);
    setActiveAlphaDecay(null);
    setRunbookState({
      status: "idle",
      currentStepId: null,
      message: "Ready to run the next checkpoint."
    });
    setActionFeedback(null);
    if (activeId) {
      listResearchObjectReferences(activeId)
        .then((references) => {
          if (cancelled) return;
          setResearchReferences(references);
          const signalReference = references.find((reference) => reference.objectType === "signal");
          if (signalReference) setActiveAlphaLink(linkFromResearchReference(signalReference));
        })
        .catch(() => {
          // Local linkage remains a development fallback when the lifecycle API is unavailable.
        });
    }
    return () => {
      cancelled = true;
    };
  }, [activeId]);

  useEffect(() => {
    const packetId = packetIdsByReviewId[activeId] ?? (activeId ? `pkt-${activeId}` : "");
    if (!packetId) return;
    const savedId = window.localStorage.getItem(`ambrosia:ollama-operation:${packetId}`);
    if (!savedId) return;
    getAgentOperation(savedId).then(setAgentOperation).catch(() => {
      window.localStorage.removeItem(`ambrosia:ollama-operation:${packetId}`);
    });
  }, [activeId, packetIdsByReviewId]);

  useEffect(() => {
    if (!agentOperation || TERMINAL_AGENT_OPERATION_STATES.has(agentOperation.state)) return;
    let cancelled = false;
    let delay = 1000;
    let timer: number;
    const poll = async () => {
      try {
        const current = await getAgentOperation(agentOperation.id);
        if (cancelled) return;
        setAgentOperation(current);
        if (current.state === "completed") {
          if (current.proposalId) {
            const proposal = await getAgentOperationProposal(current.id);
            if (!cancelled) setAgentProposal(proposal);
          }
          const packet = await getPacket(current.packetId);
          if (!cancelled) syncReviewFromPacket(activeId, packet);
          if (!cancelled && current.admissionState === "awaiting_human_review") {
            setRunbookState({
              status: "manual_required",
              currentStepId: "agents",
              message: "Ollama inference completed; inspect and admit or reject the governed proposal.",
              completedAt: new Date().toISOString()
            });
          } else if (!cancelled && current.resultPacketVersion) {
            setRunbookState({
              status: "complete",
              currentStepId: "agents",
              message: `Ollama proposal admitted to packet v${current.resultPacketVersion}.`,
              completedAt: new Date().toISOString()
            });
          }
          return;
        }
        if (!TERMINAL_AGENT_OPERATION_STATES.has(current.state)) {
          delay = Math.min(10000, Math.round(delay * 1.5));
          timer = window.setTimeout(poll, delay);
        }
      } catch {
        if (!cancelled) timer = window.setTimeout(poll, Math.min(10000, delay * 2));
      }
    };
    timer = window.setTimeout(poll, delay);
    return () => { cancelled = true; window.clearTimeout(timer); };
  // Poll identity/state are the intentional restart boundaries; syncReviewFromPacket is render-local.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agentOperation?.id, agentOperation?.state, activeId]);

  useEffect(() => {
    if (!agentOperation?.proposalId) return;
    let cancelled = false;
    getAgentOperationProposal(agentOperation.id)
      .then((proposal) => { if (!cancelled) setAgentProposal(proposal); })
      .catch(() => { if (!cancelled) setAgentProposal(null); });
    return () => { cancelled = true; };
  }, [agentOperation?.id, agentOperation?.proposalId, agentOperation?.admissionState]);

  useEffect(() => {
    if (!initialReviewId) return;
    if (reviews.some((review) => review.id === initialReviewId)) {
      setActiveId(initialReviewId);
    }
  }, [initialReviewId, reviews]);

  useEffect(() => {
    const signalId = activeAlphaLink?.signalId;
    const apiBaseUrl = getApiBaseUrl();
    if (!signalId || !apiBaseUrl) {
      setActiveAlphaDecay(null);
      return;
    }

    let cancelled = false;
    fetch(`${apiBaseUrl}/signals/${encodeURIComponent(signalId)}/alpha-decay`)
      .then((response) => {
        if (!response.ok) throw new Error(`alpha-decay ${response.status}`);
        return response.json() as Promise<Record<string, unknown>>;
      })
      .then((payload) => {
        if (cancelled) return;
        setActiveAlphaDecay({
          signalId,
          decayDetected: payload.decayDetected === true,
          recommendedAction: typeof payload.recommendedAction === "string" ? payload.recommendedAction : "n/a"
        });
      })
      .catch(() => {
        if (!cancelled) setActiveAlphaDecay(null);
      });

    return () => {
      cancelled = true;
    };
  }, [activeAlphaLink]);

  const recentReviews = useMemo(() => reviews.slice(0, 4), [reviews]);

  function updateReview(reviewId: string, updater: (review: TradeReview) => TradeReview) {
    setReviews((current) =>
      current.map((review) => {
        if (review.id !== reviewId) return review;
        const updated = updater(review);
        upsertLocalReview(updated);
        return updated;
      })
    );
  }

  function updateConfidence(value: number) {
    updateReview(activeReview.id, (review) => ({
      ...review,
      confidence: value
    }));
  }

  async function updateDecision(
    decisionState: DecisionState,
    rationale?: string,
    suggestedDecision?: DecisionState | null,
    pursueGateViolations?: string[]
  ) {
    if (decisionState === "pursue" && pursueGateViolations && pursueGateViolations.length > 0) {
      appendAuditEvent("decision.pursue.blocked", `Hard policy blocked pursue: ${pursueGateViolations.join(" ")}`);
      setActionFeedback({
        tone: "warn",
        message: `Hard policy blocked Pursue: ${pursueGateViolations.join(" ")}`
      });
      return;
    }

    const override = suggestedDecision && decisionState !== suggestedDecision;
    const decisionRationale = rationale?.trim() || `Human selected ${decisionLabels[decisionState]}.`;
    setActiveAction("Record governed decision");
    try {
      const { reviewId, packetId } = await ensurePacketForReview(activeReview);
      const packet = await recordPacketDecision(packetId, {
        decision_state: decisionState,
        rationale: decisionRationale,
        actor: "ambrosia-workbench-human"
      });
      syncReviewFromPacket(reviewId, packet);
      await recordDecision(reviewId, decisionState).catch(() => {
        // The packet is the governed source of truth; legacy review writeback is best effort.
      });
      void recordProductEvent("review_completed", "workbench", {
        objectReference: reviewId,
        properties: { mode: "governed" },
      });
      setActionFeedback({ tone: "good", message: `Governed decision recorded: ${decisionLabels[decisionState]}.` });
    } catch (error) {
      const message = error instanceof Error ? error.message : "unknown error";
      appendAuditEvent("decision.governed.blocked", `Governed decision was not recorded: ${message}`);
      setActionFeedback({ tone: "warn", message: `Decision blocked: ${message}` });
      setActiveAction(null);
      return;
    }

    updateReview(activeReview.id, (review) => ({
      ...review,
      decisionState,
      status: "decision_recorded",
      audit: [
        ...review.audit,
        ...(override
          ? [
              {
                id: `audit-${Date.now()}-override`,
                timestamp: new Date().toLocaleTimeString(),
                eventType: "decision.override",
                detail: `Override rationale: ${rationale?.trim() ? rationale.trim() : "No rationale provided."}. Suggested ${decisionLabels[suggestedDecision]}; chosen ${decisionLabels[decisionState]}.`
              } as AuditEvent
            ]
          : []),
        {
          id: `audit-${Date.now()}`,
          timestamp: new Date().toLocaleTimeString(),
          eventType: "decision.recorded",
          detail: `Human decision captured: ${decisionLabels[decisionState]}${rationale?.trim() ? ` (${rationale.trim()})` : ""}`
        }
      ]
    }));
    setActiveAction(null);

    if (activeAlphaLink) {
      upsertAlphaWritebackForReview(activeReview.id, activeAlphaLink, {
        latestDecisionState: decisionState,
        lastReviewedAt: new Date().toISOString(),
        incrementOverrideCount: Boolean(override)
      });

      if (activeAlphaLink.signalId) {
        const signalId = activeAlphaLink.signalId;
        const reviewId = activeReview.id;
        const hypothesisId = activeAlphaLink.hypothesisId;
        void (async () => {
          try {
            await linkSignalReview(signalId, {
              reviewId,
              hypothesisId,
              signalVersion: activeAlphaLink.signalVersion
            });
            await writebackSignalDecision(signalId, {
              reviewId,
              signalVersion: activeAlphaLink.signalVersion,
              decisionState,
              decisionAction: deriveSignalDecisionAction(activeReview, decisionState, activeAlphaDecay),
              decisionUse: ["buy", "sell", "hold", "hedge", "risk_adjust"],
              evidenceLinks: [`review:${reviewId}`],
              verifierStatus: "passed",
              reviewDate: new Date().toISOString().slice(0, 10),
              rationale,
              overrideUsed: Boolean(override)
            });
          } catch {
            // Keep workbench non-blocking when server-side writeback is unavailable.
          }
        })();
      }
    }
  }

  async function confirmSignalDecisionProposal(action: SignalDecisionAction, rationale?: string) {
    if (!activeReview.decisionState) {
      setActionFeedback({ tone: "warn", message: "Record a review decision before writing a signal action." });
      return;
    }

    const reviewId = activeReview.id;
    const readiness = resolveExecutionReadiness(action, activeReview, activePacketData, pursueGateViolations);
    const decisionRationale = rationale?.trim() || `Signal Decision Proposal accepted: ${action}.`;

    setActiveAction("Write signal decision");
    setActionFeedback({ tone: "neutral", message: activeAlphaLink?.signalId ? `Writing ${action} to linked signal ${activeAlphaLink.signalId}...` : `Creating a linked signal, then writing ${action}...` });
    try {
      let signalLink = activeAlphaLink?.signalId ? activeAlphaLink : await createSignalLinkForReview(activeReview);
      let signalId: string;
      try {
        signalId = await writeSignalDecisionToLink(signalLink, action, readiness, decisionRationale);
      } catch (error) {
        if (!activeAlphaLink?.signalId || signalLink.signalId !== activeAlphaLink.signalId) {
          throw error;
        }
        appendAuditEvent("signal.decision.writeback.retry", `Linked signal ${activeAlphaLink.signalId} was unavailable; creating a fresh signal before retrying.`);
        signalLink = await createSignalLinkForReview(activeReview);
        signalId = await writeSignalDecisionToLink(signalLink, action, readiness, decisionRationale);
      }
      upsertAlphaWritebackForReview(reviewId, signalLink, {
        latestDecisionState: activeReview.decisionState,
        lastReviewedAt: new Date().toISOString()
      });
      setActiveAlphaLink(signalLink);
      appendAuditEvent("signal.decision.writeback", `Signal Decision Proposal wrote ${action} to ${signalId}; readiness ${readiness}.`);
      setActionFeedback({ tone: "good", message: `Signal updated: ${action} / ${readiness}.` });
    } catch (error) {
      appendAuditEvent("signal.decision.writeback.failed", `Signal Decision Proposal failed for ${activeAlphaLink?.signalId ?? "new signal"}: ${error instanceof Error ? error.message : "unknown error"}.`);
      setActionFeedback({ tone: "warn", message: `Signal writeback failed: ${error instanceof Error ? error.message : "unknown error"}` });
    } finally {
      setActiveAction(null);
    }
  }

  async function writeSignalDecisionToLink(
    signalLink: ReviewAlphaLink,
    action: SignalDecisionAction,
    readiness: SignalExecutionReadiness,
    decisionRationale: string
  ) {
    if (!activeReview.decisionState) {
      throw new Error("Review decision is missing.");
    }
    const signalId = signalLink.signalId;
    if (!signalId) {
      throw new Error("Signal link does not include a signal id.");
    }
    const reviewId = activeReview.id;
    await attachResearchObjectReference(reviewId, {
      objectType: "signal",
      objectId: signalId,
      versionId: signalLink.signalVersion ?? "current",
      relationshipType: "research_evidence"
    });
    await linkSignalReview(signalId, {
      reviewId,
      hypothesisId: signalLink.hypothesisId,
      signalVersion: signalLink.signalVersion
    });
    await writebackSignalDecision(signalId, {
      reviewId,
      signalVersion: signalLink.signalVersion,
      decisionState: activeReview.decisionState,
      decisionAction: action,
      decisionUse: ["buy", "sell", "hold", "hedge", "risk_adjust"],
      evidenceLinks: [`review:${reviewId}`],
      verifierStatus: activeReview.validation.status === "specified" ? "passed" : "blocked",
      reviewDate: new Date().toISOString().slice(0, 10),
      rationale: decisionRationale,
      executionReadiness: readiness,
      outcomeWritebackRequired: true,
      decisionQuality: deriveDecisionQuality(activeReview)
    });
    return signalId;
  }

  async function createSignalLinkForReview(review: TradeReview): Promise<ReviewAlphaLink> {
    const ticker = safeMinimumText(review.ticker.toUpperCase(), "UNKNOWN", 1);
    const thesis = safeMinimumText(review.thesis, `${ticker} review-derived signal thesis`, 8);
    const horizon = safeMinimumText(review.timeHorizon, "20d", 1);
    const formula = safeMinimumText(review.intendedExpression, `review_expression:${ticker}`, 3);
    const disconfirmingTest = safeMinimumText(review.disconfirmingTest, "Review requires a disconfirming test before promotion.", 3);
    const nullHypothesis = safeMinimumText(review.validation.nullHypothesis, "No out-of-sample decision value after costs.", 3);
    const signalFamily = safeMinimumText(inferSignalFamily(thesis), "review-derived", 2);
    const title = `${ticker} Review-Derived Thesis`;
    const hypothesis = await createAlphaHypothesis({
      title,
      signalFamily,
      universe: [ticker],
      horizon,
      thesis,
      planQuality: "P2",
      disconfirmingTests: [disconfirmingTest, nullHypothesis],
      costModel: "10 bps round-trip",
      owner: "research"
    });
    const hypothesisId = readText(hypothesis.hypothesisId);

    const signal = await createSignal({
      name: `${ticker} Review Signal`,
      universe: [ticker],
      horizon,
      formula,
      costModel: "10 bps round-trip",
      benchmark: "SPY",
      validationGates: ["point_in_time", "costs", "walk_forward"]
    });
    const signalId = readText(signal.signalId);
    const signalVersion = readVersion(signal.activeVersion, signal.version);

    if (!hypothesisId || !signalId) {
      throw new Error("Alpha hypothesis or signal id was missing from the API response.");
    }

    await linkAlphaHypothesisSignal(hypothesisId, { signalId, signalVersion });
    const link: ReviewAlphaLink = {
      source: "alpha",
      objectType: "signal",
      hypothesisId,
      signalId,
      signalVersion,
      title,
      signalFamily,
      formula,
      ticker,
      createdAt: new Date().toISOString()
    };
    setReviewAlphaLink(review.id, link);
    appendAuditEvent("signal.created", `Signal Decision Proposal created ${signalId} and linked it to ${review.id}.`);
    return link;
  }

  function appendAuditEvent(eventType: string, detail: string) {
    if (!activeReview) return;
    updateReview(activeReview.id, (review) => ({
      ...review,
      audit: [
        ...review.audit,
        {
          id: `audit-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          timestamp: new Date().toLocaleTimeString(),
          eventType,
          detail
        }
      ]
    }));
  }

  async function runAction(label: string, action: () => Promise<ActionResult>) {
    setActiveAction(label);
    setActionFeedback({ tone: "neutral", message: `${label} running...` });
    try {
      const result = await action();
      if (result === "ok") {
        setActionFeedback({ tone: "good", message: `${label} completed. The workflow trace was updated.` });
      } else if (result === "fallback") {
        setActionFeedback({ tone: "warn", message: `${label} could not reach every API path, so the review stayed in fallback-safe mode.` });
      } else {
        setActionFeedback({ tone: "warn", message: `${label} skipped because required packet context was missing.` });
      }
    } catch (error) {
      setActionFeedback({
        tone: "warn",
        message: `${label} failed: ${error instanceof Error ? error.message : "unknown error"}`
      });
    } finally {
      setActiveAction(null);
    }
  }

  function syncReviewFromPacket(reviewId: string, packet: DecisionPacket) {
    setActivePacketData(packet);
    updateReview(reviewId, (review) => ({
      ...review,
      confidence: packet.confidence,
      status: packet.status,
      decisionState: packet.decisionState,
      followUpDate: packet.followUpDate,
      audit: packet.audit
    }));
  }

  function buildPacketShell(review: TradeReview): DecisionPacket {
    return {
      id: `pkt-${review.id}`,
      schemaVersion: "packet.v1",
      workflowVersion: "quant-agent.v1",
      contractVersion: "selective-integration.v1",
      packetVersion: 1,
      workflowRunId: null,
      title: review.title,
      thesis: review.thesis,
      ticker: review.ticker,
      assetClass: review.assetClass,
      timeHorizon: review.timeHorizon,
      intendedExpression: review.intendedExpression,
      status: review.status,
      decisionState: review.decisionState,
      confidence: review.confidence,
      trialCountImpact: review.trialCountImpact,
      followUpDate: review.followUpDate,
      createdAt: review.createdAt,
      claims: review.claims,
      strongestCritique: review.strongestCritique,
      disconfirmingTest: review.disconfirmingTest,
      historicalAnalogue: review.historicalAnalogue,
      validation: review.validation,
      tradeability: review.tradeability,
      sources: review.sources,
      audit: review.audit,
      provenance: [],
      disconfirmationResult: null,
      riskGateResult: null,
      memoryRecords: [],
      integrationStatus: {
        state: "not_started",
        completedStages: [],
        staleStages: [],
        blockers: [],
        nextAction: "Attach provenance and run selective integration.",
        policyVersion: "selective-integration.v1",
        updatedAt: null
      },
      marketSnapshot: null,
      technicals: null,
      sentiment: null,
      interMarket: null,
      fundamentals: null,
      backtestPlan: null,
      backtestResult: null,
      riskMonitor: null,
      portfolioContext: null,
      confidenceBreakdown: null,
      agentOutputs: null,
      coordinatorVersion: "coordinator.v1",
      providerInfo: null
    };
  }

  async function ensurePacketForReview(review: TradeReview): Promise<{ reviewId: string; packetId: string; packet: DecisionPacket }> {
    const cachedPacketId = packetIdsByReviewId[review.id];
    if (cachedPacketId) {
      const existing = await getPacket(cachedPacketId);
      return { reviewId: review.id, packetId: cachedPacketId, packet: existing };
    }

    const packetId = `pkt-${review.id}`;
    try {
      const existing = await getPacket(packetId);
      setPacketIdsByReviewId((current) => ({ ...current, [review.id]: packetId }));
      return { reviewId: review.id, packetId, packet: existing };
    } catch {
      const created = await createPacket(buildPacketShell(review));
      setPacketIdsByReviewId((current) => ({ ...current, [review.id]: created.id }));
      return { reviewId: review.id, packetId: created.id, packet: created };
    }
  }

  async function refreshMarketMetrics(): Promise<ActionResult> {
    if (!activeReview?.ticker) {
      appendAuditEvent("metrics.refresh.skipped", "No ticker available for metrics refresh.");
      return "skipped";
    }

    try {
      const { reviewId, packetId } = await ensurePacketForReview(activeReview);
      const packet = await refreshPacketMetrics(packetId);
      syncReviewFromPacket(reviewId, packet);
      setLiveMarketData({
        snapshot: packet.marketSnapshot ?? null,
        technicals: packet.technicals ?? null,
        sentiment: packet.sentiment ?? null,
        ticker: activeReview.ticker,
        fetchedAt: new Date().toISOString()
      });
      appendAuditEvent("metrics.refresh", `Packet metrics refreshed for ${activeReview.ticker} via ${packetId}.`);
      return "ok";
    } catch {
      appendAuditEvent("metrics.refresh.fallback", `Metrics refresh API unavailable for ${activeReview.ticker}; local workflow remains active.`);
      return "fallback";
    }
  }

  async function prepareBacktest(): Promise<ActionResult> {
    if (!activeReview) {
      appendAuditEvent("backtest.prepare.skipped", "Backtest preparation skipped because no active review is selected.");
      return "skipped";
    }
    try {
      const { reviewId, packetId } = await ensurePacketForReview(activeReview);
      const packet = await preparePacketBacktest(packetId, {
        lookbackPeriod: 252,
        holdingPeriodDays: 10,
        riskConstraints: ["Max loss 8%", "Liquidity floor enforced"]
      });
      syncReviewFromPacket(reviewId, packet);
      appendAuditEvent("backtest.prepare", `Backtest plan prepared for ${activeReview.ticker} with status ${packet.backtestPlan?.status ?? "unknown"}.`);
      return "ok";
    } catch {
      appendAuditEvent("backtest.prepare.fallback", "Backtest preparation endpoint unavailable; packet flow remains in local mode.");
      return "fallback";
    }
  }

  async function evaluateRisk(): Promise<ActionResult> {
    if (!activeReview) {
      appendAuditEvent("risk.evaluate.skipped", "Risk evaluation skipped because no active review is selected.");
      return "skipped";
    }
    try {
      const { reviewId, packetId } = await ensurePacketForReview(activeReview);
      const packet = await evaluatePacketRisk(packetId, {
        activePositionSize: 250000,
        maxDrawdownThreshold: 0.12
      });
      syncReviewFromPacket(reviewId, packet);
      appendAuditEvent("risk.evaluate", `Risk evaluated for ${activeReview.ticker}: status ${packet.riskMonitor?.status ?? "unknown"}.`);
      return "ok";
    } catch {
      appendAuditEvent("risk.evaluate.fallback", "Risk evaluation endpoint unavailable; local advisory workflow remains active.");
      return "fallback";
    }
  }

  async function runAgentSwarm(): Promise<ActionResult> {
    if (!activeReview) {
      appendAuditEvent("agents.run.skipped", "Agent swarm run skipped because no active review is selected.");
      return "skipped";
    }

    try {
      const { reviewId, packetId } = await ensurePacketForReview(activeReview);
      if (providerMode === "ollama") {
        if (agentOperation && !TERMINAL_AGENT_OPERATION_STATES.has(agentOperation.state)) return "queued";
        if (!selectedOllamaDigest) throw new Error("No approved active Ollama model policy is available");
        if (!ollamaWorkerReadiness?.ready) {
          const reason = ollamaWorkerReadiness?.reasonCode ?? "worker_offline";
          const remediation = readinessRemediation(ollamaWorkerReadiness);
          appendAuditEvent("agents.run.blocked", `Ollama review blocked: ${reason}.`);
          setActionFeedback({ tone: "warn", message: `Ollama review blocked: ${reason.replaceAll("_", " ")}. ${remediation}` });
          return "blocked";
        }
        const operation = await createAgentOperation(
          packetId,
          `${reviewId}:${packetId}:ollama:${selectedOllamaDigest}`,
          selectedOllamaDigest
        );
        setAgentOperation(operation);
        window.localStorage.setItem(`ambrosia:ollama-operation:${packetId}`, operation.id);
        appendAuditEvent("agents.run.queued", `Ollama review queued as ${operation.id}.`);
        return "queued";
      }
      const packet = await runPacketAgents(packetId, providerMode);
      syncReviewFromPacket(reviewId, packet);
      appendAuditEvent("agents.run", `Agent swarm completed for ${activeReview.ticker} using ${packet.providerInfo?.name ?? "unknown provider"}.`);
      return "ok";
    } catch (error) {
      const detail = actionableApiError(error);
      appendAuditEvent("agents.run.unavailable", `${detail}; keeping local workflow state without silent fallback.`);
      return "fallback";
    }
  }

  async function cancelOllamaOperation() {
    if (agentOperation) setAgentOperation(await cancelAgentOperation(agentOperation.id));
  }

  async function fallbackOllamaOperation() {
    if (!agentOperation) return;
    const fallback = await fallbackAgentOperation(agentOperation.id);
    setAgentOperation(fallback);
    const packet = await getPacket(fallback.packetId);
    syncReviewFromPacket(activeId, packet);
  }

  async function continueOllamaOperation() {
    if (agentOperation) setAgentOperation(await continueAgentOperation(agentOperation.id));
  }

  async function retryOllamaOperation() {
    if (!agentOperation) return;
    const operation = await createAgentOperation(agentOperation.packetId);
    setAgentOperation(operation);
    window.localStorage.setItem(`ambrosia:ollama-operation:${operation.packetId}`, operation.id);
  }

  async function refreshEvidenceAndRerunOllama(): Promise<ActionResult> {
    if (!activeReview) return "skipped";
    const { reviewId, packetId } = await ensurePacketForReview(activeReview);
    const refreshed = await refreshPacketMetrics(packetId);
    syncReviewFromPacket(reviewId, refreshed);
    const operation = await createAgentOperation(packetId, undefined, selectedOllamaDigest || undefined);
    setAgentOperation(operation);
    setAgentProposal(null);
    window.localStorage.setItem(`ambrosia:ollama-operation:${operation.packetId}`, operation.id);
    appendAuditEvent("agents.run.rerun", `Stale proposal recovery queued as ${operation.id} after evidence refresh.`);
    return "queued";
  }

  async function reviewOllamaProposal(body: AdmissionRequest) {
    if (!agentOperation) return;
    const operation = await admitAgentOperationProposal(agentOperation.id, body);
    setAgentOperation(operation);
    setAgentProposal(await getAgentOperationProposal(operation.id));
    if (operation.resultPacketVersion) {
      const packet = await getPacket(operation.packetId);
      syncReviewFromPacket(activeId, packet);
      setRunbookState({
        status: "complete",
        currentStepId: "agents",
        message: `Reviewed proposal committed to packet v${operation.resultPacketVersion}.`,
        completedAt: new Date().toISOString()
      });
    }
  }

  async function rollbackOllamaProposal(rationale: string) {
    if (!agentOperation?.resultPacketVersion) return;
    const operation = await rollbackAgentOperationProposal(
      agentOperation.id,
      agentOperation.resultPacketVersion,
      rationale
    );
    setAgentOperation(operation);
    setAgentProposal(await getAgentOperationProposal(operation.id));
    const packet = await getPacket(operation.packetId);
    syncReviewFromPacket(activeId, packet);
    setReportArtifact(null);
    setReportDiff(null);
  }

  async function deriveConfidenceFromMarket(): Promise<ActionResult> {
    if (!activeReview?.ticker) {
      appendAuditEvent("confidence.derive.skipped", "No ticker available for technicals inspection.");
      return "skipped";
    }

    try {
      const [sentimentResult, technicalsResult, snapshotResult] = await Promise.allSettled([
        getSentiment(activeReview.ticker),
        getMarketTechnicals(activeReview.ticker),
        getMarketSnapshot(activeReview.ticker)
      ]);
      const sentiment = sentimentResult.status === "fulfilled" ? sentimentResult.value : null;
      const technicals = technicalsResult.status === "fulfilled" ? technicalsResult.value : null;
      const snapshot = snapshotResult.status === "fulfilled" ? snapshotResult.value : null;
      const { reviewId, packetId } = await ensurePacketForReview(activeReview);
      const packet = await derivePacketConfidence(packetId, {
        technicalScore: technicals?.rsi !== null && technicals?.rsi !== undefined ? Math.round(technicals.rsi) : 66,
        sentimentScore: sentiment ? Math.round(sentiment.overallScore) : 50,
        blockers: sentiment?.sentiment === "bearish" ? ["Sentiment regime still bearish"] : []
      });
      syncReviewFromPacket(reviewId, packet);
      setLiveMarketData({ snapshot, technicals, sentiment, ticker: activeReview.ticker, fetchedAt: new Date().toISOString() });
      appendAuditEvent("confidence.derive", `Technicals reviewed and confidence derived for ${activeReview.ticker}: ${packet.confidence}%.`);
      return "ok";
    } catch {
      appendAuditEvent("confidence.derive.fallback", "Technicals inspection endpoint unavailable; keeping deterministic local view.");
      return "fallback";
    }
  }

  async function runSelectiveIntegration(): Promise<ActionResult> {
    if (!activeReview) {
      appendAuditEvent("selective.integration.skipped", "Selective integration skipped because no active review is selected.");
      return "skipped";
    }

    try {
      const { reviewId, packetId } = await ensurePacketForReview(activeReview);
      const packet = await selectiveIntegratePacket(packetId);
      syncReviewFromPacket(reviewId, packet);
      appendAuditEvent("selective.integration", `Selective integration completed for ${activeReview.ticker}: ${packet.disconfirmationResult?.status ?? "pending"}.`);
      return "ok";
    } catch {
      appendAuditEvent("selective.integration.blocked", "Selective integration endpoint unavailable; governed decision actions remain blocked.");
      return "fallback";
    }
  }

  async function recordOutcomeForDecision(): Promise<ActionResult> {
    if (!activeReview) {
      appendAuditEvent("outcome.recorded.skipped", "Outcome attribution skipped because no active review is selected.");
      return "skipped";
    }
    try {
      const { reviewId, packetId } = await ensurePacketForReview(activeReview);
      const packet = await recordPacketOutcome(packetId, {
        outcome: activeReview.decisionState ?? "watch",
        outcome_date: new Date().toISOString().slice(0, 10),
        pnl: 0,
        notes: "Outcome placeholder captured from focused review workbench."
      });
      syncReviewFromPacket(reviewId, packet);
      appendAuditEvent("outcome.recorded", `Outcome attribution recorded for ${activeReview.ticker}.`);
      void recordProductEvent("outcome_recorded", "workbench", {
        objectReference: reviewId,
        properties: { mode: "governed" },
      });

      if (activeAlphaLink) {
        const quality = packet.decisionState ? `decision_${packet.decisionState}` : "decision_unset";
        upsertAlphaWritebackForReview(activeReview.id, activeAlphaLink, {
          latestOutcomeQuality: quality,
          lastReviewedAt: new Date().toISOString(),
          incrementOutcomeCount: true
        });

        if (activeAlphaLink.signalId) {
          try {
            await linkSignalReview(activeAlphaLink.signalId, {
              reviewId: activeReview.id,
              hypothesisId: activeAlphaLink.hypothesisId,
              signalVersion: activeAlphaLink.signalVersion
            });
            await writebackSignalOutcome(activeAlphaLink.signalId, {
              reviewId: activeReview.id,
              signalVersion: activeAlphaLink.signalVersion,
              outcomeQuality: quality,
              lastReviewedAt: new Date().toISOString()
            });
          } catch {
            // Local writeback remains available when API persistence is unavailable.
          }
        }
      }

      return "ok";
    } catch {
      appendAuditEvent("outcome.recorded.fallback", "Outcome attribution endpoint unavailable; local decision memory retained.");
      if (activeAlphaLink) {
        const quality = activeReview.decisionState ? `decision_${activeReview.decisionState}` : "decision_unset";
        upsertAlphaWritebackForReview(activeReview.id, activeAlphaLink, {
          latestOutcomeQuality: quality,
          lastReviewedAt: new Date().toISOString(),
          incrementOutcomeCount: true
        });

        if (activeAlphaLink.signalId) {
          try {
            await linkSignalReview(activeAlphaLink.signalId, {
              reviewId: activeReview.id,
              hypothesisId: activeAlphaLink.hypothesisId,
              signalVersion: activeAlphaLink.signalVersion
            });
            await writebackSignalOutcome(activeAlphaLink.signalId, {
              reviewId: activeReview.id,
              signalVersion: activeAlphaLink.signalVersion,
              outcomeQuality: quality,
              lastReviewedAt: new Date().toISOString()
            });
          } catch {
            // Local writeback remains available when API persistence is unavailable.
          }
        }
      }
      return "fallback";
    }
  }

  async function createRunbookReportArtifact(): Promise<ReportGenerationResult> {
    if (!activeReview) {
      appendAuditEvent("report.generate.skipped", "Report generation skipped because no active review is selected.");
      return { result: "skipped", report: null };
    }
    if (providerMode === "ollama" && agentOperation?.state !== "completed") {
      appendAuditEvent("report.generate.blocked", "Verified report blocked until the Ollama operation commits.");
      return { result: "skipped", report: null };
    }

    let packetForFallback = activePacketData;
    try {
      const { reviewId, packetId, packet } = await ensurePacketForReview(activeReview);
      packetForFallback = packet;
      const report = await generatePacketReport(packetId);
      setReportArtifact(report);
      if (agentOperation?.resultPacketVersion) {
        try {
          setReportDiff(await generateReportDiff(packetId));
        } catch {
          setReportDiff(null);
        }
      }
      try {
        const refreshedPacket = await getPacket(packetId);
        syncReviewFromPacket(reviewId, refreshedPacket);
      } catch {
        appendAuditEvent("report.generated", `Report artifact generated for ${activeReview.ticker}; packet refresh unavailable after export.`);
      }
      return { result: "ok", report };
    } catch (error) {
      if (governedReportExportEnabled) throw error;
      const fallbackReport = buildLocalReportArtifact(activeReview, packetForFallback);
      setReportArtifact(fallbackReport);
      appendAuditEvent("report.generate.fallback", "Report endpoint unavailable; exported a local Markdown artifact from current packet state.");
      return { result: "fallback", report: fallbackReport };
    }
  }

  async function generateRunbookReport(): Promise<ActionResult> {
    const { result } = await createRunbookReportArtifact();
    return result;
  }

  async function executeRunbookStep(step: RunbookStep): Promise<RunbookStepResult> {
    if (step.manualGate) {
      setRunbookState({
        status: "manual_required",
        currentStepId: step.id,
        message: step.manualGate,
        completedAt: new Date().toISOString()
      });
      return "manual_required";
    }

    setRunbookState({
      status: "running",
      currentStepId: step.id,
      message: `Running ${step.label}...`,
      startedAt: new Date().toISOString()
    });

    let result: ActionResult;
    switch (step.id) {
      case "market":
        result = await refreshMarketMetrics();
        break;
      case "agents":
        result = await runAgentSwarm();
        break;
      case "risk":
        result = await evaluateRisk();
        break;
      case "confidence":
        result = await deriveConfidenceFromMarket();
        break;
      case "report":
        result = await generateRunbookReport();
        break;
      default:
        result = "skipped";
    }

    const completedAt = new Date().toISOString();
    if (result === "ok") {
      setRunbookState({
        status: "complete",
        currentStepId: step.id,
        message: `${step.label} completed with evidence available.`,
        completedAt
      });
    } else if (result === "queued") {
      setRunbookState({
        status: "running",
        currentStepId: step.id,
        message: `${step.label} queued; waiting for inference and admission evidence.`,
        startedAt: new Date().toISOString()
      });
    } else {
      setRunbookState({
        status: "failed",
        currentStepId: step.id,
        message: `${step.label} did not produce completion evidence.`,
        completedAt,
        error: result === "blocked"
          ? "No active preflighted Ollama worker is compatible with the selected model policy."
          : result === "fallback"
            ? "API path or provider fell back before checkpoint evidence was created."
            : "Required context was missing."
      });
    }
    return result;
  }

  async function runNextRunbookStep() {
    const nextStep = runbookSteps.find((step) => !step.done);
    if (!nextStep) {
      setRunbookState({
        status: "complete",
        currentStepId: null,
        message: "All runbook checkpoints are complete.",
        completedAt: new Date().toISOString()
      });
      setActionFeedback({ tone: "good", message: "All runbook checkpoints are complete." });
      return;
    }

    setActiveAction("Run next checkpoint");
    setActionFeedback({ tone: "neutral", message: `${nextStep.actionLabel} running from the Demo Runbook...` });
    try {
      const result = await executeRunbookStep(nextStep);
      if (result === "ok") {
        setActionFeedback({ tone: "good", message: `${nextStep.label} completed. Open its evidence drawer for endpoint, artifact, and audit proof.` });
      } else if (result === "queued") {
        setActionFeedback({ tone: "neutral", message: `${nextStep.label} is queued. This checkpoint will complete only after proposal admission.` });
      } else if (result === "manual_required") {
        setActionFeedback({ tone: "warn", message: nextStep.manualGate ?? `${nextStep.label} requires human action.` });
      } else {
        setActionFeedback({ tone: "warn", message: `${nextStep.label} stopped before completion evidence was produced.` });
      }
    } catch (error) {
      setRunbookState({
        status: "failed",
        currentStepId: nextStep.id,
        message: `${nextStep.label} failed.`,
        completedAt: new Date().toISOString(),
        error: actionableApiError(error)
      });
      setActionFeedback({
        tone: "warn",
        message: `${nextStep.label} failed: ${actionableApiError(error)}`
      });
    } finally {
      setActiveAction(null);
    }
  }

  async function runGuidedDemo() {
    const remainingSteps = runbookSteps.filter((step) => !step.done);
    if (remainingSteps.length === 0) {
      setRunbookState({
        status: "complete",
        currentStepId: null,
        message: "All runbook checkpoints are complete.",
        completedAt: new Date().toISOString()
      });
      setActionFeedback({ tone: "good", message: "All runbook checkpoints are complete." });
      return;
    }

    setActiveAction("Run guided demo");
    setActionFeedback({ tone: "neutral", message: "Guided demo running real checkpoints in order..." });

    try {
      for (const step of remainingSteps) {
        const result = await executeRunbookStep(step);
        if (result === "manual_required") {
          setActionFeedback({ tone: "warn", message: step.manualGate ?? `${step.label} requires human action before the runbook can continue.` });
          return;
        }
        if (result !== "ok") {
          setActionFeedback({ tone: "warn", message: `Guided demo stopped at ${step.label}; no completion evidence was produced.` });
          return;
        }
      }
      setRunbookState({
        status: "complete",
        currentStepId: null,
        message: "Guided demo completed every available checkpoint.",
        completedAt: new Date().toISOString()
      });
      setActionFeedback({ tone: "good", message: "Guided demo completed every available checkpoint." });
    } catch (error) {
      setRunbookState({
        status: "failed",
        currentStepId: null,
        message: "Guided demo failed.",
        completedAt: new Date().toISOString(),
        error: actionableApiError(error)
      });
      setActionFeedback({
        tone: "warn",
        message: `Guided demo failed: ${actionableApiError(error)}`
      });
    } finally {
      setActiveAction(null);
    }
  }

  async function exportCurrentReport() {
    if (reportArtifact) {
      downloadReportArtifact(reportArtifact);
      setActionFeedback({ tone: "good", message: "Report export started." });
      return;
    }

    setActiveAction("Generate report");
    setActionFeedback({ tone: "neutral", message: "Generating report artifact for download..." });
    setRunbookState({
      status: "running",
      currentStepId: "report",
      message: "Generating exportable decision report...",
      startedAt: new Date().toISOString()
    });

    try {
      const { result, report } = await createRunbookReportArtifact();
      const completedAt = new Date().toISOString();
      if (report) {
        downloadReportArtifact(report);
        const message = result === "ok" ? "Report generated by API and download started." : "Report exported from local fallback; API report endpoint was unavailable.";
        setRunbookState({
          status: "complete",
          currentStepId: "report",
          message,
          completedAt
        });
        setActionFeedback({
          tone: result === "ok" ? "good" : "warn",
          message
        });
        return;
      }

      setRunbookState({
        status: "failed",
        currentStepId: "report",
        message: "Report export did not produce an artifact.",
        completedAt,
        error: "Required review context was missing."
      });
      setActionFeedback({ tone: "warn", message: "Report export did not produce an artifact." });
    } catch (error) {
      setRunbookState({
        status: "failed",
        currentStepId: "report",
        message: "Report export failed.",
        completedAt: new Date().toISOString(),
        error: actionableApiError(error)
      });
      setActionFeedback({ tone: "warn", message: `Report export failed: ${actionableApiError(error)}` });
    } finally {
      setActiveAction(null);
    }
  }

  const runbookSteps = useMemo(
    () => buildRunbookSteps(activeReview, activePacketData, liveMarketData, reportArtifact),
    [activeReview, activePacketData, liveMarketData, reportArtifact]
  );

  const softPolicyReasons = useMemo(() => {
    const reasons: string[] = [];
    if (activeAlphaDecay?.decayDetected) {
      reasons.push(`Alpha decay detected for linked signal ${activeAlphaDecay.signalId}; recommended action: ${activeAlphaDecay.recommendedAction}.`);
    }
    const hygieneIssues = activePacketData?.backtestResult?.hygienIssues ?? [];
    if (hygieneIssues.length > 0) {
      reasons.push(`Backtest hygiene issues present: ${hygieneIssues.join(", ")}.`);
    }
    return reasons;
  }, [activeAlphaDecay, activePacketData]);

  const softPolicySuggestedDecision: DecisionState | null = softPolicyReasons.length > 0 ? "needs_more_data" : null;

  const pursueGateViolations = useMemo(() => {
    const violations: string[] = [];
    if (activeAlphaLink?.signalId && !activeAlphaLink.signalVersion) {
      violations.push("Signal-backed reviews require signalVersion linkage before Pursue.");
    }
    if (activeReview.validation.status !== "specified") {
      violations.push("Validation protocol must be specified.");
    }
    if (activePacketData?.riskMonitor?.status === "alert") {
      violations.push("Risk monitor is in alert state.");
    }
    return violations;
  }, [activeAlphaLink?.signalId, activeAlphaLink?.signalVersion, activePacketData, activeReview.validation.status]);

  const integrationKpis = useMemo(() => {
    const reviewLinks = listReviewAlphaLinks();
    const writebacks = listAlphaWritebacks();
    const linkedReviewCount = reviews.filter((review) => Boolean(reviewLinks[review.id])).length;
    const totalReviews = reviews.length;
    const linkedCoveragePct = totalReviews > 0 ? Math.round((linkedReviewCount / totalReviews) * 100) : 0;
    const decisionOverrideCount = reviews.reduce(
      (sum, review) => sum + review.audit.filter((event) => event.eventType === "decision.override").length,
      0
    );
    const objectWritebackCount = Object.keys(writebacks).length;
    const outcomeWritebackCount = Object.values(writebacks).reduce((sum, state) => sum + state.outcomeCount, 0);
    return {
      linkedCoveragePct,
      linkedReviewCount,
      totalReviews,
      decisionOverrideCount,
      objectWritebackCount,
      outcomeWritebackCount
    };
  }, [reviews]);

  return (
    <main className="min-h-screen pb-10 text-ink">
      <div className="mx-auto max-w-[1500px] space-y-4">
        <TopBar review={activeReview} />
        {activeAlphaLink ? <LinkedAlphaPanel link={activeAlphaLink} references={researchReferences} /> : null}
        <IntegrationKpiPanel metrics={integrationKpis} />
        {actionFeedback ? <FeedbackBanner feedback={actionFeedback} /> : null}
        <RunbookStrip
          review={activeReview}
          packet={activePacketData}
          steps={runbookSteps}
          reportArtifact={reportArtifact}
          reportDiff={reportDiff}
          runbookState={runbookState}
          activeAction={activeAction}
          governedReportExportEnabled={governedReportExportEnabled}
          providerMode={providerMode}
          ollamaModelPolicies={ollamaModelPolicies}
          ollamaWorkerReadiness={ollamaWorkerReadiness}
          selectedOllamaDigest={selectedOllamaDigest}
          onProviderModeChange={setProviderMode}
          onOllamaDigestChange={setSelectedOllamaDigest}
          onRunNext={runNextRunbookStep}
          onRunGuided={runGuidedDemo}
          onExportReport={exportCurrentReport}
        />

        <div className="grid gap-4 xl:grid-cols-[minmax(260px,0.9fr)_minmax(360px,1.35fr)_minmax(280px,0.85fr)]">
          <ContextPanel review={activeReview} recentReviews={recentReviews} onSelectReview={setActiveId} />
          <AnalysisFeed
            review={activeReview}
            packet={activePacketData}
            activeAction={activeAction}
            agentOperation={agentOperation}
            agentProposal={agentProposal}
            onReviewProposal={reviewOllamaProposal}
            onRollbackProposal={rollbackOllamaProposal}
            onCancelOperation={cancelOllamaOperation}
            onFallbackOperation={fallbackOllamaOperation}
            onContinueOperation={continueOllamaOperation}
            onRetryOperation={retryOllamaOperation}
            onRefreshAndRerunOperation={() => runAction("Refresh evidence and rerun", refreshEvidenceAndRerunOllama)}
            onRunAgents={() => runAction("Run analysis", runAgentSwarm)}
            onPrepareBacktest={() => runAction("Prepare backtest", prepareBacktest)}
            onDeriveConfidence={() => runAction("Derive confidence", deriveConfidenceFromMarket)}
            onRunSelectiveIntegration={() => runAction("Selective integration", runSelectiveIntegration)}
          />
          <MarketAndRiskPanel
            review={activeReview}
            packet={activePacketData}
            marketData={liveMarketData}
            activeAction={activeAction}
            onRefresh={() => runAction("Refresh metrics", refreshMarketMetrics)}
            onEvaluateRisk={() => runAction("Evaluate risk", evaluateRisk)}
            onRecordOutcome={() => runAction("Record outcome", recordOutcomeForDecision)}
          />
        </div>

        <DecisionStrip
          review={activeReview}
          activeAction={activeAction}
          onConfidenceChange={updateConfidence}
          onDecision={(decisionState, rationale) => updateDecision(decisionState, rationale, softPolicySuggestedDecision, pursueGateViolations)}
          suggestedDecision={softPolicySuggestedDecision}
          advisoryReasons={softPolicyReasons}
          pursueGateViolations={pursueGateViolations}
        />
        <SignalDecisionProposalPanel
          review={activeReview}
          link={activeAlphaLink}
          packet={activePacketData}
          activeAction={activeAction}
          alphaDecay={activeAlphaDecay}
          pursueGateViolations={pursueGateViolations}
          onConfirm={confirmSignalDecisionProposal}
        />
      </div>
    </main>
  );
}

function TopBar({ review }: { review: TradeReview }) {
  return (
    <Panel className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-teal">Pre-trade adversarial review</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-normal text-ink">{review.title}</h1>
          <p className="mt-2 max-w-3xl text-sm leading-5 text-slate-400">
            Focused decision workspace for one packet: original thesis, agent analysis, market context, and the human decision.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href={`/markets/${encodeURIComponent(review.ticker.toUpperCase())}`}
            className="focus-ring inline-flex items-center rounded-md border border-line bg-paper px-3 py-1.5 text-xs font-semibold text-teal hover:border-teal/60"
          >
            Open {review.ticker.toUpperCase()} intelligence
          </Link>
          <Badge tone="info">{review.schemaVersion}</Badge>
          <Badge tone="neutral">{review.workflowVersion}</Badge>
          <Badge tone={review.decisionState ? "good" : "warn"}>{review.decisionState ? decisionLabels[review.decisionState] : "Decision pending"}</Badge>
        </div>
      </div>
    </Panel>
  );
}

  function SignalDecisionProposalPanel({
    review,
    link,
    packet,
    activeAction,
    alphaDecay,
    pursueGateViolations,
    onConfirm
  }: {
    review: TradeReview;
    link: ReviewAlphaLink | null;
    packet: DecisionPacket | null;
    activeAction: string | null;
    alphaDecay: AlphaDecaySnapshot | null;
    pursueGateViolations: string[];
    onConfirm: (action: SignalDecisionAction, rationale?: string) => void;
  }) {
    const proposedAction = review.decisionState ? deriveSignalDecisionAction(review, review.decisionState, alphaDecay) : null;
    const [selectedAction, setSelectedAction] = useState<SignalDecisionAction>(proposedAction ?? "HOLD");
    const [rationale, setRationale] = useState("");
    const readiness = resolveExecutionReadiness(selectedAction, review, packet, pursueGateViolations);
    const blockers = buildSignalDecisionBlockers(review, link, packet, pursueGateViolations);
    const signalId = link?.signalId ?? null;
    const canWrite = Boolean(review.decisionState && !activeAction);

    useEffect(() => {
      setSelectedAction(proposedAction ?? "HOLD");
      setRationale("");
    }, [proposedAction, review.id]);

    return (
      <Panel className="border border-teal/30 bg-paper p-4 shadow-panel">
        <div className="grid gap-4 lg:grid-cols-[minmax(240px,0.8fr)_minmax(360px,1.2fr)_minmax(260px,0.8fr)]">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-teal">Signal Decision Proposal</p>
            <h2 className="mt-1 text-base font-semibold text-ink">Surface review result as a signal action</h2>
            <p className="mt-2 text-sm text-slate-400">
              Confirm the finance-native action that should be written to the linked signal. This updates signal memory; it does not execute a trade.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge tone={review.decisionState ? "good" : "warn"}>{review.decisionState ? `Review: ${decisionLabels[review.decisionState]}` : "Review decision pending"}</Badge>
              <Badge tone={signalId ? "info" : "warn"}>{signalId ? `Signal: ${signalId}` : "Signal will be created"}</Badge>
              <Badge tone={readiness === "paper_trade_ready" || readiness === "execution_candidate" ? "good" : readiness === "execution_blocked" ? "warn" : "neutral"}>{readiness}</Badge>
            </div>
            {link?.signalVersion ? <p className="mt-2 text-xs text-slate-500">Version v{link.signalVersion}</p> : null}
          </div>

          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              {signalDecisionActionOptions.map((option) => (
                <button
                  type="button"
                  key={option.action}
                  onClick={() => setSelectedAction(option.action)}
                  disabled={Boolean(activeAction) || !review.decisionState}
                  className={cn(
                    "focus-ring rounded-md border px-2 py-2 text-left text-xs transition disabled:cursor-not-allowed disabled:opacity-50",
                    selectedAction === option.action ? "border-teal bg-teal/10 text-teal" : "border-line bg-fog/70 text-slate-300 hover:border-teal/50"
                  )}
                  title={option.summary}
                >
                  <span className="block font-semibold">{option.label}</span>
                  <span className="mt-1 block text-[11px] text-slate-500">{option.action}</span>
                </button>
              ))}
            </div>
            <input
              value={rationale}
              onChange={(event) => setRationale(event.target.value)}
              placeholder="Optional writeback rationale"
              disabled={Boolean(activeAction) || !review.decisionState}
              className="focus-ring w-full rounded-md border border-line bg-fog/70 px-3 py-2 text-xs text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
            />
            <div className="rounded-md border border-line bg-fog/60 p-3 text-xs text-slate-300">
              <p className="font-semibold text-slate-200">Next required step</p>
              <p className="mt-1">{describeSignalDecisionNextStep(readiness, blockers)}</p>
            </div>
          </div>

          <div className="space-y-3">
            <div className="rounded-md border border-line bg-fog/60 p-3 text-xs">
              <p className="font-semibold text-slate-200">Writeback readiness</p>
              {blockers.length > 0 ? (
                <ul className="mt-2 space-y-1 text-amber">
                  {blockers.map((blocker) => (
                    <li key={blocker}>{blocker}</li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-teal">Linked signal and review decision are ready for writeback.</p>
              )}
            </div>
            <button
              type="button"
              onClick={() => onConfirm(selectedAction, rationale)}
              disabled={!canWrite}
              className="focus-ring w-full rounded-md bg-teal px-3 py-2 text-sm font-semibold text-fog transition hover:bg-teal/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {activeAction === "Write signal decision" ? "Writing signal decision..." : signalId ? `Write ${selectedAction} to Signal` : `Create Signal + Write ${selectedAction}`}
            </button>
            {signalId ? (
              <Link href="/signals" className="focus-ring inline-flex w-full items-center justify-center gap-1 rounded-md border border-line bg-fog/70 px-3 py-2 text-xs font-semibold text-teal hover:border-teal/60">
                Open Signals cockpit <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            ) : null}
          </div>
        </div>
      </Panel>
    );
  }
  function deriveSignalDecisionAction(review: TradeReview, decisionState: DecisionState, alphaDecay: AlphaDecaySnapshot | null): SignalDecisionAction {
    if (alphaDecay?.decayDetected && /retire|decay|decommission/i.test(alphaDecay.recommendedAction)) return "RETIRE";
    if (decisionState !== "pursue") return signalDecisionActions[decisionState];

    const decisionText = `${review.title} ${review.thesis} ${review.intendedExpression}`.toLowerCase();
    if (/hedge|protect|offset/.test(decisionText)) return "HEDGE";
    if (/sell|short|exit|reduce|avoid|underweight/.test(decisionText)) return "SELL";
    if (/risk|size|trim|rebalance|constrain/.test(decisionText)) return "RISK_ADJUST";
    return "BUY";
  }

  function resolveExecutionReadiness(
    action: SignalDecisionAction,
    review: TradeReview,
    packet: DecisionPacket | null,
    pursueGateViolations: string[]
  ): SignalExecutionReadiness {
    if (["BLOCK", "HOLD", "RETIRE"].includes(action)) return "not_executable";
    if (review.validation.status !== "specified" || pursueGateViolations.length > 0) return "execution_blocked";
    if (!packet?.riskMonitor || packet.riskMonitor.status === "alert") return "execution_blocked";
    return "paper_trade_ready";
  }

  function buildSignalDecisionBlockers(review: TradeReview, link: ReviewAlphaLink | null, packet: DecisionPacket | null, pursueGateViolations: string[]) {
    const blockers: string[] = [];
    if (!review.decisionState) blockers.push("Record a review decision first.");
    if (!link?.signalId) blockers.push("No linked signal yet; Ambrosia will create one before writeback.");
    if (link?.signalId && !link.signalVersion) blockers.push("Signal version is missing.");
    if (review.validation.status !== "specified") blockers.push("Validation protocol is not specified.");
    if (!packet?.riskMonitor) blockers.push("Risk evaluation has not been recorded for execution readiness.");
    if (packet?.riskMonitor?.status === "alert") blockers.push("Risk monitor is in alert state.");
    return [...blockers, ...pursueGateViolations.filter((violation) => !blockers.includes(violation))];
  }

  function describeSignalDecisionNextStep(readiness: SignalExecutionReadiness, blockers: string[]) {
    if (blockers.length > 0) return blockers[0];
    if (readiness === "paper_trade_ready") return "Send to paper-trade review when the user wants execution evidence.";
    if (readiness === "execution_candidate") return "Route to execution intelligence for approval and sizing.";
    if (readiness === "execution_blocked") return "Resolve validation, risk, liquidity, or approval blockers before execution.";
    return "Store the decision in signal history; no execution path should open.";
  }

  function deriveDecisionQuality(review: TradeReview) {
    if (review.confidence >= 80 && review.validation.status === "specified") return "D4";
    if (review.confidence >= 60) return "D3";
    return "D2";
  }

  function inferSignalFamily(thesis: string): string {
    const lower = thesis.toLowerCase();
    if (/momentum|trend|breakout|relative strength/.test(lower)) return "momentum";
    if (/liquid|volume|spread|depth/.test(lower)) return "liquidity";
    if (/quality|margin|balance sheet|earnings/.test(lower)) return "quality";
    if (/duration|curve|rate|yield|macro/.test(lower)) return "macro";
    return "review-derived";
  }

  function readText(value: unknown): string {
    return typeof value === "string" ? value : "";
  }

  function readVersion(activeVersion: unknown, fallbackVersion: unknown): number {
    if (typeof activeVersion === "number" && activeVersion >= 1) return Math.floor(activeVersion);
    if (typeof fallbackVersion === "number" && fallbackVersion >= 1) return Math.floor(fallbackVersion);
    return 1;
  }

  function safeMinimumText(value: string | null | undefined, fallback: string, minLength: number): string {
    const trimmed = (value ?? "").trim();
    return trimmed.length >= minLength ? trimmed : fallback;
  }

function linkFromResearchReference(reference: ResearchObjectReference): ReviewAlphaLink {
  const snapshot = reference.snapshot;
  const universe = Array.isArray(snapshot.universe) ? snapshot.universe : [];
  return {
    source: "alpha",
    objectType: reference.objectType,
    signalId: reference.objectType === "signal" ? reference.objectId : undefined,
    hypothesisId: reference.objectType === "hypothesis" ? reference.objectId : undefined,
    signalVersion: reference.objectType === "signal" ? reference.versionId : undefined,
    title: readOptionalText(snapshot.name) ?? readOptionalText(snapshot.title),
    signalFamily: readOptionalText(snapshot.signalFamily),
    formula: readOptionalText(snapshot.formula),
    ticker: readOptionalText(universe[0]),
    createdAt: reference.attachedAt
  };
}

function readOptionalText(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function LinkedAlphaPanel({ link, references }: { link: ReviewAlphaLink; references: ResearchObjectReference[] }) {
  const objectId = link.objectType === "hypothesis" ? link.hypothesisId : link.signalId;

  return (
    <Panel className="p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-teal">Linked Alpha Context</p>
          <p className="mt-1 text-sm text-ink/80">
            {link.objectType === "hypothesis" ? "Hypothesis" : "Signal"}
            {link.title ? `: ${link.title}` : ""}
          </p>
          <p className="mt-1 text-xs text-ink/65">
            {objectId ? `ID ${objectId}` : "ID unavailable"}
            {link.ticker ? ` | Ticker ${link.ticker}` : ""}
            {link.signalFamily ? ` | Family ${link.signalFamily}` : ""}
          </p>
          {link.formula ? <p className="mt-1 text-xs text-ink/65">Formula: {link.formula}</p> : null}
          {references.map((reference) => (
            <p key={reference.referenceId} className="mt-1 text-xs text-ink/65">
              Snapshot v{reference.versionId} | {reference.relationshipType} | {reference.driftStatus} | hash {reference.contentHash.slice(0, 12)}
            </p>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <Link href="/alpha" className="focus-ring rounded-md border border-line bg-paper px-3 py-1.5 text-xs font-semibold text-teal hover:border-teal/60">
            Open Alpha Lab
          </Link>
          <Badge tone="info">{link.objectType}</Badge>
          {references.some((reference) => reference.driftStatus === "superseded") ? <Badge tone="warn">Superseded snapshot</Badge> : null}
        </div>
      </div>
    </Panel>
  );
}

function IntegrationKpiPanel({
  metrics
}: {
  metrics: {
    linkedCoveragePct: number;
    linkedReviewCount: number;
    totalReviews: number;
    decisionOverrideCount: number;
    objectWritebackCount: number;
    outcomeWritebackCount: number;
  };
}) {
  return (
    <Panel className="p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-teal">Integration KPIs</p>
      <div className="mt-3 grid gap-2 md:grid-cols-3 xl:grid-cols-6 text-sm">
        <ContextMetric label="Linked coverage" value={`${metrics.linkedCoveragePct}%`} />
        <ContextMetric label="Linked reviews" value={`${metrics.linkedReviewCount}/${metrics.totalReviews}`} />
        <ContextMetric label="Decision overrides" value={String(metrics.decisionOverrideCount)} />
        <ContextMetric label="Objects with writeback" value={String(metrics.objectWritebackCount)} />
        <ContextMetric label="Outcome writebacks" value={String(metrics.outcomeWritebackCount)} />
        <ContextMetric label="Governance mode" value="linked" />
      </div>
    </Panel>
  );
}

function FeedbackBanner({ feedback }: { feedback: { tone: "neutral" | "good" | "warn"; message: string } }) {
  return (
    <div
      className={cn(
        "rounded-lg border px-3 py-2 text-sm",
        feedback.tone === "good"
          ? "border-teal/30 bg-teal/10 text-teal"
          : feedback.tone === "warn"
            ? "border-amber/30 bg-amber/10 text-amber"
            : "border-line bg-paper text-slate-300"
      )}
    >
      {feedback.message}
    </div>
  );
}

function RunbookStrip({
  review,
  packet,
  steps,
  reportArtifact,
  reportDiff,
  runbookState,
  activeAction,
  governedReportExportEnabled,
  providerMode,
  ollamaModelPolicies,
  ollamaWorkerReadiness,
  selectedOllamaDigest,
  onProviderModeChange,
  onOllamaDigestChange,
  onRunNext,
  onRunGuided,
  onExportReport
}: {
  review: TradeReview;
  packet: DecisionPacket | null;
  steps: RunbookStep[];
  reportArtifact: ReportArtifact | null;
  reportDiff: ReportDiff | null;
  runbookState: RunbookRunState;
  activeAction: string | null;
  governedReportExportEnabled: boolean;
  providerMode: ProviderMode;
  ollamaModelPolicies: OllamaModelPolicy[];
  ollamaWorkerReadiness: OllamaWorkerReadiness | null;
  selectedOllamaDigest: string;
  onProviderModeChange: (mode: ProviderMode) => void;
  onOllamaDigestChange: (digest: string) => void;
  onRunNext: () => void;
  onRunGuided: () => void;
  onExportReport: () => void;
}) {
  const nextStep = steps.find((step) => !step.done) ?? null;
  const currentStep = runbookState.currentStepId ? steps.find((step) => step.id === runbookState.currentStepId) ?? null : null;
  const latestAudit = review.audit.at(-1);
  const statusLabel =
    runbookState.status === "running" && currentStep
      ? `Running ${currentStep.label}`
      : runbookState.status === "manual_required" && currentStep
        ? `${currentStep.label} requires human action`
        : nextStep
          ? `Next: ${nextStep.actionLabel}`
          : "Complete";
  const statusTone = runbookState.status === "failed" ? "warn" : runbookState.status === "complete" && !nextStep ? "good" : "info";

  return (
    <Panel className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-teal">Demo runbook</p>
          <p className="text-sm text-ink/70">Run one investment decision through visible proof checkpoints.</p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Badge tone={statusTone}>{statusLabel}</Badge>
          <label className="flex items-center gap-2 text-xs font-semibold text-slate-400">
            Provider
            <select
              aria-label="Provider mode"
              value={providerMode}
              disabled={Boolean(activeAction)}
              onChange={(event) => onProviderModeChange(event.target.value as ProviderMode)}
              className="focus-ring rounded-md border border-line bg-fog px-2 py-1 text-xs font-semibold text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {providerModes.map((mode) => (
                <option key={mode} value={mode}>
                  {mode}
                </option>
              ))}
            </select>
          </label>
          {providerMode === "ollama" ? (
            <label className="flex items-center gap-2 text-xs font-semibold text-slate-400">
              Model policy
              <select
                aria-label="Ollama model policy"
                value={selectedOllamaDigest}
                disabled={Boolean(activeAction) || ollamaModelPolicies.length === 0}
                onChange={(event) => onOllamaDigestChange(event.target.value)}
                className="focus-ring max-w-64 rounded-md border border-line bg-fog px-2 py-1 text-xs font-semibold text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {ollamaModelPolicies.length === 0 ? <option value="">No configured approved model policy</option> : null}
                {ollamaModelPolicies.map((policy) => (
                  <option key={policy.digest} value={policy.digest}>
                    {policy.name ?? "Ollama"} · {policy.workerCompatibility?.ready ? "worker ready" : (policy.workerCompatibility?.reasonCode ?? "worker unavailable").replaceAll("_", " ")} · {policy.digest.slice(0, 18)}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <button
            type="button"
            onClick={onRunNext}
            disabled={Boolean(activeAction) || !nextStep || (providerMode === "ollama" && nextStep.id === "agents" && (!selectedOllamaDigest || !ollamaWorkerReadiness?.ready))}
            className="focus-ring rounded-md bg-teal px-3 py-2 text-xs font-semibold text-fog transition hover:bg-teal/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {activeAction === "Run next checkpoint" ? "Running..." : nextStep ? "Run next checkpoint" : "Runbook complete"}
          </button>
          {providerMode === "ollama" && nextStep?.id === "agents" && !ollamaWorkerReadiness?.ready ? (
            <span className="text-xs text-amber">
              Blocked: {(ollamaWorkerReadiness?.reasonCode ?? "worker_offline").replaceAll("_", " ")}
              {ollamaWorkerReadiness?.lastHeartbeatAgeSeconds != null ? ` · last heartbeat ${ollamaWorkerReadiness.lastHeartbeatAgeSeconds}s ago` : ""}
              {` · ${readinessRemediation(ollamaWorkerReadiness)}`}
            </span>
          ) : null}
          <button
            type="button"
            onClick={onRunGuided}
            disabled={Boolean(activeAction) || !nextStep}
            className="focus-ring rounded-md border border-line bg-fog/70 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:border-teal/50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {activeAction === "Run guided demo" ? "Running..." : "Run guided demo"}
          </button>
          {governedReportExportEnabled ? (
            <button
              type="button"
              onClick={onExportReport}
              disabled={Boolean(activeAction)}
              className="focus-ring inline-flex items-center gap-1 rounded-md border border-line bg-fog/70 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:border-teal/50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Download className="h-3.5 w-3.5" />
              {activeAction === "Generate report" ? "Generating..." : reportArtifact ? "Export report" : "Generate / export report"}
            </button>
          ) : null}
        </div>
      </div>

      <div
        role="status"
        aria-live="polite"
        className="mt-4 grid gap-2 rounded-md border border-line bg-fog/60 p-3 text-xs text-slate-300 md:grid-cols-4"
      >
        <ProofMetric label="Runbook status" value={statusLabel} />
        <ProofMetric label="Provider path" value={packet?.providerInfo ? `${packet.providerInfo.name} / ${packet.providerInfo.type}` : providerMode} />
        <ProofMetric label="Fallback" value={packet?.providerInfo ? (packet.providerInfo.fallbackUsed ? "Fallback used" : "No runtime fallback") : "Pending provider evidence"} />
        <ProofMetric label="Last audit" value={latestAudit ? latestAudit.eventType : "No audit event yet"} />
      </div>

      {runbookState.message ? (
        <p className={cn("mt-3 rounded-md border px-3 py-2 text-xs", runbookState.status === "failed" || runbookState.status === "manual_required" ? "border-amber/30 bg-amber/10 text-amber" : "border-line bg-paper text-slate-300")}>
          {runbookState.message}
          {runbookState.error ? ` ${runbookState.error}` : ""}
        </p>
      ) : null}

      <ol className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-8">
        {steps.map((step, index) => (
          <RunbookStepCard
            key={step.id}
            step={step}
            index={index}
            displayStatus={getRunbookDisplayStatus(step, nextStep, runbookState)}
            reportArtifact={reportArtifact}
            activeAction={activeAction}
            onExportReport={onExportReport}
          />
        ))}
      </ol>
      {reportDiff ? (
        <div className="mt-3 rounded-md border border-teal/30 bg-teal/5 p-3 text-xs">
          <p className="font-semibold">Governed report diff · packet v{reportDiff.beforePacketVersion} → v{reportDiff.afterPacketVersion}</p>
          <p className="mt-1">Changed sections: {reportDiff.changedSections.join(", ") || "none"}</p>
          <p className="mt-1">Added claims: {reportDiff.addedClaimIds.join(", ") || "none"} · Corrected: {reportDiff.correctedClaimIds.join(", ") || "none"} · Rejected: {reportDiff.rejectedClaimIds.join(", ") || "none"}</p>
          <p className="mt-1 text-slate-500">Citations Δ {reportDiff.citationDelta} · confidence Δ {reportDiff.confidenceDelta} · {reportDiff.storageStatus ?? "unknown storage"}</p>
        </div>
      ) : null}
    </Panel>
  );
}

function RunbookStepCard({
  step,
  index,
  displayStatus,
  reportArtifact,
  activeAction,
  onExportReport
}: {
  step: RunbookStep;
  index: number;
  displayStatus: { label: string; tone: "neutral" | "good" | "warn" | "info"; active: boolean };
  reportArtifact: ReportArtifact | null;
  activeAction: string | null;
  onExportReport: () => void;
}) {
  return (
    <li className={cn("rounded-md border p-2 text-xs", step.done ? "border-teal/30 bg-teal/10" : displayStatus.active ? "border-amber/40 bg-amber/5" : "border-line bg-fog/70")}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className={cn("flex h-5 w-5 items-center justify-center rounded-full border text-[10px] font-semibold", step.done ? "border-teal bg-teal text-fog" : "border-line text-ink/60")}>
                {index + 1}
              </span>
              <span className="font-semibold text-ink">{step.label}</span>
            </div>
            <p className="mt-1 text-ink/60">{step.detail}</p>
        </div>
        <Badge tone={displayStatus.tone}>{displayStatus.label}</Badge>
      </div>
      {step.id === "report" ? (
        <div className="mt-3 border-t border-line pt-2">
          <button
            type="button"
            onClick={onExportReport}
            disabled={Boolean(activeAction)}
            className="focus-ring inline-flex items-center gap-1 rounded-md border border-line bg-fog/80 px-2 py-1 text-[11px] font-semibold text-slate-200 transition hover:border-teal/50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download className="h-3 w-3" />
            {activeAction === "Generate report" ? "Generating..." : reportArtifact ? "Download Markdown report" : "Generate and download report"}
          </button>
        </div>
      ) : null}
    </li>
  );
}

function buildRunbookSteps(review: TradeReview, packet: DecisionPacket | null, marketData: LiveMarketData | null, reportArtifact: ReportArtifact | null): RunbookStep[] {
  const hasAudit = (eventType: string) => review.audit.some((event) => event.eventType === eventType);
  const marketDone = Boolean(packet?.marketSnapshot || marketData?.snapshot);
  const agentsDone = Boolean(packet?.agentOutputs);
  const riskDone = Boolean(packet?.riskMonitor);
  const confidenceDone = Boolean(packet?.confidenceBreakdown);
  const decisionDone = Boolean(review.decisionState);
  const outcomeDone = hasAudit("outcome.recorded");
  const reportDone = hasAudit("report.generated") || Boolean(reportArtifact);

  return [
    {
      id: "intake",
      label: "Intake",
      done: true,
      detail: "Review object",
      actionLabel: "Open review",
      endpoint: "buildPacketShell(...) / createPacket(...)",
      artifact: review.id,
      auditEvents: ["review.created", "packet.created"],
      latestAudit: getLatestAuditEvent(review.audit, ["review.created", "packet.created"])
    },
    {
      id: "market",
      label: "Market Context",
      done: marketDone,
      detail: "Snapshot / technicals / sentiment",
      actionLabel: "Refresh market context",
      endpoint: "POST /packets/{packet_id}/metrics/refresh",
      artifact: packet?.marketSnapshot?.timestamp ?? marketData?.fetchedAt ?? "Pending market snapshot",
      auditEvents: ["metrics.refresh", "metrics.refresh.fallback"],
      latestAudit: getLatestAuditEvent(review.audit, ["metrics.refresh", "metrics.refresh.fallback"])
    },
    {
      id: "agents",
      label: "Agents",
      done: agentsDone,
      detail: "Specialists + PM synthesis",
      actionLabel: "Run agent swarm",
      endpoint: "POST /packets/{packet_id}/agents/run",
      artifact: packet?.agentOutputs ? `${Object.values(packet.agentOutputs).filter(Boolean).length}/${expectedAgentRoles.length} specialist outputs` : "Pending agent outputs",
      auditEvents: ["agents.run", "agents.run.fallback"],
      latestAudit: getLatestAuditEvent(review.audit, ["agents.run", "agents.run.fallback"])
    },
    {
      id: "risk",
      label: "Risk",
      done: riskDone,
      detail: "Monitor state",
      actionLabel: "Evaluate risk",
      endpoint: "POST /packets/{packet_id}/risk/evaluate",
      artifact: packet?.riskMonitor ? `${packet.riskMonitor.status} / concentration ${packet.riskMonitor.concentrationRisk}` : "Pending risk monitor",
      auditEvents: ["risk.evaluate", "risk.evaluate.fallback"],
      latestAudit: getLatestAuditEvent(review.audit, ["risk.evaluate", "risk.evaluate.fallback"])
    },
    {
      id: "confidence",
      label: "Confidence",
      done: confidenceDone,
      detail: "Score breakdown",
      actionLabel: "Derive confidence",
      endpoint: "POST /packets/{packet_id}/confidence/derive",
      artifact: packet?.confidenceBreakdown ? `${packet.confidenceBreakdown.overallConfidence}% overall confidence` : "Pending confidence breakdown",
      auditEvents: ["confidence.derive", "confidence.derive.fallback"],
      latestAudit: getLatestAuditEvent(review.audit, ["confidence.derive", "confidence.derive.fallback"])
    },
    {
      id: "decision",
      label: "Decision",
      done: decisionDone,
      detail: "Human-owned",
      actionLabel: "Choose human decision",
      endpoint: "PATCH /reviews/{review_id}/decision",
      artifact: review.decisionState ? decisionLabels[review.decisionState] : "Pending human decision",
      auditEvents: ["decision.recorded"],
      latestAudit: getLatestAuditEvent(review.audit, ["decision.recorded"]),
      manualGate: decisionDone ? undefined : "Manual required: choose Pursue, Watch, Reject, or Needs more data in the decision controls."
    },
    {
      id: "outcome",
      label: "Outcome",
      done: outcomeDone,
      detail: "Feedback loop",
      actionLabel: "Record outcome",
      endpoint: "POST /packets/{packet_id}/outcome",
      artifact: outcomeDone ? "Outcome audit recorded" : "Pending outcome attribution",
      auditEvents: ["outcome.recorded", "outcome.recorded.fallback"],
      latestAudit: getLatestAuditEvent(review.audit, ["outcome.recorded", "outcome.recorded.fallback"]),
      manualGate: outcomeDone ? undefined : "Manual required: record an outcome from the Outcome Loop when the result is known."
    },
    {
      id: "report",
      label: "Report",
      done: reportDone,
      detail: "Exportable packet",
      actionLabel: "Generate report",
      endpoint: "POST /packets/{packet_id}/report",
      artifact: reportArtifact ? `${reportArtifact.title} / ${reportArtifact.dataMode}` : "Pending report artifact",
      auditEvents: ["report.generated", "report.generate.fallback"],
      latestAudit: getLatestAuditEvent(review.audit, ["report.generated", "report.generate.fallback"])
    }
  ];
}

function getLatestAuditEvent(audit: AuditEvent[], eventTypes: string[]): AuditEvent | null {
  const allowedEvents = new Set(eventTypes);
  for (let index = audit.length - 1; index >= 0; index -= 1) {
    if (allowedEvents.has(audit[index].eventType)) {
      return audit[index];
    }
  }
  return null;
}

function getRunbookDisplayStatus(step: RunbookStep, nextStep: RunbookStep | null, runbookState: RunbookRunState): { label: string; tone: "neutral" | "good" | "warn" | "info"; active: boolean } {
  if (runbookState.currentStepId === step.id) {
    if (runbookState.status === "running") return { label: "Running", tone: "info", active: true };
    if (runbookState.status === "manual_required") return { label: "Manual", tone: "warn", active: true };
    if (runbookState.status === "failed") return { label: "Failed", tone: "warn", active: true };
    if (runbookState.status === "complete") return { label: "Complete", tone: "good", active: false };
  }

  if (step.done) {
    return { label: "Complete", tone: "good", active: false };
  }

  if (nextStep?.id === step.id) {
    return { label: step.manualGate ? "Manual required" : "Ready", tone: step.manualGate ? "warn" : "info", active: true };
  }

  return { label: "Pending", tone: "neutral", active: false };
}

function ContextPanel({ review, recentReviews, onSelectReview }: { review: TradeReview; recentReviews: TradeReview[]; onSelectReview: (reviewId: string) => void }) {
  return (
    <div className="space-y-4">
      <Panel className="p-5">
        <PanelHeader eyebrow="Left Context" title="Thesis and sources" />
        <div className="mt-4 space-y-4 text-sm">
          <div className="grid grid-cols-2 gap-2">
            <ContextMetric label="Ticker" value={review.ticker} />
            <ContextMetric label="Asset" value={review.assetClass} />
            <ContextMetric label="Horizon" value={review.timeHorizon} />
            <ContextMetric label="Expression" value={review.intendedExpression} />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Original thesis</p>
            <p className="mt-2 leading-6 text-slate-200">{review.thesis}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Claim map</p>
            <ul className="mt-2 space-y-2">
              {review.claims.map((claim) => (
                <ClaimRow key={claim.id} claim={claim} />
              ))}
            </ul>
          </div>
        </div>
      </Panel>

      <Panel className="p-5">
        <PanelHeader eyebrow="Source Context" title="Evidence pointers" />
        <ul className="mt-3 space-y-2">
          {review.sources.map((source) => (
            <SourceRow key={source.id} source={source} />
          ))}
        </ul>
      </Panel>

      <Panel className="p-5">
        <PanelHeader eyebrow="Review Queue" title="Resume another packet" />
        <div className="mt-3 space-y-2">
          {recentReviews.map((item) => (
            <button
              type="button"
              key={item.id}
              onClick={() => onSelectReview(item.id)}
              className={cn(
                "focus-ring w-full rounded-md border p-3 text-left text-sm transition",
                item.id === review.id ? "border-teal/70 bg-teal/10" : "border-line bg-fog/60 hover:border-teal/40"
              )}
            >
              <span className="block font-semibold">{item.title}</span>
              <span className="mt-1 block text-xs text-slate-400">
                {item.ticker} / {item.timeHorizon}
              </span>
            </button>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function AnalysisFeed({
  review,
  packet,
  activeAction,
  agentOperation,
  agentProposal,
  onReviewProposal,
  onRollbackProposal,
  onCancelOperation,
  onFallbackOperation,
  onContinueOperation,
  onRetryOperation,
  onRefreshAndRerunOperation,
  onRunAgents,
  onPrepareBacktest,
  onDeriveConfidence,
  onRunSelectiveIntegration
}: {
  review: TradeReview;
  packet: DecisionPacket | null;
  activeAction: string | null;
  agentOperation: AgentOperation | null;
  agentProposal: PacketMutationProposal | null;
  onReviewProposal: (body: AdmissionRequest) => Promise<void>;
  onRollbackProposal: (rationale: string) => Promise<void>;
  onCancelOperation: () => void;
  onFallbackOperation: () => void;
  onContinueOperation: () => void;
  onRetryOperation: () => void;
  onRefreshAndRerunOperation: () => void;
  onRunAgents: () => void;
  onPrepareBacktest: () => void;
  onDeriveConfidence: () => void;
  onRunSelectiveIntegration: () => void;
}) {
  const stages = buildWorkflowStages(review, packet);

  return (
    <div className="space-y-4">
      <Panel className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <PanelHeader eyebrow="Center Analysis" title="Live workflow feed" />
          <div className="flex flex-wrap gap-2">
            <ActionButton label="Run analysis" icon={<Activity className="h-4 w-4" />} activeAction={activeAction} onClick={onRunAgents} />
            <ActionButton label="Prepare backtest" icon={<Beaker className="h-4 w-4" />} activeAction={activeAction} onClick={onPrepareBacktest} />
            <ActionButton label="Derive confidence" icon={<SlidersHorizontal className="h-4 w-4" />} activeAction={activeAction} onClick={onDeriveConfidence} />
            <ActionButton label="Integrate" icon={<ShieldCheck className="h-4 w-4" />} activeAction={activeAction} onClick={onRunSelectiveIntegration} />
          </div>
        </div>
        <ProviderProvenancePanel packet={packet} operation={agentOperation} proposal={agentProposal}
          onReviewProposal={onReviewProposal}
          onRollbackProposal={onRollbackProposal}
          onCancel={onCancelOperation} onFallback={onFallbackOperation}
          onContinue={onContinueOperation} onRetry={onRetryOperation}
          onRefreshAndRerun={onRefreshAndRerunOperation} />

        <div className="mt-4 space-y-3">
          {stages.map((stage) => (
            <WorkflowStageCard key={stage.status} stage={stage} currentStatus={review.status} review={review} packet={packet} />
          ))}
        </div>
      </Panel>

      <Panel className="p-5">
        <PanelHeader eyebrow="Decision Evidence" title="Critique and disconfirming test" />
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <EvidenceBlock label="Strongest critique" text={review.strongestCritique} tone="warn" />
          <EvidenceBlock label="Disconfirming test" text={review.disconfirmingTest} tone="info" />
        </div>
        <details className="mt-3 rounded-md border border-line bg-fog/60 p-3 text-sm">
          <summary className="cursor-pointer font-semibold text-slate-200">Historical analogue</summary>
          <div className="mt-3 space-y-2 text-slate-300">
            <p className="font-semibold">{review.historicalAnalogue.title}</p>
            <p>{review.historicalAnalogue.similarity}</p>
            <p>{review.historicalAnalogue.differences}</p>
            <p>{review.historicalAnalogue.resolution}</p>
          </div>
        </details>
      </Panel>
    </div>
  );
}

function MarketAndRiskPanel({
  review,
  packet,
  marketData,
  activeAction,
  onRefresh,
  onEvaluateRisk,
  onRecordOutcome
}: {
  review: TradeReview;
  packet: DecisionPacket | null;
  marketData: LiveMarketData | null;
  activeAction: string | null;
  onRefresh: () => void;
  onEvaluateRisk: () => void;
  onRecordOutcome: () => void;
}) {
  const snapshot = marketData?.snapshot ?? packet?.marketSnapshot ?? null;
  const technicals = marketData?.technicals ?? packet?.technicals ?? null;
  const sentiment = marketData?.sentiment ?? packet?.sentiment ?? null;

  return (
    <div className="space-y-4">
      <Panel className="p-5">
        <div className="flex items-start justify-between gap-3">
          <PanelHeader eyebrow="Right Context" title={`${review.ticker} market dock`} />
          <ActionButton label="Refresh" icon={<RefreshCw className="h-4 w-4" />} activeAction={activeAction} onClick={onRefresh} compact />
        </div>
        <div className="mt-4 space-y-2 text-sm">
          <MetricRow label="Price" value={snapshot ? `$${snapshot.price.toFixed(2)}` : "Not loaded"} />
          <MetricRow label="24h change" value={snapshot ? `${snapshot.priceChange24h >= 0 ? "+" : ""}${snapshot.priceChange24h.toFixed(2)}%` : "Not loaded"} tone={snapshot && snapshot.priceChange24h < 0 ? "warn" : "good"} />
          <MetricRow label="Volume" value={snapshot ? compactNumber(snapshot.volume24h) : "Not loaded"} />
          <MetricRow label="RSI" value={technicals?.rsi !== null && technicals?.rsi !== undefined ? technicals.rsi.toFixed(1) : "Not loaded"} />
          <MetricRow label="MA200" value={technicals?.movingAverage200 !== null && technicals?.movingAverage200 !== undefined ? `$${technicals.movingAverage200.toFixed(2)}` : "Not loaded"} />
          <MetricRow label="Sentiment" value={sentiment ? `${sentiment.sentiment} (${Math.round(sentiment.overallScore)}%)` : "Not loaded"} />
        </div>
        <div className="mt-4 rounded-md border border-line bg-fog/60 p-3 text-xs text-slate-400">
          Source: {snapshot?.dataSource ?? "pending"} / Mode: {snapshot?.dataSourceConfidence ?? technicals?.dataMode ?? sentiment?.dataMode ?? "not loaded"}
        </div>
        <Link href={`/markets/${review.ticker}`} className="focus-ring mt-3 inline-flex items-center gap-1 text-sm font-semibold text-teal">
          Open deep charting <ArrowRight className="h-4 w-4" />
        </Link>
      </Panel>

      <Panel className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <PanelHeader eyebrow="Risk Gate" title="Tradeability and controls" />
          <ActionButton label="Evaluate" icon={<ShieldCheck className="h-4 w-4" />} activeAction={activeAction} onClick={onEvaluateRisk} compact />
        </div>
        <div className="mt-4 space-y-3">
          {review.tradeability.map((item) => (
            <div key={`${item.topic}-${item.question}`} className="rounded-md border border-line bg-fog/60 p-3 text-sm">
              <div className="flex items-center justify-between gap-2">
                <p className="font-semibold">{item.topic}</p>
                <Badge tone={item.severity === "high" ? "warn" : "neutral"}>{item.severity}</Badge>
              </div>
              <p className="mt-2 text-slate-300">{item.question}</p>
            </div>
          ))}
        </div>
        <div className="mt-4 rounded-md border border-line bg-fog/60 p-3 text-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Risk monitor</p>
          <p className="mt-2 text-slate-300">{packet?.riskMonitor ? `${packet.riskMonitor.status} / concentration ${packet.riskMonitor.concentrationRisk}` : "Not evaluated yet"}</p>
        </div>
      </Panel>

      <Panel className="p-5">
        <PanelHeader eyebrow="Outcome Loop" title="After decision" />
        <p className="mt-3 text-sm text-slate-400">
          Once a human decision is recorded, capture the outcome so Ambrosia can update history and calibration.
        </p>
        <button
          type="button"
          onClick={onRecordOutcome}
          disabled={Boolean(activeAction) || !review.decisionState}
          className="focus-ring mt-4 w-full rounded-md border border-line bg-paper px-3 py-2 text-sm font-semibold text-slate-200 hover:border-teal/50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Record outcome
        </button>
      </Panel>
    </div>
  );
}

function DecisionStrip({
  review,
  activeAction,
  onConfidenceChange,
  onDecision,
  suggestedDecision,
  advisoryReasons,
  pursueGateViolations
}: {
  review: TradeReview;
  activeAction: string | null;
  onConfidenceChange: (value: number) => void;
  onDecision: (decisionState: DecisionState, rationale?: string) => void;
  suggestedDecision: DecisionState | null;
  advisoryReasons: string[];
  pursueGateViolations: string[];
}) {
  const [overrideRationale, setOverrideRationale] = useState("");
  const [decisionError, setDecisionError] = useState<string | null>(null);

  function submitDecision(state: DecisionState) {
    if (state === "pursue" && pursueGateViolations.length > 0) {
      setDecisionError("Pursue is locked until the hard gate items are resolved. Watch, Reject, or Needs more data remain available.");
      return;
    }
    setDecisionError(null);
    onDecision(state, overrideRationale.trim() || undefined);
  }

  return (
    <Panel className="border-2 border-teal/40 bg-paper p-4 shadow-panel">
      <div className="grid gap-4 lg:grid-cols-[minmax(220px,0.8fr)_minmax(360px,1.2fr)_minmax(220px,0.8fr)] lg:items-center">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-teal">Decision controls</p>
          <p className="mt-1 text-sm text-slate-400">Human authority remains explicit. Ambrosia supports the decision; it does not make it.</p>
          {suggestedDecision ? (
            <p className="mt-2 text-xs text-amber">
              Soft policy suggests {decisionLabels[suggestedDecision]}; non-executing decisions remain available with optional rationale.
            </p>
          ) : null}
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-400">Confidence</span>
            <span className="font-semibold text-teal">{review.confidence}%</span>
          </div>
          <input
            aria-label="Confidence"
            type="range"
            min={0}
            max={100}
            value={review.confidence}
            onChange={(event) => onConfidenceChange(Number(event.target.value))}
            className="w-full accent-teal"
          />
          <p className="text-xs text-slate-500">
            Trial impact: +{review.trialCountImpact} / Follow-up: {review.followUpDate}
          </p>
          {advisoryReasons.length > 0 ? (
            <div className="rounded-md border border-amber/30 bg-amber/10 p-2 text-xs text-amber">
              {advisoryReasons.map((reason) => (
                <p key={reason}>{reason}</p>
              ))}
            </div>
          ) : null}
          {pursueGateViolations.length > 0 ? (
            <div className="rounded-md border border-coral/30 bg-coral/10 p-2 text-xs text-coral">
              <p className="font-semibold">Pursue and execution are locked until these hard gates clear:</p>
              {pursueGateViolations.map((reason) => (
                <p key={reason}>{reason}</p>
              ))}
              <p className="mt-1 text-slate-300">Watch, Reject, and Needs more data remain safe to record.</p>
            </div>
          ) : null}
          {suggestedDecision ? (
            <input
              value={overrideRationale}
              onChange={(event) => setOverrideRationale(event.target.value)}
              placeholder="Optional rationale when choosing outside the soft-policy suggestion"
              className="focus-ring w-full rounded-md border border-line bg-fog/70 px-2 py-1.5 text-xs text-slate-200"
            />
          ) : null}
          {decisionError ? <p className="text-xs text-amber">{decisionError}</p> : null}
        </div>
        <div className="grid grid-cols-2 gap-2">
          {(Object.entries(decisionLabels) as Array<[DecisionState, string]>).map(([state, label]) => (
            <button
              type="button"
              key={state}
              onClick={() => submitDecision(state)}
              disabled={Boolean(activeAction) || (state === "pursue" && pursueGateViolations.length > 0)}
              className={cn(
                "focus-ring rounded-md px-3 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50",
                review.decisionState === state
                  ? "bg-teal text-fog"
                  : suggestedDecision === state
                    ? "border border-amber/50 bg-amber/10 text-amber hover:border-amber"
                    : "border border-line bg-fog/70 text-slate-200 hover:border-teal/50"
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function WorkflowStageCard({ stage, currentStatus, review, packet }: { stage: WorkflowStage; currentStatus: ReviewStatus; review: TradeReview; packet: DecisionPacket | null }) {
  const currentIndex = statusOrder.indexOf(currentStatus);
  const stageIndex = statusOrder.indexOf(stage.status);
  const done = stageIndex < currentIndex || currentStatus === "decision_recorded";
  const active = stage.status === currentStatus && currentStatus !== "decision_recorded";
  const waiting = stageIndex > currentIndex;
  const Icon = done ? CheckCircle2 : active ? Clock3 : Circle;

  return (
    <details className={cn("rounded-md border p-3 text-sm", done ? "border-teal/30 bg-teal/5" : active ? "border-amber/40 bg-amber/5" : "border-line bg-fog/60")} open={active}>
      <summary className="flex cursor-pointer list-none items-start gap-3">
        <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", done ? "text-teal" : active ? "text-amber" : "text-slate-500")} />
        <span className="flex-1">
          <span className="block font-semibold">{stage.label}</span>
          <span className={cn("mt-1 block text-xs", waiting ? "text-slate-500" : "text-slate-300")}>{stage.summary}</span>
        </span>
      </summary>
      <div className="mt-3 border-t border-line pt-3 text-xs leading-5 text-slate-300">
        {stage.status === "validation" ? (
          <div className="space-y-2">
            <p>{review.validation.hypothesis}</p>
            <p className="text-slate-500">Null: {review.validation.nullHypothesis}</p>
            {review.validation.refusalReason ? <p className="text-amber">Refusal: {review.validation.refusalReason}</p> : null}
          </div>
        ) : stage.status === "tradeability" ? (
          <ul className="space-y-1">
            {review.tradeability.map((item) => (
              <li key={item.question}>{item.topic}: {item.question}</li>
            ))}
          </ul>
        ) : stage.status === "synthesis" && packet?.agentOutputs ? (
          <AgentOutputList packet={packet} />
        ) : (
          <p>{stage.summary}</p>
        )}
      </div>
    </details>
  );
}

function ProposalReview({ proposal, onSubmit, onRollback }: {
  proposal: PacketMutationProposal;
  onSubmit: (body: AdmissionRequest) => Promise<void>;
  onRollback: (rationale: string) => Promise<void>;
}) {
  const claims = proposal.originalOutput.materialClaims ?? [];
  const evidenceById = new Map(
    proposal.evidenceSnapshot.map((item) => [String(item.evidenceId ?? item.id ?? ""), item])
  );
  const [decisions, setDecisions] = useState<Record<string, "accept_as_proposed" | "accept_with_human_correction" | "reject">>(
    () => Object.fromEntries(claims.map((claim) => [claim.claimId, "reject"]))
  );
  const [corrections, setCorrections] = useState<Record<string, string>>({});
  const [rationale, setRationale] = useState("Reviewed against the immutable evidence snapshot.");
  const [submitting, setSubmitting] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  function validateCorrectionClaims(): string | null {
    const correctedClaims = claims.filter(
      (claim) => decisions[claim.claimId] === "accept_with_human_correction"
    );
    for (const claim of correctedClaims) {
      const correctedText = (corrections[claim.claimId] ?? claim.text ?? "").trim();
      if (!correctedText) {
        return `Correction text is required for ${claim.claimId}.`;
      }
      const supporting = (claim.supportingEvidenceIds ?? []).map((item) => String(item).trim()).filter(Boolean);
      if (supporting.length === 0) {
        return `At least one supporting evidence reference is required for corrected claim ${claim.claimId}.`;
      }
      if (supporting.some((item) => !evidenceById.has(item))) {
        return `Corrected claim ${claim.claimId} references evidence outside the immutable snapshot.`;
      }
      if (!String(claim.falsifier ?? "").trim()) {
        return `A falsifier is required for corrected factual claim ${claim.claimId}.`;
      }
    }
    return null;
  }

  async function submit(disposition: "accepted" | "corrected" | "rejected") {
    setValidationError(null);
    if (disposition !== "rejected") {
      const error = validateCorrectionClaims();
      if (error) {
        setValidationError(error);
        return;
      }
    }
    setSubmitting(true);
    try {
      await onSubmit({
        proposalId: proposal.id,
        expectedPacketVersion: proposal.basePacketVersion,
        expectedProposalHash: proposal.proposedPatchHash,
        disposition,
        claimDecisions: claims.map((claim) => ({
          claimId: claim.claimId,
          decision: disposition === "rejected" ? "reject" : decisions[claim.claimId],
          correctedText: decisions[claim.claimId] === "accept_with_human_correction" ? (corrections[claim.claimId] ?? claim.text) : undefined,
          supportingEvidenceIds: claim.supportingEvidenceIds,
          falsifier: claim.falsifier
        })),
        rationale
      });
    } catch (error) {
      if (error instanceof ApiProblemError && error.problem.code === "PROPOSAL_STALE") {
        setValidationError(
          "This proposal became stale before admission. Use Refresh evidence and rerun to create a new governed proposal."
        );
      } else {
        setValidationError(actionableApiError(error));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <details className="mt-3 rounded border border-amber/30 bg-amber/5 p-3" open={proposal.admissionState === "awaiting_human_review"}>
      <summary className="cursor-pointer font-semibold">Inspect immutable proposal · {proposal.admissionState}</summary>
      <div className="mt-3 space-y-3">
        <div className="grid gap-2 md:grid-cols-3">
          <ProofMetric label="Proposal hash" value={proposal.proposedPatchHash.slice(0, 20)} />
          <ProofMetric label="Evidence hash" value={proposal.evidencePackHash.slice(0, 20)} />
          <ProofMetric label="Model" value={`${proposal.modelName} · ${proposal.modelDigest.slice(0, 16)}`} />
        </div>
        {claims.map((claim) => (
          <div key={claim.claimId} className="rounded border border-line bg-white p-3">
            <p className="font-semibold">{claim.claimId}</p>
            <p className="mt-1 text-slate-700">{claim.text}</p>
            <p className="mt-1 text-slate-500">Evidence: {claim.supportingEvidenceIds?.join(", ") || "none"}</p>
            <div className="mt-2 space-y-2">
              {(claim.supportingEvidenceIds ?? []).map((evidenceId) => {
                const evidence = evidenceById.get(evidenceId);
                return (
                  <div key={evidenceId} className="rounded border border-line bg-fog/50 p-2">
                    <p className="font-semibold">{evidenceId} · {String(evidence?.dataMode ?? "unknown mode")}</p>
                    <p>Instrument: {String(evidence?.canonicalTicker ?? evidence?.subjectInstrumentId ?? "unknown")} · observed {String(evidence?.observedAt ?? "unknown")}</p>
                    <p>Trust: {String(evidence?.trustBoundary ?? "unknown")} · permission {String(evidence?.permission ?? "unknown")}</p>
                    <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap text-[10px]">{JSON.stringify(evidence?.content ?? {}, null, 2)}</pre>
                  </div>
                );
              })}
            </div>
            <div className="mt-2 text-slate-600">
              Findings: {proposal.deterministicFindings.filter((finding) => String(finding.claimId) === claim.claimId).map((finding) => `${String(finding.status)} (${String(finding.verifier ?? "deterministic")})`).join(", ") || "none"}
            </div>
            <p className="mt-1 text-slate-500">Report impact: {proposal.reviewImpact.filter((impact) => impact.claimId === claim.claimId).map((impact) => impact.reportSection).join(", ") || "none"}</p>
            <select
              className="mt-2 rounded border border-line px-2 py-1"
              value={decisions[claim.claimId]}
              onChange={(event) => setDecisions((current) => ({ ...current, [claim.claimId]: event.target.value as "accept_as_proposed" | "accept_with_human_correction" | "reject" }))}
            >
              <option value="accept_as_proposed">Accept as proposed</option>
              <option value="accept_with_human_correction">Correct with cited evidence and accept</option>
              <option value="reject">Reject</option>
            </select>
            {decisions[claim.claimId] === "accept_with_human_correction" ? (
              <textarea
                className="mt-2 w-full rounded border border-line p-2"
                value={corrections[claim.claimId] ?? claim.text}
                onChange={(event) => setCorrections((current) => ({ ...current, [claim.claimId]: event.target.value }))}
                aria-label={`Correction for ${claim.claimId}`}
              />
            ) : null}
          </div>
        ))}
        <textarea className="w-full rounded border border-line p-2" value={rationale} onChange={(event) => setRationale(event.target.value)} aria-label="Review rationale" />
        {validationError ? <p className="text-amber-800">{validationError}</p> : null}
        {proposal.admissionState === "awaiting_human_review" || proposal.admissionState === "proposed" ? (
          <div className="flex flex-wrap gap-2">
            <button disabled={submitting} className="rounded border border-teal px-3 py-1" onClick={() => submit(Object.values(decisions).includes("accept_with_human_correction") ? "corrected" : "accepted")}>Validate and admit selected claims</button>
            <button disabled={submitting} className="rounded border border-line px-3 py-1" onClick={() => submit("rejected")}>Reject proposal</button>
          </div>
        ) : null}
        {["auto_admitted", "human_admitted", "corrected_and_admitted"].includes(proposal.admissionState) ? (
          <button disabled={submitting} className="rounded border border-amber px-3 py-1" onClick={() => onRollback(rationale)}>Create compensating rollback version</button>
        ) : null}
        <p className="text-slate-500">Human admission is analytical approval, not trading authorization.</p>
        {proposal.proposalEvents.length ? (
          <details className="rounded border border-line p-2">
            <summary className="cursor-pointer font-semibold">Proposal event lineage</summary>
            {proposal.proposalEvents.map((event) => (
              <p key={String(event.eventHash)} className="mt-1 text-slate-500">{String(event.createdAt)} · {String(event.eventType)} · {String(event.actor)}</p>
            ))}
          </details>
        ) : null}
      </div>
    </details>
  );
}

function ProviderProvenancePanel({ packet, operation, proposal, onReviewProposal, onRollbackProposal, onCancel, onFallback, onContinue, onRetry, onRefreshAndRerun }: {
  packet: DecisionPacket | null;
  operation: AgentOperation | null;
  proposal: PacketMutationProposal | null;
  onReviewProposal: (body: AdmissionRequest) => Promise<void>;
  onRollbackProposal: (rationale: string) => Promise<void>;
  onCancel: () => void;
  onFallback: () => void;
  onContinue: () => void;
  onRetry: () => void;
  onRefreshAndRerun: () => void;
}) {
  const provider = packet?.providerInfo;
  const agentOutputs = packet?.agentOutputs ? Object.values(packet.agentOutputs).filter(Boolean) : [];
  const roleCount = agentOutputs.length;
  const provenance = packet?.provenance ?? [];
  const disconfirmation = packet?.disconfirmationResult;
  const riskGate = packet?.riskGateResult;
  const memoryRecords = packet?.memoryRecords ?? [];
  const integration = packet?.integrationStatus;

  return (
    <div className="mt-4 rounded-md border border-line bg-fog/60 p-3 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-semibold text-ink">Provider provenance</p>
          <p className="mt-1 text-ink/60">
            {provider ? `${provider.name} / ${provider.type}` : "Run analysis to expose provider mode, fallback chain, and role outputs."}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={provider?.fallbackUsed ? "warn" : provider ? "good" : "neutral"}>
            {provider ? (provider.fallbackUsed ? "Fallback used" : "No runtime fallback") : "Pending"}
          </Badge>
          <Badge tone="info">{roleCount}/{expectedAgentRoles.length} roles</Badge>
          <Badge tone={integration?.state === "promotable" || integration?.state === "decided" || integration?.state === "resolved" ? "good" : integration?.state === "blocked" ? "warn" : "neutral"}>
            {integration?.state ?? "not_started"}
          </Badge>
        </div>
      </div>
      {provider ? (
        <div className="mt-3 grid gap-2 md:grid-cols-3">
          <ProofMetric label="Fallback chain" value={provider.fallbackChain.join(" -> ")} />
          <ProofMetric label="Reason" value={provider.reason} />
          <ProofMetric label="Coordinator" value={packet?.coordinatorVersion ?? "coordinator.v1"} />
          <ProofMetric label="Requested / actual" value={`${provider.requestedProvider ?? provider.type} / ${provider.actualProvider ?? provider.type}`} />
          <ProofMetric label="Model digest" value={provider.modelDigest ?? "Not reported"} />
          <ProofMetric label="Worker" value={provider.workerId ?? "Hosted coordinator"} />
        </div>
      ) : null}
      {operation ? (
        <div className="mt-3 rounded border border-line bg-white p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold">Ollama execution: {operation.state}</p>
            <Badge tone={operation.state === "completed" ? "good" : operation.state === "failed" ? "warn" : "info"}>
              {operation.progress}% · {operation.stage}
            </Badge>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded bg-fog"><div className="h-full bg-sky-500" style={{ width: `${operation.progress}%` }} /></div>
          <div className="mt-2 grid gap-2 md:grid-cols-3">
            <ProofMetric label="Provider requested" value="Ollama" />
            <ProofMetric label="Worker" value={operation.workerName ?? operation.workerId ?? "Waiting for compatible worker"} />
            <ProofMetric label="Elapsed" value={`${Math.max(0, Math.floor((Date.now() - Date.parse(operation.createdAt)) / 1000))}s`} />
            <ProofMetric label="Deadline" value={new Date(operation.deadlineAt).toLocaleString()} />
            <ProofMetric label="Verification" value={operation.verificationStatus ?? "Pending server admission"} />
            <ProofMetric label="Admission" value={operation.admissionState ?? "Not available"} />
            <ProofMetric label="Result packet" value={operation.resultPacketVersion ? `v${operation.resultPacketVersion}` : "No packet mutation"} />
            <ProofMetric label="Model" value={operation.modelName ? `${operation.modelName} · ${(operation.modelDigest ?? "").slice(0, 16)}` : "Pending claim"} />
          </div>
          {operation.error ? <p className="mt-2 text-amber-800">{operation.error.code}: {operation.error.message}</p> : null}
          <div className="mt-3 flex gap-2">
            {!TERMINAL_AGENT_OPERATION_STATES.has(operation.state) ? <button className="rounded border border-line px-3 py-1" onClick={onCancel}>Cancel</button> : null}
            {operation.state === "expired" ? <button className="rounded border border-line px-3 py-1" onClick={onContinue}>Continue waiting</button> : null}
            {["failed", "dead_letter", "expired", "superseded"].includes(operation.state) ? <button className="rounded border border-line px-3 py-1" onClick={onRetry}>Retry Ollama</button> : null}
            {["failed", "dead_letter", "expired", "superseded"].includes(operation.state) ? <button className="rounded border border-line px-3 py-1" onClick={onFallback}>Run explicit deterministic fallback</button> : null}
            {(operation.state === "superseded" || proposal?.admissionState === "stale") ? (
              <button className="rounded border border-amber px-3 py-1" onClick={onRefreshAndRerun}>
                Refresh evidence and rerun
              </button>
            ) : null}
          </div>
          {proposal ? <ProposalReview proposal={proposal} onSubmit={onReviewProposal} onRollback={onRollbackProposal} /> : null}
        </div>
      ) : null}
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        <ProofMetric label="Provenance sources" value={provenance.length ? provenance.map((item) => item.source).join(", ") : "No provenance attached yet"} />
        <ProofMetric label="Disconfirmation" value={disconfirmation ? `${disconfirmation.status} (${disconfirmation.requiresHumanReview ? "needs review" : "auto-pass"})` : "Pending"} />
      </div>
      <div className="mt-2 grid gap-2 md:grid-cols-2">
        <ProofMetric label="Risk gate" value={riskGate ? `${riskGate.status} ${riskGate.reasons.length ? `- ${riskGate.reasons.join(", ")}` : ""}`.trim() : "Pending"} />
        <ProofMetric label="Memory records" value={memoryRecords.length ? `${memoryRecords.length} record(s) stored` : "No memory records yet"} />
      </div>
      <div className="mt-2 grid gap-2 md:grid-cols-2">
        <ProofMetric label="Next governed action" value={integration?.nextAction ?? "Run selective integration before recording a decision."} />
        <ProofMetric label="Workflow blockers" value={integration?.blockers.length ? integration.blockers.join("; ") : "None recorded"} />
      </div>
      {provenance.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {provenance.map((item) => (
            <Badge key={item.envelopeId ?? `${item.source}-${item.timestamp}`} tone={item.stale || item.coverageStatus === "unavailable" ? "warn" : item.dataMode === "live" ? "good" : "neutral"}>
              {item.source}: {item.dataMode ?? "unknown"} / {item.coverageStatus ?? "unknown"}{item.stale ? " / stale" : ""}
            </Badge>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function AgentOutputList({ packet }: { packet: DecisionPacket }) {
  const agents = packet.agentOutputs ? Object.values(packet.agentOutputs).flatMap((agent) => (agent ? [agent] : [])) : [];
  return (
    <ul className="space-y-2">
      {agents.map((agent) => (
        <li key={`${agent.role}-${agent.timestamp}`} className="rounded-md border border-line bg-paper/70 p-2">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="font-semibold text-ink">{agent.role}</p>
              <p className="mt-1">{agent.summary}</p>
            </div>
            <div className="flex flex-wrap gap-1">
              <Badge tone={agent.fallbackUsed ? "warn" : "good"}>{agent.fallbackUsed ? "fallback" : "primary"}</Badge>
              <Badge tone="neutral">{agent.provider}</Badge>
              {agent.score !== null ? <Badge tone="info">{agent.score}</Badge> : null}
              <Badge tone={agent.verificationStatus === "passed" || agent.verificationStatus === "repaired" ? "good" : agent.verificationStatus === "human_review" ? "warn" : "neutral"}>{agent.verificationStatus ?? "unverified"}</Badge>
            </div>
          </div>
          <p className="mt-2 text-[11px] text-slate-500">{agent.timestamp}</p>
        </li>
      ))}
    </ul>
  );
}

function ProofMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-paper/80 p-2">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-slate-300">{value}</p>
    </div>
  );
}

function buildWorkflowStages(review: TradeReview, packet: DecisionPacket | null): WorkflowStage[] {
  return [
    { status: "intake", label: statusLabels.intake, summary: `${review.ticker} thesis normalized into a review packet.` },
    { status: "retrieval", label: statusLabels.retrieval, summary: `${review.sources.length} source pointer${review.sources.length === 1 ? "" : "s"} available for review context.` },
    { status: "adversarial_review", label: statusLabels.adversarial_review, summary: review.strongestCritique },
    { status: "validation", label: statusLabels.validation, summary: review.validation.status === "refused" ? "Validation refused until the evidence contract is tighter." : "Validation protocol is specified." },
    { status: "tradeability", label: statusLabels.tradeability, summary: `${review.tradeability.length} tradeability question${review.tradeability.length === 1 ? "" : "s"} must be answered before action.` },
    { status: "synthesis", label: statusLabels.synthesis, summary: packet?.providerInfo ? `Coordinator output available from ${packet.providerInfo.name}.` : `Current confidence is ${review.confidence}%.` },
    { status: "decision_recorded", label: statusLabels.decision_recorded, summary: review.decisionState ? `Human decision: ${decisionLabels[review.decisionState]}.` : "Awaiting human decision." }
  ];
}

function ActionButton({ label, icon, activeAction, onClick, compact = false }: { label: string; icon: React.ReactNode; activeAction: string | null; onClick: () => void; compact?: boolean }) {
  const running = activeAction === label;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={Boolean(activeAction)}
      className={cn(
        "focus-ring inline-flex items-center justify-center gap-2 rounded-md border border-line bg-fog/70 font-semibold text-slate-200 transition hover:border-teal/50 disabled:cursor-not-allowed disabled:opacity-50",
        compact ? "px-2.5 py-1.5 text-xs" : "px-3 py-2 text-xs"
      )}
    >
      {icon}
      {running ? "Running..." : label}
    </button>
  );
}

function PanelHeader({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-teal">{eyebrow}</p>
      <h2 className="text-base font-semibold text-ink">{title}</h2>
    </div>
  );
}

function ContextMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-fog/60 p-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-200">{value}</p>
    </div>
  );
}

function ClaimRow({ claim }: { claim: Claim }) {
  return (
    <li className="rounded-md border border-line bg-fog/60 p-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm text-slate-200">{claim.text}</p>
        <Badge tone={claim.kind === "contradiction" ? "warn" : claim.kind === "sourced" ? "good" : "neutral"}>{claim.kind}</Badge>
      </div>
      <p className="mt-2 text-xs text-slate-500">Confidence: {claim.confidence}%{claim.evidence ? ` / ${claim.evidence}` : ""}</p>
    </li>
  );
}

function SourceRow({ source }: { source: SourcePointer }) {
  return (
    <li className="rounded-md border border-line bg-fog/60 p-3 text-sm">
      <p className="font-semibold text-slate-200">{source.title}</p>
      <p className="mt-1 text-xs text-slate-500">
        {source.sourceType} / {source.timestamp} / relevance {Math.round(source.relevance * 100)}%
      </p>
    </li>
  );
}

function EvidenceBlock({ label, text, tone }: { label: string; text: string; tone: "warn" | "info" }) {
  return (
    <div className={cn("rounded-md border p-3 text-sm", tone === "warn" ? "border-amber/30 bg-amber/5" : "border-violet/30 bg-violet/5")}>
      <p className={cn("text-xs font-semibold uppercase tracking-wide", tone === "warn" ? "text-amber" : "text-violet")}>{label}</p>
      <p className="mt-2 leading-5 text-slate-200">{text}</p>
    </div>
  );
}

function MetricRow({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "neutral" | "good" | "warn" }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-line bg-fog/60 px-3 py-2">
      <span className="text-slate-400">{label}</span>
      <span className={cn("font-semibold", tone === "good" ? "text-teal" : tone === "warn" ? "text-amber" : "text-slate-200")}>{value}</span>
    </div>
  );
}

function compactNumber(value: number) {
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function buildLocalReportArtifact(review: TradeReview, packet: DecisionPacket | null): ReportArtifact {
  const agentSummaries = packet?.agentOutputs
    ? Object.values(packet.agentOutputs).flatMap((agent) =>
        agent
          ? [`- ${agent.role}: ${agent.summary}${agent.score !== null ? ` (score ${agent.score})` : ""}; provider ${agent.provider}; fallback ${agent.fallbackUsed ? "yes" : "no"}`]
          : []
      )
    : [];
  const auditTrail = review.audit.slice(-8).map((event) => `- ${event.eventType}: ${event.detail}`);
  const riskSummary = packet?.riskMonitor
    ? `Risk monitor status: ${packet.riskMonitor.status}. Concentration risk: ${packet.riskMonitor.concentrationRisk}. Max drawdown threshold: ${Math.round(packet.riskMonitor.maxDrawdownThreshold * 100)}%.`
    : `Risk monitor not yet evaluated. Tradeability checks: ${review.tradeability.map((item) => `${item.topic}: ${item.question}`).join(" | ")}`;
  const confidenceSummary = packet?.confidenceBreakdown
    ? `Overall confidence: ${packet.confidenceBreakdown.overallConfidence}%. Evidence ${packet.confidenceBreakdown.evidenceScore} / technical ${packet.confidenceBreakdown.technicalScore} / sentiment ${packet.confidenceBreakdown.sentimentScore}. Blockers: ${packet.confidenceBreakdown.blockers.join("; ") || "none"}.`
    : `Current review confidence: ${review.confidence}%. Confidence breakdown has not been derived yet.`;

  return {
    packetId: packet?.id ?? `pkt-${review.id}`,
    ticker: review.ticker,
    title: `Investment Decision Report: ${review.ticker}`,
    createdAt: new Date().toISOString(),
    sections: [
      {
        title: "Decision Context",
        content: [
          `Review: ${review.title}`,
          `Thesis: ${review.thesis}`,
          `Intended expression: ${review.intendedExpression}`,
          `Time horizon: ${review.timeHorizon}`,
          `Human decision state: ${review.decisionState ? decisionLabels[review.decisionState] : "pending"}`
        ].join("\n\n")
      },
      {
        title: "Unverified Local Continuity Report",
        content: "Explicit development continuity mode produced this browser-only artifact. It is not a governed ticker-intelligence report and its agent prose has not passed server claim-level verification.", evidenceMode:"unavailable", verificationStatus:"unverified"
      },
      {
        title: "Investment Trading Decision Evidence",
        content: [
          confidenceSummary,
          riskSummary,
          `Strongest critique: ${review.strongestCritique}`,
          `Disconfirming test: ${review.disconfirmingTest}`
        ].join("\n\n")
      },
      {
        title: "Swarm Intelligence and Agentic Swarm",
        content: agentSummaries.length > 0 ? agentSummaries.join("\n") : "Agent swarm outputs have not been run for this browser session. The report preserves this as missing evidence rather than inventing specialist conclusions."
      },
      {
        title: "Audit Trail",
        content: auditTrail.length > 0 ? auditTrail.join("\n") : "No audit events attached to this review yet."
      }
    ],
    dataMode: "demo",
    provenanceLabel: "Client-side development continuity artifact generated without governed server report evidence.",
    marketDataSource: packet?.marketSnapshot?.dataSource ?? null,
    marketDataFreshnessSeconds: null
    ,schemaVersion:"continuity-report.v1",verifiedClaimCoverage:0,unresolvedMaterialClaimCount:0,reportValidationStatus:"legacy"
  };
}

function downloadReportArtifact(report: ReportArtifact) {
  if (typeof window === "undefined") return;
  const markdown = renderReportMarkdown(report);
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${safeFilename(report.ticker)}-investment-decision-report.md`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

function renderReportMarkdown(report: ReportArtifact) {
  const metadata = [
    `# ${report.title}`,
    "",
    `Ticker: ${report.ticker}`,
    `Packet ID: ${report.packetId}`,
    `Generated: ${formatReportTimestamp(report.createdAt)}`,
    `Data mode: ${report.dataMode}`,
    `Provenance: ${report.provenanceLabel}`,
    `Validation: ${report.reportValidationStatus ?? "legacy"}`,
    `Verified claim coverage: ${Math.round((report.verifiedClaimCoverage ?? 0)*100)}%`,
    report.marketDataSource ? `Market data source: ${report.marketDataSource}` : "Market data source: none attached",
    report.marketDataFreshnessSeconds !== null ? `Market data freshness: ${report.marketDataFreshnessSeconds}s` : "Market data freshness: unavailable",
    ""
  ];

  const sections = report.sections.flatMap((section) => [`## ${section.title}`, "", section.content, ""]);
  return [...metadata, ...sections].join("\n");
}

function safeFilename(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "ambrosia";
}

function formatReportTimestamp(value: string) {
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) return value;
  return new Date(timestamp).toISOString();
}

function mergeReviews(apiReviews: TradeReview[], localReviews: TradeReview[]): TradeReview[] {
  const apiMap = new Map(apiReviews.map((review) => [review.id, review]));
  const merged = [...apiReviews];
  for (const local of localReviews) {
    if (!apiMap.has(local.id)) {
      merged.push(local);
    }
  }
  return merged;
}
