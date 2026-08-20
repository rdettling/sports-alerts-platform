import type { AlertSettings, AlertSettingsUpdate } from "../../../../shared/api";

type RuleFieldKey =
  "close_game_margin_threshold" | "close_game_time_threshold_seconds" | "inning_start_threshold";

type RuleFieldConfig = {
  key: RuleFieldKey;
  label: string;
  options: number[];
  defaultValue: number;
  unit?: "minutes";
};

type RuleConfig = {
  fields: RuleFieldConfig[];
};

export const ALERT_RULE_CONFIG: Record<string, RuleConfig> = {
  close_game_late: {
    fields: [
      {
        key: "close_game_margin_threshold",
        label: "Margin",
        options: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        defaultValue: 5,
      },
      {
        key: "close_game_time_threshold_seconds",
        label: "Minutes",
        options: [1, 2, 3, 4, 5, 10],
        defaultValue: 5,
        unit: "minutes",
      },
    ],
  },
  inning_start: {
    fields: [
      {
        key: "inning_start_threshold",
        label: "Inning",
        options: [1, 2, 3, 4, 5, 6, 7, 8, 9],
        defaultValue: 7,
      },
    ],
  },
};

export function ruleFieldsFor(alertType: string, isEnabled: boolean): RuleFieldConfig[] {
  const config = ALERT_RULE_CONFIG[alertType];
  if (!config || !isEnabled) return [];
  return config.fields;
}

export function getRuleFieldValue(settings: AlertSettings, field: RuleFieldConfig): number {
  const value = settings[field.key];
  if (typeof value !== "number") return field.defaultValue;
  if (field.unit === "minutes" && field.key === "close_game_time_threshold_seconds") {
    return Math.max(1, Math.round(value / 60));
  }
  return value;
}

export function buildAlertSettingsPayload(
  settings: AlertSettings & { alert_type: string },
  change: { is_enabled?: boolean } | { fieldKey: RuleFieldKey; fieldValue: number },
): AlertSettingsUpdate {
  const payload: AlertSettingsUpdate = {
    is_enabled:
      "is_enabled" in change ? (change.is_enabled ?? settings.is_enabled) : settings.is_enabled,
    close_game_margin_threshold: settings.close_game_margin_threshold,
    close_game_time_threshold_seconds: settings.close_game_time_threshold_seconds,
    inning_start_threshold: settings.inning_start_threshold,
  };

  for (const field of ALERT_RULE_CONFIG[settings.alert_type]?.fields ?? []) {
    if (!("fieldKey" in change) || change.fieldKey !== field.key) continue;
    const nextValueRaw = change.fieldValue;
    const nextValue =
      field.unit === "minutes" && field.key === "close_game_time_threshold_seconds"
        ? nextValueRaw * 60
        : nextValueRaw;
    if (field.key === "close_game_margin_threshold")
      payload.close_game_margin_threshold = nextValue;
    if (field.key === "close_game_time_threshold_seconds")
      payload.close_game_time_threshold_seconds = nextValue;
    if (field.key === "inning_start_threshold") payload.inning_start_threshold = nextValue;
  }

  return payload;
}
