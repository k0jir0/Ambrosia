export type ProductRole = "viewer" | "analyst" | "reviewer" | "owner" | "admin";

export type RouteFeatureId =
  | "market-scanner"
  | "market-intelligence"
  | "operations"
  | "calibration"
  | "review-export"
  | "alpha-lab"
  | "signals-lab"
  | "cli-design"
  | "legacy-labs";

export type DeploymentEnvironment = "development" | "test" | "staging" | "production";
export type RouteDataMode = "live" | "qualified-fixture";
export type RouteReleaseStatus = "implemented" | "qualified" | "internal";

export type RouteAvailability = {
  featureId: RouteFeatureId;
  label: string;
  owningWorkflow: string;
  paths: readonly string[];
  buildSwitch: `NEXT_PUBLIC_${string}`;
  runtimePolicy: string | null;
  dedicatedSwitch: boolean;
  enabled: boolean;
  roles: ReadonlySet<ProductRole>;
  minimumRole: ProductRole;
  authority: "read";
  environments: readonly DeploymentEnvironment[];
  dataModes: readonly RouteDataMode[];
  releaseStatus: RouteReleaseStatus;
  evidenceArtifactId: string;
  unavailableRedirect: string;
};

export const PUBLIC_PATHS = new Set([
  "/",
  "/signup",
  "/login",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
  "/accept-invite",
  "/terms",
  "/privacy",
  "/company-proof",
]);

const developmentDefault = process.env.NODE_ENV !== "production";

const marketScannerEnabled =
  process.env.NEXT_PUBLIC_ENABLE_MARKET_SCANNER === "true" ||
  (process.env.NEXT_PUBLIC_ENABLE_MARKET_SCANNER === undefined && developmentDefault);

const marketIntelligenceEnabled =
  process.env.NEXT_PUBLIC_ENABLE_MARKET_INTELLIGENCE === "true" ||
  (process.env.NEXT_PUBLIC_ENABLE_MARKET_INTELLIGENCE === undefined && developmentDefault);

const operationsEnabled = process.env.NEXT_PUBLIC_ENABLE_OPERATIONS === "true";
const calibrationEnabled = process.env.NEXT_PUBLIC_ENABLE_CALIBRATION === "true";
const reviewExportEnabled = process.env.NEXT_PUBLIC_ENABLE_REVIEW_EXPORT === "true";
const alphaLabEnabled = process.env.NEXT_PUBLIC_ENABLE_ALPHA_LAB === "true";
const signalsLabEnabled = process.env.NEXT_PUBLIC_ENABLE_SIGNALS_LAB === "true";
const cliDesignEnabled = process.env.NEXT_PUBLIC_ENABLE_CLI_DESIGN === "true";

const legacyLabsEnabled =
  developmentDefault && process.env.NEXT_PUBLIC_ENABLE_LABS === "true";

const ALL_ROLES = new Set<ProductRole>(["viewer", "analyst", "reviewer", "owner", "admin"]);
const MARKET_SCANNER_ROLES = new Set<ProductRole>(["analyst", "reviewer", "owner", "admin"]);
const ANALYST_ROLES = new Set<ProductRole>(["analyst", "reviewer", "owner", "admin"]);
const ALL_ENVIRONMENTS = ["development", "test", "staging", "production"] as const;

