import Constants from "expo-constants";
import { Platform } from "react-native";
import type { ModuleId } from "./types";

declare const require: (moduleName: string) => typeof import("expo-notifications");

export type NotificationTarget =
  | { module: "reviews"; reviewId: string }
  | { module: "signals"; signalId: string }
  | { module: "scanner" }
  | { module: ModuleId };

type NotificationResponse = import("expo-notifications").NotificationResponse;
type NotificationSubscription = { remove: () => void };

function canUseExpoNotifications(): boolean {
  return !(Platform.OS === "android" && Constants.appOwnership === "expo");
}

function getNotifications(): typeof import("expo-notifications") | null {
  if (!canUseExpoNotifications()) {
    return null;
  }
  return require("expo-notifications");
}

const Notifications = getNotifications();

Notifications?.setNotificationHandler({
  handleNotification: async () => ({
    shouldPlaySound: false,
    shouldSetBadge: true,
    shouldShowBanner: true,
    shouldShowList: true
  })
});

export async function requestNotificationPermissions(): Promise<boolean> {
  if (!Notifications) {
    return false;
  }
  const current = await Notifications.getPermissionsAsync();
  if (current.granted) {
    return true;
  }
  const next = await Notifications.requestPermissionsAsync();
  return next.granted;
}

export function targetFromUrl(url: string): NotificationTarget | null {
  const normalized = url.replace("ambrosia://", "");
  const [module, id] = normalized.split("/");
  if (module === "review" && id) {
    return { module: "reviews", reviewId: id };
  }
  if (module === "signal" && id) {
    return { module: "signals", signalId: id };
  }
  if (module === "scanner") {
    return { module: "scanner" };
  }
  if (["today", "reviews", "scanner", "signals", "alpha", "history", "enterprise"].includes(module)) {
    return { module: module as ModuleId };
  }
  return null;
}

export function targetFromNotificationResponse(
  response: NotificationResponse
): NotificationTarget | null {
  const data = response.notification.request.content.data ?? {};
  if (typeof data.url === "string") {
    return targetFromUrl(data.url);
  }
  if (typeof data.reviewId === "string") {
    return { module: "reviews", reviewId: data.reviewId };
  }
  if (typeof data.signalId === "string") {
    return { module: "signals", signalId: data.signalId };
  }
  return null;
}

export function addNotificationResponseListener(
  listener: (response: NotificationResponse) => void
): NotificationSubscription {
  if (!Notifications) {
    return { remove: () => undefined };
  }
  return Notifications.addNotificationResponseReceivedListener(listener);
}

export async function scheduleLocalMobileAlert(
  title: string,
  body: string,
  target: NotificationTarget
): Promise<void> {
  if (!Notifications) {
    return;
  }
  const granted = await requestNotificationPermissions();
  if (!granted) {
    return;
  }
  await Notifications.scheduleNotificationAsync({
    content: {
      title,
      body,
      data: target
    },
    trigger: null
  });
}
