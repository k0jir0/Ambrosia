import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator, type NativeStackScreenProps } from "@react-navigation/native-stack";
import { StatusBar } from "expo-status-bar";
import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Linking,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View
} from "react-native";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import {
  alphaKey,
  buildReviewInputFromScannerCandidate,
  constrainSignal,
  createReview,
  getApiBaseUrl,
  getReviewSummary,
  getSignalDecisionReadiness,
  loadMobileDataset,
  promoteSignal,
  promoteScannerCandidate,
  recordReviewDecision,
  recordReviewOutcome,
  retireSignal,
  signalKey,
  validateSignal
} from "./src/api";
import { buildSampleDataset } from "./src/sample-data";
import { ActionButton, Badge, Card, Metric, SectionTitle } from "./src/components";
import { colors, radius, spacing } from "./src/theme";
import { linkingConfig, type RootStackParamList } from "./src/navigation";
import { queueReviewDraft, readQueuedDrafts, type QueuedDraft } from "./src/storage";
import {
  addNotificationResponseListener,
  requestNotificationPermissions,
  targetFromNotificationResponse,
  targetFromUrl,
  type NotificationTarget
} from "./src/notifications";
import type {
  CreateReviewInput,
  DecisionState,
  MobileDataset,
  MobileReviewSummary,
  MobileSignalDecisionReadiness,
  ModuleId,
  PriorityItem,
  ScannerCandidate,
  SignalRecord,
  TradeReview
} from "./src/types";

type SignalLifecycleAction = "validate" | "promote" | "constrain" | "retire";
type WorkbenchProps = {
  initialModule?: ModuleId;
  initialReviewId?: string;
  initialSignalId?: string;
};
type MainScreenProps = NativeStackScreenProps<RootStackParamList, "Main">;
type ReviewScreenProps = NativeStackScreenProps<RootStackParamList, "ReviewDetail">;
type SignalScreenProps = NativeStackScreenProps<RootStackParamList, "SignalDetail">;
type ScannerScreenProps = NativeStackScreenProps<RootStackParamList, "ScannerCandidateDetail">;
type AlphaScreenProps = NativeStackScreenProps<RootStackParamList, "AlphaHypothesisDetail">;
type HistoryScreenProps = NativeStackScreenProps<RootStackParamList, "DecisionHistoryDetail">;

const Stack = createNativeStackNavigator<RootStackParamList>();

const MODULES: Array<{ id: ModuleId; label: string }> = [
  { id: "today", label: "Today" },
  { id: "reviews", label: "Reviews" },
  { id: "scanner", label: "Scanner" },
  { id: "signals", label: "Signals" },
  { id: "alpha", label: "Alpha" },
  { id: "history", label: "History" },
  { id: "enterprise", label: "Enterprise" }
];

const emptyReviewInput: CreateReviewInput = {
  thesis: "A market setup deserves adversarial review before capital is put at risk.",
  ticker: "SPY",
  assetClass: "US equities",
  timeHorizon: "1-4 weeks",
  intendedExpression: "Watchlist review",
  sourcePointer: "Mobile intake"
};

