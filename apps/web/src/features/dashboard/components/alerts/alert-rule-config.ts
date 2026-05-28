import type { AlertPreference, GameAlertPreferenceItem } from "../../../../shared/api";

type RuleFieldKey =
  | "close_game_margin_threshold"
  | "close_game_time_threshold_seconds"
  | "inning_start_threshold";

type RuleFieldConfig = {
  key: RuleFieldKey;
  label: string;
  options: number[];
  defaultValue: number;
  unit?: "minutes";
};

type RuleConfig = {
  fields: RuleFieldConfig[];
  requiresEnabled: boolean;
};

export const ALERT_RULE_CONFIG: Record<string, RuleConfig> = {
  close_game_late: {
    requiresEnabled: true,
    fields: [
      { key: "close_game_margin_threshold", label: "Margin", options: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], defaultValue: 5 },
      { key: "close_game_time_threshold_seconds", label: "Minutes", options: [1, 2, 3, 4, 5, 10], defaultValue: 5, unit: "minutes" },
    ],
  },
  inning_start: {
    requiresEnabled: true,
    fields: [{ key: "inning_start_threshold", label: "Inning", options: [1, 2, 3, 4, 5, 6, 7, 8, 9], defaultValue: 7 }],
  },
};

export function ruleFieldsFor(alertType: string, isEnabled: boolean): RuleFieldConfig[] {
  const config = ALERT_RULE_CONFIG[alertType];
  if (!config) return [];
  if (config.requiresEnabled && !isEnabled) return [];
  return config.fields;
}

export function getLeagueFieldValue(preference: AlertPreference, field: RuleFieldConfig): number {
  const value = preference[field.key];
  if (typeof value !== "number") return field.defaultValue;
  if (field.unit === "minutes" && field.key === "close_game_time_threshold_seconds") {
    return Math.max(1, Math.round(value / 60));
  }
  return value;
}

export function getGameFieldValue(item: GameAlertPreferenceItem, field: RuleFieldConfig): number {
  const value = item[field.key];
  if (typeof value !== "number") return field.defaultValue;
  if (field.unit === "minutes" && field.key === "close_game_time_threshold_seconds") {
    return Math.max(1, Math.round(value / 60));
  }
  return value;
}

export function buildLeagueRulePayload(
  preference: AlertPreference,
  change: { is_enabled?: boolean } | { fieldKey: RuleFieldKey; fieldValue: number },
): {
  is_enabled: boolean;
  close_game_margin_threshold?: number;
  close_game_time_threshold_seconds?: number;
  inning_start_threshold?: number;
} {
  const payload: {
    is_enabled: boolean;
    close_game_margin_threshold?: number;
    close_game_time_threshold_seconds?: number;
    inning_start_threshold?: number;
  } = {
    is_enabled: "is_enabled" in change ? change.is_enabled ?? preference.is_enabled : preference.is_enabled,
  };

  for (const field of ALERT_RULE_CONFIG[preference.alert_type]?.fields ?? []) {
    const nextValueRaw = "fieldKey" in change && change.fieldKey === field.key ? change.fieldValue : getLeagueFieldValue(preference, field);
    const nextValue = field.unit === "minutes" && field.key === "close_game_time_threshold_seconds" ? nextValueRaw * 60 : nextValueRaw;
    if (field.key === "close_game_margin_threshold") payload.close_game_margin_threshold = nextValue;
    if (field.key === "close_game_time_threshold_seconds") payload.close_game_time_threshold_seconds = nextValue;
    if (field.key === "inning_start_threshold") payload.inning_start_threshold = nextValue;
  }

  return payload;
}

export function buildGameRuleOverridePayload(
  item: GameAlertPreferenceItem,
  change: { is_enabled_override: boolean } | { fieldKey: RuleFieldKey; fieldValue: number },
): {
  is_enabled_override?: boolean | null;
  close_game_margin_threshold_override?: number | null;
  close_game_time_threshold_seconds_override?: number | null;
  inning_start_threshold_override?: number | null;
} {
  const payload: {
    is_enabled_override?: boolean | null;
    close_game_margin_threshold_override?: number | null;
    close_game_time_threshold_seconds_override?: number | null;
    inning_start_threshold_override?: number | null;
  } = {
    is_enabled_override:
      "is_enabled_override" in change ? change.is_enabled_override : (item.override?.is_enabled_override ?? item.is_enabled),
    close_game_margin_threshold_override: null,
    close_game_time_threshold_seconds_override: null,
    inning_start_threshold_override: null,
  };

  for (const field of ALERT_RULE_CONFIG[item.alert_type]?.fields ?? []) {
    const nextValueRaw = "fieldKey" in change && change.fieldKey === field.key ? change.fieldValue : getGameFieldValue(item, field);
    const nextValue = field.unit === "minutes" && field.key === "close_game_time_threshold_seconds" ? nextValueRaw * 60 : nextValueRaw;
    if (field.key === "close_game_margin_threshold") payload.close_game_margin_threshold_override = nextValue;
    if (field.key === "close_game_time_threshold_seconds") payload.close_game_time_threshold_seconds_override = nextValue;
    if (field.key === "inning_start_threshold") payload.inning_start_threshold_override = nextValue;
  }

  return payload;
}