export const ROUTE_AVAILABILITY: readonly RouteAvailability[] = [
  {
    featureId: "market-scanner",
    label: "Market Scanner",
    owningWorkflow: "market-discovery",
    paths: ["/market-scanner"],
    buildSwitch: "NEXT_PUBLIC_ENABLE_MARKET_SCANNER",
    runtimePolicy: "MARKET_SCANNER_ENABLED",
    dedicatedSwitch: true,
    enabled: marketScannerEnabled,
    roles: MARKET_SCANNER_ROLES,
    minimumRole: "analyst",
    authority: "read",
    environments: ALL_ENVIRONMENTS,
    dataModes: ["live", "qualified-fixture"],
    releaseStatus: "qualified",
    evidenceArtifactId: "market-scanner-readiness",
    unavailableRedirect: "/app",
  },
  {
    featureId: "market-intelligence",
    label: "Market Intelligence",
    owningWorkflow: "market-research",
    paths: ["/markets"],
    buildSwitch: "NEXT_PUBLIC_ENABLE_MARKET_INTELLIGENCE",
    runtimePolicy: "MARKET_INTELLIGENCE_ENABLED",
    dedicatedSwitch: true,
    enabled: marketIntelligenceEnabled,
    roles: MARKET_SCANNER_ROLES,
    minimumRole: "analyst",
    authority: "read",
    environments: ALL_ENVIRONMENTS,
    dataModes: ["live", "qualified-fixture"],
    releaseStatus: "implemented",
    evidenceArtifactId: "market-intelligence-readiness",
    unavailableRedirect: "/app",
  },
  {
    featureId: "operations",
    label: "Operations",
    owningWorkflow: "operations-control-plane",
    paths: ["/operations"],
    buildSwitch: "NEXT_PUBLIC_ENABLE_OPERATIONS",
    runtimePolicy: "OPERATIONS_ENABLED",
    dedicatedSwitch: true,
    enabled: operationsEnabled,
    roles: new Set<ProductRole>(["owner", "admin"]),
    minimumRole: "owner",
    authority: "read",
    environments: ALL_ENVIRONMENTS,
    dataModes: ["live"],
    releaseStatus: "implemented",
    evidenceArtifactId: "operations-readiness",
    unavailableRedirect: "/app",
  },
  {
    featureId: "calibration",
    label: "Calibration",
    owningWorkflow: "outcomes-and-memory",
    paths: ["/calibration"],
    buildSwitch: "NEXT_PUBLIC_ENABLE_CALIBRATION",
    runtimePolicy: "CALIBRATION_ENABLED",
    dedicatedSwitch: true,
    enabled: calibrationEnabled,
    roles: ALL_ROLES,
    minimumRole: "viewer",
    authority: "read",
    environments: ALL_ENVIRONMENTS,
    dataModes: ["live"],
    releaseStatus: "implemented",
    evidenceArtifactId: "calibration-readiness",
    unavailableRedirect: "/history",
  },
  {
    featureId: "review-export",
    label: "Review Export",
    owningWorkflow: "review",
    paths: ["/reports"],
    buildSwitch: "NEXT_PUBLIC_ENABLE_REVIEW_EXPORT",
    runtimePolicy: "REPORT_EXPORT_ENABLED",
    dedicatedSwitch: true,
    enabled: reviewExportEnabled,
    roles: ALL_ROLES,
    minimumRole: "viewer",
    authority: "read",
    environments: ALL_ENVIRONMENTS,
    dataModes: ["live"],
    releaseStatus: "implemented",
    evidenceArtifactId: "review-export-readiness",
    unavailableRedirect: "/review",
  },
  {
    featureId: "alpha-lab",
    label: "Alpha Lab",
    owningWorkflow: "research-lifecycle",
    paths: ["/alpha"],
    buildSwitch: "NEXT_PUBLIC_ENABLE_ALPHA_LAB",
    runtimePolicy: "ALPHA_LIFECYCLE_WRITES_ENABLED",
    dedicatedSwitch: true,
    enabled: alphaLabEnabled,
    roles: ANALYST_ROLES,
    minimumRole: "analyst",
    authority: "read",
    environments: ALL_ENVIRONMENTS,
    dataModes: ["live", "qualified-fixture"],
    releaseStatus: "implemented",
    evidenceArtifactId: "alpha-decay-alerts",
    unavailableRedirect: "/app",
  },
  {
    featureId: "signals-lab",
    label: "Signals Lab",
    owningWorkflow: "research-lifecycle",
    paths: ["/signals"],
    buildSwitch: "NEXT_PUBLIC_ENABLE_SIGNALS_LAB",
    runtimePolicy: "SIGNAL_LIFECYCLE_WRITES_ENABLED",
    dedicatedSwitch: true,
    enabled: signalsLabEnabled,
    roles: ANALYST_ROLES,
    minimumRole: "analyst",
    authority: "read",
    environments: ALL_ENVIRONMENTS,
    dataModes: ["live", "qualified-fixture"],
    releaseStatus: "implemented",
    evidenceArtifactId: "signal-validation-readiness",
    unavailableRedirect: "/app",
  },
  {
    featureId: "cli-design",
    label: "CLI Guide",
    owningWorkflow: "cli-sdk-contracts",
    paths: ["/cli-design"],
    buildSwitch: "NEXT_PUBLIC_ENABLE_CLI_DESIGN",
    runtimePolicy: null,
    dedicatedSwitch: true,
    enabled: cliDesignEnabled,
    roles: ANALYST_ROLES,
    minimumRole: "analyst",
    authority: "read",
    environments: ALL_ENVIRONMENTS,
    dataModes: ["live"],
    releaseStatus: "implemented",
    evidenceArtifactId: "cli-contract-readiness",
    unavailableRedirect: "/app",
  },
  {
    featureId: "legacy-labs",
    label: "Internal Labs",
    owningWorkflow: "internal-evidence",
    paths: [
      "/advanced",
      "/execution-intelligence",
      "/relay-benchmarks",
    ],
    buildSwitch: "NEXT_PUBLIC_ENABLE_LABS",
    runtimePolicy: null,
    dedicatedSwitch: false,
    enabled: legacyLabsEnabled,
    roles: ALL_ROLES,
    minimumRole: "viewer",
    authority: "read",
    environments: ["development", "test"],
    dataModes: ["qualified-fixture"],
    releaseStatus: "internal",
    evidenceArtifactId: "legacy-labs-internal-only",
    unavailableRedirect: "/app",
  },
] as const;