export default function App() {
  return (
    <SafeAreaProvider>
      <NavigationContainer linking={linkingConfig}>
        <Stack.Navigator screenOptions={{ headerShown: false }}>
          <Stack.Screen name="Main" component={MainScreen} />
          <Stack.Screen name="ReviewDetail" component={ReviewDeepLinkScreen} />
          <Stack.Screen name="ScannerCandidateDetail" component={ScannerDeepLinkScreen} />
          <Stack.Screen name="SignalDetail" component={SignalDeepLinkScreen} />
          <Stack.Screen name="AlphaHypothesisDetail" component={AlphaDeepLinkScreen} />
          <Stack.Screen name="DecisionHistoryDetail" component={HistoryDeepLinkScreen} />
          <Stack.Screen name="EnterpriseStatusDetail" component={EnterpriseDeepLinkScreen} />
        </Stack.Navigator>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}

function MainScreen({ route }: MainScreenProps) {
  return <MobileWorkbench initialModule={route.params?.module ?? "today"} />;
}

function ReviewDeepLinkScreen({ route }: ReviewScreenProps) {
  return <MobileWorkbench initialModule="reviews" initialReviewId={route.params.reviewId} />;
}

function ScannerDeepLinkScreen({ route }: ScannerScreenProps) {
  return <MobileWorkbench initialModule="scanner" />;
}

function SignalDeepLinkScreen({ route }: SignalScreenProps) {
  return <MobileWorkbench initialModule="signals" initialSignalId={route.params.signalId} />;
}

function AlphaDeepLinkScreen({ route }: AlphaScreenProps) {
  return <MobileWorkbench initialModule="alpha" />;
}

function HistoryDeepLinkScreen({ route }: HistoryScreenProps) {
  return <MobileWorkbench initialModule="history" initialReviewId={route.params.reviewId} />;
}

function EnterpriseDeepLinkScreen() {
  return <MobileWorkbench initialModule="enterprise" />;
}

function MobileWorkbench({ initialModule = "today", initialReviewId, initialSignalId }: WorkbenchProps) {
  const [activeModule, setActiveModule] = useState<ModuleId>(initialModule);
  const [dataset, setDataset] = useState<MobileDataset>(() => buildSampleDataset(getApiBaseUrl()));
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reviewInput, setReviewInput] = useState<CreateReviewInput>(emptyReviewInput);
  const [selectedReviewSummary, setSelectedReviewSummary] = useState<MobileReviewSummary | null>(null);
  const [selectedSignalReadiness, setSelectedSignalReadiness] = useState<MobileSignalDecisionReadiness | null>(null);
  const [queuedDrafts, setQueuedDrafts] = useState<QueuedDraft[]>([]);

  const pendingReviews = useMemo(
    () => dataset.reviews.filter((review) => review.decisionState === null),
    [dataset.reviews]
  );

  async function refresh() {
    setLoading(true);
    setError(null);
    const next = await loadMobileDataset();
    setDataset(next);
    setError(next.source === "sample" ? "API unavailable or incomplete; mobile is showing deterministic fallback data." : null);
    setLoading(false);
  }

  async function openReview(reviewId: string) {
    setActiveModule("reviews");
    setSelectedSignalReadiness(null);
    setDetailLoading(true);
    setError(null);
    try {
      setSelectedReviewSummary(await getReviewSummary(reviewId));
    } catch {
      const localReview = dataset.reviews.find((review) => review.id === reviewId);
      if (localReview) {
        setSelectedReviewSummary(buildLocalReviewSummary(localReview));
        setError("Live review summary could not be loaded; showing the local review snapshot.");
      } else {
        setError("Review summary could not be loaded.");
      }
    } finally {
      setDetailLoading(false);
    }
  }

  async function openSignal(signalId: string) {
    setActiveModule("signals");
    setSelectedReviewSummary(null);
    setDetailLoading(true);
    setError(null);
    try {
      setSelectedSignalReadiness(await getSignalDecisionReadiness(signalId));
    } catch {
      const localSignal = dataset.signals.find((signal) => signalKey(signal) === signalId);
      if (localSignal) {
        setSelectedSignalReadiness(buildLocalSignalReadiness(localSignal));
        setError("Live signal readiness could not be loaded; showing the local signal snapshot.");
      } else {
        setError("Signal readiness could not be loaded.");
      }
    } finally {
      setDetailLoading(false);
    }
  }

  async function submitReview() {
    setLoading(true);
    setError(null);
    try {
      const review = await createReview(reviewInput);
      setDataset((current) => withUpdatedReview(current, review, "api"));
      Alert.alert("Review created", `${review.ticker} is ready for adversarial review.`);
      setActiveModule("reviews");
      await openReview(review.id);
    } catch {
      const draft = await queueReviewDraft(reviewInput, "Review creation failed before server confirmation.");
      setQueuedDrafts((current) => [draft, ...current]);
      const fallback = buildSampleDataset(dataset.apiUrl);
      setDataset((current) => ({
        ...current,
        source: "sample",
        reviews: [...fallback.reviews, ...current.reviews],
        loadedAt: new Date().toISOString()
      }));
      setError("Review creation could not reach the API; local sample reviews were added for continuity.");
    } finally {
      setLoading(false);
    }
  }

  async function submitDecision(reviewId: string, decisionState: DecisionState) {
    setLoading(true);
    setError(null);
    try {
      const review = await recordReviewDecision(reviewId, decisionState);
      setDataset((current) => withUpdatedReview(current, review, "api"));
      setSelectedReviewSummary(await getReviewSummary(review.id));
      Alert.alert("Decision recorded", `${review.ticker} is now ${formatLabel(decisionState)}.`);
    } catch {
      setError("Decision writeback failed. Check API connectivity before treating the decision as recorded.");
    } finally {
      setLoading(false);
    }
  }

  async function submitOutcome(reviewId: string) {
    setLoading(true);
    setError(null);
    try {
      const review = await recordReviewOutcome(
        reviewId,
        "Mobile monitoring checkpoint recorded",
        new Date().toISOString().slice(0, 10)
      );
      setDataset((current) => withUpdatedReview(current, review, "api"));
      setSelectedReviewSummary(await getReviewSummary(review.id));
      Alert.alert("Outcome recorded", `${review.ticker} received a mobile outcome checkpoint.`);
    } catch {
      setError("Outcome writeback failed. The review was not updated on the server.");
    } finally {
      setLoading(false);
    }
  }

  async function submitPromoteCandidate(candidate: ScannerCandidate) {
    setLoading(true);
    setError(null);
    try {
      const promotion = await promoteScannerCandidate(candidate);
      setDataset((current) => withPromotion(current, promotion));
      Alert.alert("Candidate promoted", `${candidate.ticker} was promoted into the Alpha and Signals workflow.`);
      if (promotion.signal) {
        await openSignal(signalKey(promotion.signal));
      } else {
        setActiveModule("alpha");
      }
    } catch {
      setError("Scanner promotion failed. Candidate remains available for review intake.");
    } finally {
      setLoading(false);
    }
  }

  async function submitSignalLifecycleAction(signalId: string, action: SignalLifecycleAction) {
    setLoading(true);
    setError(null);
    try {
      const operations: Record<SignalLifecycleAction, (target: string) => Promise<Record<string, unknown>>> = {
        validate: validateSignal,
        promote: promoteSignal,
        constrain: constrainSignal,
        retire: retireSignal
      };
      await operations[action](signalId);
      const readiness = await getSignalDecisionReadiness(signalId);
      setSelectedSignalReadiness(readiness);
      setDataset((current) => withUpdatedSignal(current, readiness.signal));
      Alert.alert("Signal updated", `${readiness.signal.name} is now ${readiness.signal.status}.`);
    } catch {
      setError(`${formatLabel(action)} failed. The server did not confirm the signal policy change.`);
    } finally {
      setLoading(false);
    }
  }

  function handleTarget(target: NotificationTarget | null) {
    if (!target) {
      return;
    }
    if ("reviewId" in target) {
      void openReview(target.reviewId);
      return;
    }
    if ("signalId" in target) {
      void openSignal(target.signalId);
      return;
    }
    setActiveModule(target.module);
  }

  useEffect(() => {
    let mounted = true;
    void refresh();
    void readQueuedDrafts().then((drafts) => {
      if (mounted) {
        setQueuedDrafts(drafts);
      }
    });
    void Linking.getInitialURL().then((url: string | null) => {
      if (mounted && url) {
        handleTarget(targetFromUrl(url));
      }
    });
    const urlSubscription = Linking.addEventListener("url", ({ url }: { url: string }) => {
      handleTarget(targetFromUrl(url));
    });
    const notificationSubscription = addNotificationResponseListener((response) => {
      handleTarget(targetFromNotificationResponse(response));
    });
    return () => {
      mounted = false;
      urlSubscription.remove();
      notificationSubscription.remove();
    };
  }, []);

  useEffect(() => {
    if (initialReviewId) {
      void openReview(initialReviewId);
    }
  }, [initialReviewId]);

  useEffect(() => {
    if (initialSignalId) {
      void openSignal(initialSignalId);
    }
  }, [initialSignalId]);

  async function enableMobileAlerts() {
    const granted = await requestNotificationPermissions();
    Alert.alert(
      granted ? "Alerts enabled" : "Alerts unavailable",
      granted
        ? "Ambrosia can now route review and signal alerts into the mobile workbench."
        : "Notifications were not enabled. The app remains usable; review and signal state still refresh from the API."
    );
  }

  return (
    <SafeAreaView edges={["top", "right", "bottom", "left"]} style={styles.safeArea}>
      <StatusBar style="dark" />
      <View style={styles.header}>
        <View style={styles.headerTop}>
          <View style={styles.headerText}>
            <Text style={styles.kicker}>Ambrosia Mobile</Text>
            <Text style={styles.headline}>Investment decisions, compressed for triage.</Text>
          </View>
          <Badge tone={dataset.source === "api" ? "good" : "warn"}>{dataset.source.toUpperCase()}</Badge>
        </View>
        <Text style={styles.apiText} numberOfLines={1}>
          API: {dataset.apiUrl}
        </Text>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.moduleTabsScroller}
        contentContainerStyle={styles.moduleTabs}
      >
        {MODULES.map((module) => {
          const active = module.id === activeModule;
          return (
            <Pressable
              accessibilityRole="tab"
              accessibilityState={{ selected: active }}
              key={module.id}
              onPress={() => {
                setActiveModule(module.id);
                if (module.id !== "reviews") {
                  setSelectedReviewSummary(null);
                }
                if (module.id !== "signals") {
                  setSelectedSignalReadiness(null);
                }
              }}
              style={[styles.moduleTab, active ? styles.moduleTabActive : null]}
            >
              <Text style={[styles.moduleTabText, active ? styles.moduleTabTextActive : null]}>{module.label}</Text>
            </Pressable>
          );
        })}
      </ScrollView>

      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} tintColor={colors.teal} />}
      >
        {error ? (
          <Card style={styles.warningCard}>
            <Text style={styles.warningTitle}>Attention</Text>
            <Text style={styles.bodyText}>{error}</Text>
          </Card>
        ) : null}

        {activeModule === "today" ? (
          <TodayScreen
            dataset={dataset}
            pendingReviews={pendingReviews}
            queuedDrafts={queuedDrafts}
            onNavigate={setActiveModule}
            onOpenReview={openReview}
            onOpenSignal={openSignal}
            onRefresh={refresh}
          />
        ) : null}
        {activeModule === "reviews" ? (
          <ReviewsScreen
            detailLoading={detailLoading}
            input={reviewInput}
            loading={loading}
            onBack={() => setSelectedReviewSummary(null)}
            onChangeInput={setReviewInput}
            onDecision={submitDecision}
            onOutcome={submitOutcome}
            onSelectReview={openReview}
            onSubmit={submitReview}
            queuedDrafts={queuedDrafts}
            reviews={dataset.reviews}
            selectedSummary={selectedReviewSummary}
          />
        ) : null}
        {activeModule === "scanner" ? (
          <ScannerScreen
            candidates={dataset.scannerCandidates}
            loading={loading}
            onCreateReview={(candidate) => {
              setReviewInput(buildReviewInputFromScannerCandidate(candidate));
              setSelectedReviewSummary(null);
              setActiveModule("reviews");
            }}
            onPromoteCandidate={submitPromoteCandidate}
          />
        ) : null}
        {activeModule === "signals" ? (
          <SignalsScreen
            detailLoading={detailLoading}
            onBack={() => setSelectedSignalReadiness(null)}
            onSignalAction={submitSignalLifecycleAction}
            onSelectSignal={openSignal}
            selectedReadiness={selectedSignalReadiness}
            signals={dataset.signals}
          />
        ) : null}
        {activeModule === "alpha" ? <AlphaScreen dataset={dataset} /> : null}
        {activeModule === "history" ? <HistoryScreen reviews={dataset.reviews} onOpenReview={openReview} /> : null}
        {activeModule === "enterprise" ? (
          <EnterpriseScreen dataset={dataset} onRequestNotifications={enableMobileAlerts} />
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

function TodayScreen({
  dataset,
  pendingReviews,
  queuedDrafts,
  onNavigate,
  onOpenReview,
  onOpenSignal,
  onRefresh
}: {
  dataset: MobileDataset;
  pendingReviews: TradeReview[];
  queuedDrafts: QueuedDraft[];
  onNavigate: (module: ModuleId) => void;
  onOpenReview: (reviewId: string) => void;
  onOpenSignal: (signalId: string) => void;
  onRefresh: () => void;
}) {
  return (
    <View style={styles.screen}>
      <View style={styles.metricsGrid}>
        <Metric label="Pending Reviews" value={String(dataset.summary.pendingReviews)} note="Need human decision" />
        <Metric label="Decisions" value={String(dataset.summary.decidedReviews)} note="Recorded in memory" />
        <Metric label="Signals" value={String(dataset.summary.activeSignals)} note="Active or hypothesis" />
        <Metric label="Scanner" value={String(dataset.scannerCandidates.length)} note="Current candidates" />
        <Metric label="Queued Drafts" value={String(queuedDrafts.length)} note="Awaiting server confirmation" />
      </View>

      <Card>
        <SectionTitle
          eyebrow="Priority Queue"
          title="What needs attention"
          action={<ActionButton label="Refresh" onPress={onRefresh} secondary />}
        />
        {dataset.priorityQueue.length > 0 ? (
          dataset.priorityQueue.map((item) => (
            <PriorityRow
              item={item}
              key={`${item.kind}-${item.id}`}
              onPress={() => {
                if (item.kind.includes("review")) {
                  onOpenReview(item.id);
                } else if (item.kind.includes("signal")) {
                  onOpenSignal(item.id);
                }
              }}
            />
          ))
        ) : pendingReviews.length > 0 ? (
          pendingReviews.slice(0, 4).map((review) => (
            <ReviewRow compact key={review.id} onPress={() => onOpenReview(review.id)} review={review} />
          ))
        ) : (
          <Text style={styles.bodyText}>No pending reviews. Scanner and Signals remain available for new intake.</Text>
        )}
      </Card>

      <Card>
        <SectionTitle eyebrow="Mobile Handoff" title="Exact web loop, mobile-sized" />
        <Text style={styles.bodyText}>
          Scanner, Alpha, Signals, Review, History, and Enterprise state all read from Ambrosia API contracts. Mobile
          captures fast triage and pushes deeper work back into the full web workbench.
        </Text>
        <View style={styles.buttonRow}>
          <ActionButton label="Create Review" onPress={() => onNavigate("reviews")} />
          <ActionButton label="Open Signals" onPress={() => onNavigate("signals")} secondary />
        </View>
      </Card>
    </View>
  );
}

function ReviewsScreen({
  detailLoading,
  input,
  loading,
  onBack,
  onChangeInput,
  onDecision,
  onOutcome,
  onSelectReview,
  onSubmit,
  queuedDrafts,
  reviews,
  selectedSummary
}: {
  detailLoading: boolean;
  input: CreateReviewInput;
  loading: boolean;
  onBack: () => void;
  onChangeInput: (input: CreateReviewInput) => void;
  onDecision: (reviewId: string, decisionState: DecisionState) => void;
  onOutcome: (reviewId: string) => void;
  onSelectReview: (reviewId: string) => void;
  onSubmit: () => void;
  queuedDrafts: QueuedDraft[];
  reviews: TradeReview[];
  selectedSummary: MobileReviewSummary | null;
}) {
  if (selectedSummary) {
    return (
      <ReviewDetailScreen
        loading={loading || detailLoading}
        onBack={onBack}
        onDecision={onDecision}
        onOutcome={onOutcome}
        summary={selectedSummary}
      />
    );
  }

  return (
    <View style={styles.screen}>
      <Card>
        <SectionTitle eyebrow="New Review" title="Adversarial review intake" />
        <Field label="Ticker" value={input.ticker} onChangeText={(ticker) => onChangeInput({ ...input, ticker })} />
        <Field
          label="Thesis"
          multiline
          value={input.thesis}
          onChangeText={(thesis) => onChangeInput({ ...input, thesis })}
        />
        <Field
          label="Intended Expression"
          value={input.intendedExpression}
          onChangeText={(intendedExpression) => onChangeInput({ ...input, intendedExpression })}
        />
        <View style={styles.buttonRow}>
          <ActionButton disabled={loading || input.thesis.trim().length < 8} label="Create Review" onPress={onSubmit} />
        </View>
      </Card>

      {queuedDrafts.length > 0 ? (
        <Card>
          <SectionTitle eyebrow="Queued" title="Drafts waiting for API confirmation" />
          {queuedDrafts.map((draft) => (
            <View key={draft.id} style={styles.listItem}>
              <View style={styles.rowBetween}>
                <Text style={styles.cardTitle}>{draft.payload.ticker}</Text>
                <Badge tone="warn">queued</Badge>
              </View>
              <Text style={styles.bodyText}>{draft.payload.thesis}</Text>
              <Text style={styles.mutedText}>{draft.reason}</Text>
            </View>
          ))}
        </Card>
      ) : null}

      <Card>
        <SectionTitle eyebrow="Review Archive" title="Active decision packets" />
        {reviews.map((review) => (
          <ReviewRow key={review.id} onPress={() => onSelectReview(review.id)} review={review} />
        ))}
      </Card>
    </View>
  );
}

function ReviewDetailScreen({
  loading,
  onBack,
  onDecision,
  onOutcome,
  summary
}: {
  loading: boolean;
  onBack: () => void;
  onDecision: (reviewId: string, decisionState: DecisionState) => void;
  onOutcome: (reviewId: string) => void;
  summary: MobileReviewSummary;
}) {
  const review = summary.review;
  const riskBlocked = summary.riskGate.status === "blocked";
  return (
    <View style={styles.screen}>
      <Card>
        <SectionTitle
          eyebrow="Review Detail"
          title={review.ticker}
          action={<ActionButton label="Back" onPress={onBack} secondary />}
        />
        <View style={styles.rowBetween}>
          <View style={styles.flex}>
            <Text style={styles.cardTitle}>{review.title}</Text>
            <Text style={styles.bodyText}>{review.thesis}</Text>
          </View>
          <Badge tone={review.decisionState ? "good" : "warn"}>{review.decisionState ?? "pending"}</Badge>
        </View>

        <View style={styles.detailGrid}>
          <Detail label="Confidence" value={`${review.confidence}%`} />
          <Detail label="Status" value={formatLabel(String(review.status))} />
          <Detail label="Freshness" value={formatLabel(summary.freshness)} />
          <Detail label="Claims" value={String(review.claimCount)} />
          <Detail label="Sources" value={String(review.sourceCount)} />
          <Detail label="Follow-up" value={shortDate(review.followUpDate)} />
          <Detail label="Next" value={formatLabel(summary.nextAction)} />
        </View>

        <TagList emptyLabel="No hard blocks returned by mobile summary." items={summary.hardBlocks} tone="danger" />

        <View style={styles.buttonRow}>
          {summary.availableDecisionStates.map((decision) => (
            <ActionButton
              disabled={loading || (decision === "pursue" && !summary.canPursue)}
              key={decision}
              label={formatLabel(decision)}
              onPress={() => onDecision(review.id, decision)}
              secondary={decision !== "pursue"}
            />
          ))}
        </View>
        <View style={styles.buttonRow}>
          <ActionButton
            disabled={loading || review.decisionState === null}
            label="Record Outcome"
            onPress={() => onOutcome(review.id)}
            secondary
          />
        </View>
      </Card>

      <Card>
        <SectionTitle eyebrow="Runbook" title="Mobile workbench checkpoints" />
        {summary.runbook.map((step) => (
          <View key={step.id} style={styles.timelineItem}>
            <View style={styles.rowBetween}>
              <Text style={styles.cardTitle}>{step.label}</Text>
              <Badge tone={step.status === "complete" ? "good" : step.status === "blocked" ? "danger" : "neutral"}>
                {formatLabel(step.status)}
              </Badge>
            </View>
            <Text style={styles.mutedText}>{step.detail}</Text>
          </View>
        ))}
      </Card>

      <Card>
        <SectionTitle eyebrow="Validation" title={formatLabel(review.validation.status)} />
        <Text style={styles.bodyText}>{review.validation.protocol}</Text>
        {review.validation.refusalReason ? <Text style={styles.warningText}>{review.validation.refusalReason}</Text> : null}
        <TagList items={review.validation.dataRequirements} tone="info" />
      </Card>

      <Card>
        <SectionTitle eyebrow="Adversarial View" title="Critique and falsification" />
        <Text style={styles.bodyText}>{review.strongestCritique}</Text>
        <Text style={styles.mutedBlock}>{review.disconfirmingTest}</Text>
      </Card>

      <Card>
        <SectionTitle eyebrow="Risk Gate" title={riskBlocked ? "Blocked before pursue" : "Controls require review"} />
        <View style={styles.detailGrid}>
          <Detail label="Status" value={formatLabel(summary.riskGate.status)} />
          <Detail label="Hard Blocks" value={String(summary.riskGate.hardBlockCount)} />
          <Detail label="High Severity" value={String(summary.riskGate.highSeverityCount)} />
          <Detail label="Authority" value={formatLabel(summary.riskGate.executionAuthority)} />
        </View>
        {summary.riskGate.tradeabilityQuestions.map((item) => (
          <View key={`${item.topic}-${item.question}`} style={styles.listItem}>
            <View style={styles.rowBetween}>
              <Text style={styles.cardTitle}>{item.topic}</Text>
              <Badge tone={item.severity === "high" ? "danger" : item.severity === "medium" ? "warn" : "neutral"}>
                {item.severity}
              </Badge>
            </View>
            <Text style={styles.bodyText}>{item.question}</Text>
          </View>
        ))}
      </Card>

      <Card>
        <SectionTitle eyebrow="Historical Analogue" title={summary.historicalAnalogue.title} />
        <Text style={styles.bodyText}>{summary.historicalAnalogue.similarity}</Text>
        <Text style={styles.mutedBlock}>{summary.historicalAnalogue.differences}</Text>
        <Text style={styles.bodyText}>{summary.historicalAnalogue.resolution}</Text>
      </Card>

      <Card>
        <SectionTitle eyebrow="Evidence" title="Claims" />
        {summary.claims.map((claim) => (
          <View key={claim.id} style={styles.listItem}>
            <Text style={styles.cardTitle}>{formatLabel(claim.kind)}</Text>
            <Text style={styles.bodyText}>{claim.text}</Text>
            {claim.evidence ? <Text style={styles.mutedText}>Evidence: {claim.evidence}</Text> : null}
            <Text style={styles.mutedText}>Confidence: {claim.confidence}%</Text>
          </View>
        ))}
      </Card>

      <Card>
        <SectionTitle eyebrow="Sources" title="Source map" />
        {summary.sources.length > 0 ? (
          summary.sources.map((source) => (
            <View key={source.id} style={styles.listItem}>
              <Text style={styles.cardTitle}>{source.title}</Text>
              <View style={styles.detailGrid}>
                <Detail label="Type" value={formatLabel(source.sourceType)} />
                <Detail label="Permission" value={formatLabel(source.permission)} />
                <Detail label="Relevance" value={`${Math.round(source.relevance * 100)}%`} />
                <Detail label="Timestamp" value={shortDate(source.timestamp)} />
              </View>
            </View>
          ))
        ) : (
          <Text style={styles.bodyText}>No sources returned by the canonical review artifact.</Text>
        )}
      </Card>

      <Card>
        <SectionTitle eyebrow="Signal Writeback" title={formatLabel(summary.signalWriteback.status)} />
        <View style={styles.detailGrid}>
          <Detail label="Decision" value={summary.signalWriteback.decisionState ?? "not recorded"} />
          <Detail label="Suggested" value={formatLabel(summary.signalWriteback.suggestedAction)} />
          <Detail label="Readiness" value={formatLabel(summary.signalWriteback.executionReadiness)} />
          <Detail label="Can Write" value={summary.signalWriteback.canWriteDecision ? "yes" : "no"} />
        </View>
        <Text style={styles.bodyText}>
          Signal memory writeback remains a server-confirmed action and does not execute a trade.
        </Text>
      </Card>

      <Card>
        <SectionTitle eyebrow="Provenance" title={summary.providerProvenance.provider} />
        <View style={styles.detailGrid}>
          <Detail label="Mode" value={formatLabel(summary.providerProvenance.mode)} />
          <Detail label="Fallback" value={summary.providerProvenance.fallbackUsed ? "yes" : "no"} />
          <Detail label="Sources" value={String(summary.providerProvenance.sourceCount)} />
          <Detail label="Audit" value={String(summary.providerProvenance.auditCount)} />
          <Detail label="Report" value={formatLabel(summary.reportStatus.status)} />
        </View>
        {summary.providerProvenance.lastAuditEvent ? (
          <Text style={styles.mutedBlock}>{summary.providerProvenance.lastAuditEvent.detail}</Text>
        ) : null}
      </Card>

      <Card>
        <SectionTitle eyebrow="Audit" title="Review timeline" />
        {summary.audit.map((event) => (
          <View key={event.id} style={styles.timelineItem}>
            <Text style={styles.cardTitle}>{formatLabel(event.eventType)}</Text>
            <Text style={styles.bodyText}>{event.detail}</Text>
            <Text style={styles.mutedText}>{event.timestamp}</Text>
          </View>
        ))}
      </Card>
    </View>
  );
}

function ScannerScreen({
  candidates,
  loading,
  onCreateReview,
  onPromoteCandidate
}: {
  candidates: ScannerCandidate[];
  loading: boolean;
  onCreateReview: (candidate: ScannerCandidate) => void;
  onPromoteCandidate: (candidate: ScannerCandidate) => void;
}) {
  return (
    <View style={styles.screen}>
      <Card>
        <SectionTitle eyebrow="Market Scanner" title="Candidate thesis formation" />
        <Text style={styles.bodyText}>
          Scanner candidates keep the web workflow: inspect signal, create alpha hypothesis, or route into review before
          action.
        </Text>
      </Card>
      {candidates.map((candidate) => (
        <Card key={`${candidate.ticker}-${candidate.signal}-${candidate.scannedAt}`}>
          <View style={styles.rowBetween}>
            <View style={styles.flex}>
              <Text style={styles.cardTitle}>{candidate.ticker}</Text>
              <Text style={styles.mutedText}>{formatLabel(candidate.signal)}</Text>
            </View>
            <Badge tone={candidate.dataMode === "live" ? "good" : "warn"}>{candidate.dataMode}</Badge>
          </View>
          <Text style={styles.bodyText}>{candidate.thesisSuggestion}</Text>
          <View style={styles.detailGrid}>
            <Detail label="Score" value={`${Math.round(candidate.score * 100)}%`} />
            <Detail label="Trend" value={candidate.trend} />
            <Detail label="RSI" value={candidate.rsi === null ? "n/a" : String(Math.round(candidate.rsi))} />
          </View>
          <View style={styles.buttonRow}>
            <ActionButton label="Route to Review" onPress={() => onCreateReview(candidate)} secondary />
            <ActionButton
              disabled={loading}
              label="Create Alpha Hypothesis"
              onPress={() => onPromoteCandidate(candidate)}
            />
          </View>
        </Card>
      ))}
    </View>
  );
}

function SignalsScreen({
  detailLoading,
  onBack,
  onSignalAction,
  onSelectSignal,
  selectedReadiness,
  signals
}: {
  detailLoading: boolean;
  onBack: () => void;
  onSignalAction: (signalId: string, action: SignalLifecycleAction) => void;
  onSelectSignal: (signalId: string) => void;
  selectedReadiness: MobileSignalDecisionReadiness | null;
  signals: SignalRecord[];
}) {
  if (selectedReadiness) {
    return (
      <SignalDetailScreen
        loading={detailLoading}
        onBack={onBack}
        onSignalAction={onSignalAction}
        readiness={selectedReadiness}
      />
    );
  }

  return (
    <View style={styles.screen}>
      <Card>
        <SectionTitle eyebrow="Signals" title="Signal decision cockpit" />
        <Text style={styles.bodyText}>
          Signals expose formula, universe, cost model, validation state, linked reviews, decision action, execution
          readiness, and outcome memory.
        </Text>
      </Card>
      {signals.map((signal) => (
        <Pressable
          key={signalKey(signal)}
          onPress={() => onSelectSignal(signalKey(signal))}
          style={({ pressed }) => [styles.interactiveCard, pressed ? styles.pressedRow : null]}
        >
          <View style={styles.rowBetween}>
            <Text style={styles.cardTitle}>{signal.name}</Text>
            <Badge tone={signal.status === "retired" ? "neutral" : "info"}>{signal.status}</Badge>
          </View>
          <Text style={styles.bodyText}>{signal.formula ?? "Formula not yet published"}</Text>
          <View style={styles.detailGrid}>
            <Detail label="Benchmark" value={signal.benchmark ?? "n/a"} />
            <Detail label="Horizon" value={signal.horizon ?? "n/a"} />
            <Detail label="Decision" value={signal.latestDecisionAction ?? signal.latestDecisionState ?? "unset"} />
            <Detail label="Readiness" value={signal.executionReadiness ?? "not assessed"} />
          </View>
        </Pressable>
      ))}
    </View>
  );
}

function SignalDetailScreen({
  loading,
  onBack,
  onSignalAction,
  readiness
}: {
  loading: boolean;
  onBack: () => void;
  onSignalAction: (signalId: string, action: SignalLifecycleAction) => void;
  readiness: MobileSignalDecisionReadiness;
}) {
  const signal = readiness.signal;
  const signalId = signalKey(signal);
  const outcomeCount = readNumber(readiness.outcomeRollup.outcomeCount);
  const decayDetected = readBoolean(readiness.alphaDecay.decayDetected);

  return (
    <View style={styles.screen}>
      <Card>
        <SectionTitle
          eyebrow="Signal Detail"
          title={signal.name}
          action={<ActionButton label="Back" onPress={onBack} secondary />}
        />
        <View style={styles.rowBetween}>
          <View style={styles.flex}>
            <Text style={styles.cardTitle}>{readiness.decisionReadiness}</Text>
            <Text style={styles.bodyText}>{signal.formula ?? "Formula not yet published"}</Text>
          </View>
          <Badge tone={readiness.hardBlocks.length > 0 ? "danger" : "good"}>
            {readiness.hardBlocks.length > 0 ? "blocked" : "ready"}
          </Badge>
        </View>
        <View style={styles.detailGrid}>
          <Detail label="Next" value={formatLabel(readiness.nextAction)} />
          <Detail label="Validation" value={String(readiness.validationRuns.length)} />
          <Detail label="Policy" value={String(readiness.policyEvents.length)} />
          <Detail label="Decisions" value={String(readiness.decisionLinks.length)} />
          <Detail label="Outcomes" value={String(outcomeCount)} />
          <Detail label="Decay" value={decayDetected ? "detected" : "not detected"} />
        </View>
        <TagList emptyLabel="No hard blocks returned by readiness endpoint." items={readiness.hardBlocks} tone="danger" />
        <View style={styles.buttonRow}>
          <ActionButton
            disabled={loading}
            label="Validate"
            onPress={() => onSignalAction(signalId, "validate")}
          />
          <ActionButton
            disabled={loading || readiness.validationRuns.length === 0}
            label="Promote"
            onPress={() => onSignalAction(signalId, "promote")}
            secondary
          />
          <ActionButton
            disabled={loading}
            label="Constrain"
            onPress={() => onSignalAction(signalId, "constrain")}
            secondary
          />
          <ActionButton
            disabled={loading}
            label="Retire"
            onPress={() => onSignalAction(signalId, "retire")}
            secondary
          />
        </View>
        {loading ? <Text style={styles.mutedText}>Loading readiness...</Text> : null}
      </Card>

      <Card>
        <SectionTitle eyebrow="Execution Boundary" title="Human authority preserved" />
        <View style={styles.detailGrid}>
          <Detail label="Human Decision" value={readiness.humanDecisionAuthority ? "required" : "unknown"} />
          <Detail label="LLM Order Loop" value={readiness.llmInLiveOrderLoop ? "enabled" : "disabled"} />
          <Detail label="Updated" value={shortDate(readiness.updatedAt)} />
        </View>
      </Card>
    </View>
  );
}

function AlphaScreen({ dataset }: { dataset: MobileDataset }) {
  return (
    <View style={styles.screen}>
      <Card>
        <SectionTitle eyebrow="Alpha Lab" title="Hypotheses and signal memory" />
        <Text style={styles.bodyText}>
          Alpha objects are hypotheses first. They should become validated signals only after evidence, costs, risk, and
          outcomes support the claim.
        </Text>
      </Card>
      {dataset.alphaHypotheses.map((alpha) => (
        <Card key={alphaKey(alpha)}>
          <View style={styles.rowBetween}>
            <Text style={styles.cardTitle}>{alpha.title}</Text>
            <Badge tone="info">{alpha.status ?? "hypothesis"}</Badge>
          </View>
          <Text style={styles.bodyText}>{alpha.thesis ?? "No thesis text returned by API."}</Text>
          <View style={styles.detailGrid}>
            <Detail label="Family" value={alpha.signalFamily ?? "n/a"} />
            <Detail label="Horizon" value={alpha.horizon ?? "n/a"} />
            <Detail label="Universe" value={(alpha.universe ?? []).join(", ") || "n/a"} />
          </View>
        </Card>
      ))}
    </View>
  );
}

function HistoryScreen({
  reviews,
  onOpenReview
}: {
  reviews: TradeReview[];
  onOpenReview: (reviewId: string) => void;
}) {
  return (
    <View style={styles.screen}>
      <Card>
        <SectionTitle eyebrow="Decision History" title="Review and outcome memory" />
        {reviews.map((review) => (
          <Pressable
            key={review.id}
            onPress={() => onOpenReview(review.id)}
            style={({ pressed }) => [styles.timelineItem, pressed ? styles.pressedRow : null]}
          >
            <Badge tone={review.decisionState ? "good" : "warn"}>{review.decisionState ?? "pending"}</Badge>
            <Text style={styles.cardTitle}>{review.ticker}</Text>
            <Text style={styles.bodyText}>{review.title}</Text>
            <Text style={styles.mutedText}>Follow-up: {shortDate(review.followUpDate)}</Text>
          </Pressable>
        ))}
      </Card>
    </View>
  );
}

function EnterpriseScreen({
  dataset,
  onRequestNotifications
}: {
  dataset: MobileDataset;
  onRequestNotifications: () => void;
}) {
  const persistence = dataset.health.persistence;
  const enterprise = dataset.enterpriseStatus;
  const governance = readRecord(enterprise?.governance);
  const toolBoundaries = Array.isArray(enterprise?.toolBoundaries) ? enterprise.toolBoundaries.length : 0;

  return (
    <View style={styles.screen}>
      <Card>
        <SectionTitle eyebrow="Enterprise" title="Governed operating surface" />
        <Text style={styles.bodyText}>
          Mobile preserves Ambrosia's boundaries: human authority, visible data freshness, backend system of record, and
          no live order execution inside the LLM decision surface.
        </Text>
        <View style={styles.detailGrid}>
          <Detail label="API Status" value={dataset.health.status ?? "unknown"} />
          <Detail label="Persistence" value={persistence?.mode ?? "unknown"} />
          <Detail label="Database" value={persistence?.databaseConnected ? "connected" : "not confirmed"} />
          <Detail label="Loaded" value={new Date(dataset.loadedAt).toLocaleTimeString()} />
          <Detail label="Tool Rules" value={String(toolBoundaries)} />
          <Detail
            label="Human Authority"
            value={readBoolean(governance.humanDecisionAuthority) ? "required" : "unknown"}
          />
        </View>
      </Card>

      <Card>
        <SectionTitle eyebrow="Deployment" title="iOS and Android readiness" />
        <Text style={styles.bodyText}>
          Expo powers local development, iOS simulator/device runs, Android emulator/device runs, and EAS production
          builds. Configure `EXPO_PUBLIC_API_URL` to target local, staging, or production Ambrosia APIs.
        </Text>
      </Card>

      <Card>
        <SectionTitle
          eyebrow="Alerts"
          title="Review and signal notifications"
          action={<ActionButton label="Enable Alerts" onPress={onRequestNotifications} secondary />}
        />
        <Text style={styles.bodyText}>
          Notification permission is requested only when enabled here. Denying alerts does not block review, signal, or
          scanner workflows.
        </Text>
      </Card>
    </View>
  );
}

function PriorityRow({ item, onPress }: { item: PriorityItem; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.priorityRow, pressed ? styles.pressedRow : null]}>
      <View style={styles.flex}>
        <Text style={styles.cardTitle}>{item.label}</Text>
        <Text style={styles.mutedText}>{formatLabel(item.nextAction)}</Text>
      </View>
      <Badge tone={priorityTone(item.severity)}>{formatLabel(item.severity)}</Badge>
    </Pressable>
  );
}

