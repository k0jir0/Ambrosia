import type { LinkingOptions } from "@react-navigation/native";
import type { ModuleId } from "./types";

export type RootStackParamList = {
  Main: { module?: ModuleId } | undefined;
  ReviewDetail: { reviewId: string };
  ScannerCandidateDetail: { ticker: string; signal: string };
  SignalDetail: { signalId: string };
  AlphaHypothesisDetail: { hypothesisId: string };
  DecisionHistoryDetail: { reviewId: string };
  EnterpriseStatusDetail: undefined;
};

export const moduleRoutes: Record<ModuleId, keyof RootStackParamList> = {
  today: "Main",
  reviews: "ReviewDetail",
  scanner: "ScannerCandidateDetail",
  signals: "SignalDetail",
  alpha: "AlphaHypothesisDetail",
  history: "DecisionHistoryDetail",
  enterprise: "EnterpriseStatusDetail"
};

export const linkingConfig: LinkingOptions<RootStackParamList> = {
  prefixes: ["ambrosia://"],
  config: {
    screens: {
      Main: "",
      ReviewDetail: "review/:reviewId",
      ScannerCandidateDetail: "scanner/:ticker/:signal",
      SignalDetail: "signal/:signalId",
      AlphaHypothesisDetail: "alpha/:hypothesisId",
      DecisionHistoryDetail: "history/:reviewId",
      EnterpriseStatusDetail: "enterprise"
    }
  }
};

export function moduleFromRouteName(routeName: keyof RootStackParamList): ModuleId {
  if (routeName === "ReviewDetail") {
    return "reviews";
  }
  if (routeName === "ScannerCandidateDetail") {
    return "scanner";
  }
  if (routeName === "SignalDetail") {
    return "signals";
  }
  if (routeName === "AlphaHypothesisDetail") {
    return "alpha";
  }
  if (routeName === "DecisionHistoryDetail") {
    return "history";
  }
  if (routeName === "EnterpriseStatusDetail") {
    return "enterprise";
  }
  return "today";
}