export function validateRouteManifest(
  manifest: readonly RouteAvailability[] = ROUTE_AVAILABILITY,
  environment: { NODE_ENV?: string; NEXT_PUBLIC_ENABLE_LABS?: string } = process.env,
): string[] {
  const errors: string[] = [];
  const prefixes = new Set<string>();

  for (const entry of manifest) {
    for (const prefix of entry.paths) {
      if (prefixes.has(prefix)) errors.push(`Duplicate route prefix: ${prefix}`);
      prefixes.add(prefix);
    }
    if (entry.roles.size === 0 || !entry.roles.has(entry.minimumRole)) {
      errors.push(`${entry.featureId} has an invalid role declaration`);
    }
    if (entry.releaseStatus !== "internal" && !entry.dedicatedSwitch) {
      errors.push(`${entry.featureId} must use a dedicated exposure switch`);
    }
  }

  if (environment.NODE_ENV === "production" && environment.NEXT_PUBLIC_ENABLE_LABS === "true") {
    errors.push("NEXT_PUBLIC_ENABLE_LABS=true is forbidden in production");
  }
  return errors;
}

function matchesPath(pathname: string, prefix: string): boolean {
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

export function getRouteAvailability(pathname: string): RouteAvailability | null {
  return ROUTE_AVAILABILITY.find((entry) => entry.paths.some((prefix) => matchesPath(pathname, prefix))) ?? null;
}

export function isRouteAvailable(pathname: string, role: string): boolean {
  const availability = getRouteAvailability(pathname);
  if (!availability) return true;
  return availability.enabled && availability.roles.has(role as ProductRole);
}

export function isFeatureEnabled(featureId: RouteFeatureId): boolean {
  return ROUTE_AVAILABILITY.find((entry) => entry.featureId === featureId)?.enabled ?? false;
}