function ReviewRow({
  review,
  compact = false,
  onPress
}: {
  review: TradeReview;
  compact?: boolean;
  onPress?: () => void;
}) {
  const content = (
    <>
      <View style={styles.rowBetween}>
        <View style={styles.flex}>
          <Text style={styles.cardTitle}>{review.ticker}</Text>
          <Text style={styles.mutedText}>{review.title}</Text>
        </View>
        <Badge tone={review.decisionState ? "good" : "warn"}>{review.decisionState ?? "pending"}</Badge>
      </View>
      {!compact ? <Text style={styles.bodyText}>{review.strongestCritique}</Text> : null}
      <View style={styles.detailGrid}>
        <Detail label="Confidence" value={`${review.confidence}%`} />
        <Detail label="Status" value={formatLabel(review.status)} />
        <Detail label="Follow-up" value={shortDate(review.followUpDate)} />
      </View>
    </>
  );

  if (onPress) {
    return (
      <Pressable onPress={onPress} style={({ pressed }) => [styles.reviewRow, pressed ? styles.pressedRow : null]}>
        {content}
      </Pressable>
    );
  }

  return <View style={styles.reviewRow}>{content}</View>;
}

function Field({
  label,
  value,
  onChangeText,
  multiline = false
}: {
  label: string;
  value: string;
  onChangeText: (value: string) => void;
  multiline?: boolean;
}) {
  return (
    <View style={styles.field}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <TextInput
        multiline={multiline}
        onChangeText={onChangeText}
        placeholderTextColor={colors.muted}
        style={[styles.input, multiline ? styles.multilineInput : null]}
        value={value}
      />
    </View>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.detail}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text style={styles.detailValue} numberOfLines={2}>
        {value}
      </Text>
    </View>
  );
}

