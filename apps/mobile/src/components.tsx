import type { ReactNode } from "react";
import { Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";
import { colors, radius, spacing } from "./theme";

export function Card({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function SectionTitle({
  eyebrow,
  title,
  action
}: {
  eyebrow?: string;
  title: string;
  action?: ReactNode;
}) {
  return (
    <View style={styles.sectionTitle}>
      <View style={styles.sectionText}>
        {eyebrow ? <Text style={styles.eyebrow}>{eyebrow}</Text> : null}
        <Text style={styles.title}>{title}</Text>
      </View>
      {action}
    </View>
  );
}

export function Badge({
  children,
  tone = "neutral"
}: {
  children: ReactNode;
  tone?: "neutral" | "good" | "warn" | "danger" | "info";
}) {
  return (
    <View style={[styles.badge, badgeTone[tone]]}>
      <Text style={[styles.badgeText, badgeTextTone[tone]]}>{children}</Text>
    </View>
  );
}

export function Metric({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <Card style={styles.metric}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={styles.metricValue}>{value}</Text>
      {note ? <Text style={styles.metricNote}>{note}</Text> : null}
    </Card>
  );
}

export function ActionButton({
  label,
  onPress,
  disabled = false,
  secondary = false
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  secondary?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        secondary ? styles.secondaryButton : styles.primaryButton,
        disabled ? styles.disabledButton : null,
        pressed && !disabled ? styles.pressed : null
      ]}
    >
      <Text style={[styles.buttonText, secondary ? styles.secondaryButtonText : styles.primaryButtonText]}>
        {label}
      </Text>
    </Pressable>
  );
}

const badgeTone = StyleSheet.create({
  neutral: { backgroundColor: "#edf2ef", borderColor: colors.line },
  good: { backgroundColor: "#e8f7ee", borderColor: "#a7e3bb" },
  warn: { backgroundColor: "#fff7e8", borderColor: "#f0cf8a" },
  danger: { backgroundColor: "#fff0ed", borderColor: "#f4b4ab" },
  info: { backgroundColor: "#edf5ff", borderColor: "#b8d5ff" }
});

const badgeTextTone = StyleSheet.create({
  neutral: { color: colors.muted },
  good: { color: colors.green },
  warn: { color: colors.amber },
  danger: { color: colors.red },
  info: { color: colors.blue }
});

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.paper,
    borderColor: colors.line,
    borderRadius: radius.md,
    borderWidth: 1,
    padding: spacing.lg
  },
  sectionTitle: {
    alignItems: "center",
    flexDirection: "row",
    gap: spacing.md,
    justifyContent: "space-between",
    marginBottom: spacing.md
  },
  sectionText: {
    flex: 1
  },
  eyebrow: {
    color: colors.teal,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0,
    textTransform: "uppercase"
  },
  title: {
    color: colors.ink,
    fontSize: 18,
    fontWeight: "700",
    marginTop: spacing.xs
  },
  badge: {
    alignSelf: "flex-start",
    borderRadius: radius.sm,
    borderWidth: 1,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs
  },
  badgeText: {
    fontSize: 12,
    fontWeight: "700"
  },
  metric: {
    flex: 1,
    minWidth: 148
  },
  metricLabel: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "600"
  },
  metricValue: {
    color: colors.ink,
    fontSize: 26,
    fontWeight: "800",
    marginTop: spacing.xs
  },
  metricNote: {
    color: colors.muted,
    fontSize: 12,
    lineHeight: 17,
    marginTop: spacing.sm
  },
  button: {
    alignItems: "center",
    borderRadius: radius.md,
    borderWidth: 1,
    justifyContent: "center",
    minHeight: 42,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm
  },
  primaryButton: {
    backgroundColor: colors.teal,
    borderColor: colors.teal
  },
  secondaryButton: {
    backgroundColor: colors.paper,
    borderColor: colors.line
  },
  disabledButton: {
    opacity: 0.45
  },
  pressed: {
    opacity: 0.72
  },
  buttonText: {
    fontSize: 14,
    fontWeight: "700"
  },
  primaryButtonText: {
    color: colors.paper
  },
  secondaryButtonText: {
    color: colors.ink
  }
});