function TagList({
  emptyLabel,
  items,
  tone = "neutral"
}: {
  emptyLabel?: string;
  items: string[];
  tone?: "neutral" | "good" | "warn" | "danger" | "info";
}) {
  if (items.length === 0 && emptyLabel) {
    return <Text style={styles.mutedText}>{emptyLabel}</Text>;
  }
  return (
    <View style={styles.tagRow}>
      {items.map((item) => (
        <Badge key={item} tone={tone}>
          {formatLabel(item)}
        </Badge>
      ))}
    </View>
  );
}

function withUpdatedReview(dataset: MobileDataset, review: TradeReview, source: MobileDataset["source"]): MobileDataset {
  const reviews = [review, ...dataset.reviews.filter((item) => item.id !== review.id)];
  const pending = reviews.filter((item) => item.decisionState === null).length;
  return {
    ...dataset,
    source,
    reviews,
    summary: {
      ...dataset.summary,
      pendingReviews: pending,
      decidedReviews: reviews.length - pending
    },
    loadedAt: new Date().toISOString()
  };
}

function withPromotion(
  dataset: MobileDataset,
  promotion: { hypothesis?: MobileDataset["alphaHypotheses"][number]; signal?: SignalRecord }
): MobileDataset {
  const signals = promotion.signal
    ? [promotion.signal, ...dataset.signals.filter((signal) => signalKey(signal) !== signalKey(promotion.signal as SignalRecord))]
    : dataset.signals;
  const alphaHypotheses = promotion.hypothesis
    ? [
        promotion.hypothesis,
        ...dataset.alphaHypotheses.filter((alpha) => alphaKey(alpha) !== alphaKey(promotion.hypothesis as MobileDataset["alphaHypotheses"][number]))
      ]
    : dataset.alphaHypotheses;

  return {
    ...dataset,
    source: "api",
    signals,
    alphaHypotheses,
    summary: {
      ...dataset.summary,
      activeSignals: signals.filter((signal) => !["retired", "blocked"].includes(signal.status)).length,
      alphaHypotheses: alphaHypotheses.length
    },
    loadedAt: new Date().toISOString()
  };
}

function withUpdatedSignal(dataset: MobileDataset, signal: SignalRecord): MobileDataset {
  const signals = [signal, ...dataset.signals.filter((item) => signalKey(item) !== signalKey(signal))];
  return {
    ...dataset,
    source: "api",
    signals,
    summary: {
      ...dataset.summary,
      activeSignals: signals.filter((item) => !["retired", "blocked"].includes(item.status)).length
    },
    loadedAt: new Date().toISOString()
  };
}

function buildLocalReviewSummary(review: TradeReview): MobileReviewSummary {
  const hardBlocks = [
    review.validation.status === "refused" ? "validation_refused" : null,
    review.confidence < 50 ? "low_confidence" : null
  ].filter(Boolean) as string[];

  return {
    schemaVersion: "mobile-review-summary.v1",
    review: {
      id: review.id,
      schemaVersion: review.schemaVersion,
      workflowVersion: review.workflowVersion,
      title: review.title,
      thesis: review.thesis,
      ticker: review.ticker,
      assetClass: review.assetClass,
      timeHorizon: review.timeHorizon,
      intendedExpression: review.intendedExpression,
      status: review.status,
      decisionState: review.decisionState,
      confidence: review.confidence,
      followUpDate: review.followUpDate,
      createdAt: review.createdAt,
      strongestCritique: review.strongestCritique,
      disconfirmingTest: review.disconfirmingTest,
      validation: review.validation,
      tradeability: review.tradeability,
      claimCount: review.claims.length,
      sourceCount: review.sources?.length ?? 0,
      auditCount: review.audit.length
    },
    historicalAnalogue: review.historicalAnalogue,
    claims: review.claims,
    sources: review.sources ?? [],
    audit: review.audit,
    runbook: [
      { id: "intake", label: "Intake", status: "complete", detail: "Local review snapshot loaded." },
      { id: "evidence", label: "Evidence", status: "complete", detail: "Claims and source map available locally." },
      { id: "adversarial", label: "Adversarial", status: "complete", detail: "Critique and falsification are present." },
      {
        id: "validation",
        label: "Validation",
        status: hardBlocks.length > 0 ? "blocked" : "complete",
        detail: "Validation and tradeability gates determine pursue availability."
      },
      {
        id: "outcome",
        label: "Outcome",
        status: review.decisionState ? "pending" : "pending",
        detail: "Outcome recording requires API confirmation."
      }
    ],
    providerProvenance: {
      mode: "local_snapshot",
      fallbackUsed: true,
      sourceCount: review.sources?.length ?? 0,
      auditCount: review.audit.length,
      provider: "mobile-fallback",
      lastAuditEvent: review.audit.length > 0 ? review.audit[review.audit.length - 1] : null
    },
    riskGate: {
      status: review.tradeability.some((item) => item.severity === "high") ? "blocked" : "review_required",
      hardBlockCount: hardBlocks.length,
      highSeverityCount: review.tradeability.filter((item) => item.severity === "high").length,
      tradeabilityQuestions: review.tradeability,
      requiresServerConfirmation: true,
      executionAuthority: "human_review_only"
    },
    signalWriteback: {
      status: review.decisionState ? "ready_to_link" : "review_or_evidence_required",
      requiresLinkedSignal: true,
      canWriteDecision: Boolean(review.decisionState && hardBlocks.length === 0),
      suggestedAction: review.decisionState ? "link_signal_and_write_decision" : "capture_human_decision",
      decisionState: review.decisionState,
      executionReadiness: review.decisionState === "pursue" ? "paper_trade_ready" : "not_executable"
    },
    reportStatus: {
      status: "not_generated",
      latestEvent: null,
      exportAvailable: false,
      desktopRoute: `/reports/export?id=${review.id}`
    },
    hardBlocks,
    softAdvisories: review.tradeability.filter((item) => item.severity !== "high").map((item) => item.topic),
    canPursue: hardBlocks.length === 0,
    availableDecisionStates: ["pursue", "watch", "reject", "needs_more_data"],
    nextAction: hardBlocks.length > 0 ? "resolve_hard_blocks_before_pursue" : "capture_human_decision",
    freshness: "local",
    updatedAt: new Date().toISOString()
  };
}

function buildLocalSignalReadiness(signal: SignalRecord): MobileSignalDecisionReadiness {
  return {
    schemaVersion: "mobile-signal-decision-readiness.v1",
    signal,
    decisionReadiness: "local_snapshot",
    nextAction: "reload_when_api_available",
    hardBlocks: ["offline_detail_unavailable"],
    validationRuns: [],
    policyEvents: [],
    decisionLinks: [],
    outcomeRollup: { outcomeCount: 0 },
    alphaContext: {},
    alphaDecay: { decayDetected: false },
    humanDecisionAuthority: true,
    llmInLiveOrderLoop: false,
    updatedAt: new Date().toISOString()
  };
}

function formatLabel(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function shortDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}

function priorityTone(severity: string): "neutral" | "good" | "warn" | "danger" | "info" {
  if (severity === "critical") {
    return "danger";
  }
  if (severity === "warning") {
    return "warn";
  }
  if (severity === "info") {
    return "info";
  }
  return "neutral";
}

function readRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function readBoolean(value: unknown): boolean {
  return value === true || value === "true";
}

function readNumber(value: unknown): number {
  return typeof value === "number" ? value : 0;
}

const styles = StyleSheet.create({
  safeArea: {
    backgroundColor: colors.fog,
    flex: 1
  },
  header: {
    backgroundColor: colors.paper,
    borderBottomColor: colors.line,
    borderBottomWidth: 1,
    padding: spacing.lg
  },
  headerTop: {
    alignItems: "flex-start",
    flexDirection: "row",
    gap: spacing.md,
    justifyContent: "space-between"
  },
  headerText: {
    flex: 1
  },
  kicker: {
    color: colors.teal,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0,
    textTransform: "uppercase"
  },
  headline: {
    color: colors.ink,
    fontSize: 22,
    fontWeight: "800",
    lineHeight: 28,
    marginTop: spacing.xs
  },
  apiText: {
    color: colors.muted,
    fontSize: 12,
    marginTop: spacing.md
  },
  moduleTabs: {
    alignItems: "center",
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md
  },
  moduleTabsScroller: {
    backgroundColor: colors.fog,
    flexGrow: 0,
    maxHeight: 76
  },
  moduleTab: {
    alignItems: "center",
    backgroundColor: colors.paper,
    borderColor: colors.line,
    borderRadius: radius.md,
    borderWidth: 1,
    justifyContent: "center",
    minHeight: 44,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm
  },
  moduleTabActive: {
    backgroundColor: colors.teal,
    borderColor: colors.teal
  },
  moduleTabText: {
    color: colors.ink,
    fontSize: 13,
    fontWeight: "700",
    includeFontPadding: true,
    lineHeight: 18
  },
  moduleTabTextActive: {
    color: colors.paper
  },
  content: {
    gap: spacing.md,
    padding: spacing.lg,
    paddingBottom: spacing.xl
  },
  screen: {
    gap: spacing.md
  },
  metricsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.md
  },
  warningCard: {
    backgroundColor: "#fff7e8",
    borderColor: "#f0cf8a"
  },
  warningTitle: {
    color: colors.amber,
    fontSize: 14,
    fontWeight: "800",
    marginBottom: spacing.xs
  },
  warningText: {
    color: colors.red,
    fontSize: 14,
    lineHeight: 21,
    marginTop: spacing.sm
  },
  bodyText: {
    color: colors.ink,
    fontSize: 14,
    lineHeight: 21,
    marginTop: spacing.sm
  },
  mutedText: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 19
  },
  mutedBlock: {
    backgroundColor: colors.fog,
    borderColor: colors.line,
    borderRadius: radius.sm,
    borderWidth: 1,
    color: colors.muted,
    fontSize: 13,
    lineHeight: 19,
    marginTop: spacing.md,
    padding: spacing.md
  },
  cardTitle: {
    color: colors.ink,
    fontSize: 16,
    fontWeight: "800"
  },
  rowBetween: {
    alignItems: "flex-start",
    flexDirection: "row",
    gap: spacing.md,
    justifyContent: "space-between"
  },
  flex: {
    flex: 1
  },
  buttonRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.md
  },
  tagRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.md
  },
  detailGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.md
  },
  detail: {
    backgroundColor: colors.fog,
    borderColor: colors.line,
    borderRadius: radius.sm,
    borderWidth: 1,
    minWidth: 118,
    padding: spacing.sm
  },
  detailLabel: {
    color: colors.muted,
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase"
  },
  detailValue: {
    color: colors.ink,
    fontSize: 13,
    fontWeight: "700",
    marginTop: spacing.xs
  },
  field: {
    marginBottom: spacing.md
  },
  fieldLabel: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "700",
    marginBottom: spacing.xs,
    textTransform: "uppercase"
  },
  input: {
    backgroundColor: colors.fog,
    borderColor: colors.line,
    borderRadius: radius.md,
    borderWidth: 1,
    color: colors.ink,
    fontSize: 15,
    minHeight: 44,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm
  },
  multilineInput: {
    minHeight: 110,
    textAlignVertical: "top"
  },
  priorityRow: {
    alignItems: "flex-start",
    borderBottomColor: colors.line,
    borderBottomWidth: 1,
    flexDirection: "row",
    gap: spacing.md,
    justifyContent: "space-between",
    paddingVertical: spacing.md
  },
  reviewRow: {
    borderBottomColor: colors.line,
    borderBottomWidth: 1,
    gap: spacing.sm,
    paddingVertical: spacing.md
  },
  interactiveCard: {
    backgroundColor: colors.paper,
    borderColor: colors.line,
    borderRadius: radius.md,
    borderWidth: 1,
    padding: spacing.lg
  },
  pressedRow: {
    opacity: 0.72
  },
  listItem: {
    borderBottomColor: colors.line,
    borderBottomWidth: 1,
    paddingVertical: spacing.md
  },
  timelineItem: {
    borderBottomColor: colors.line,
    borderBottomWidth: 1,
    gap: spacing.xs,
    paddingVertical: spacing.md
  }
});
