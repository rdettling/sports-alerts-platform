import { describe, expect, it } from "vitest";

import {
  ALERT_RULE_CONFIG,
  buildAlertSettingsPayload,
  getRuleFieldValue,
} from "./alert-rule-config";

describe("alert rule settings", () => {
  it("builds the same full payload for boolean competition and game settings", () => {
    expect(
      buildAlertSettingsPayload(
        {
          alert_type: "game_start",
          is_enabled: true,
          close_game_margin_threshold: null,
          close_game_time_threshold_seconds: null,
          inning_start_threshold: null,
        },
        { is_enabled: false },
      ),
    ).toEqual({
      is_enabled: false,
      close_game_margin_threshold: null,
      close_game_time_threshold_seconds: null,
      inning_start_threshold: null,
    });
  });

  it("preserves concrete thresholds and converts selected minutes to seconds", () => {
    const settings = {
      alert_type: "close_game_late",
      is_enabled: true,
      close_game_margin_threshold: 5,
      close_game_time_threshold_seconds: 300,
      inning_start_threshold: null,
    };
    const minutes = ALERT_RULE_CONFIG.close_game_late.fields[1];

    expect(getRuleFieldValue(settings, minutes)).toBe(5);
    expect(
      buildAlertSettingsPayload(settings, {
        fieldKey: "close_game_time_threshold_seconds",
        fieldValue: 10,
      }),
    ).toEqual({
      is_enabled: true,
      close_game_margin_threshold: 5,
      close_game_time_threshold_seconds: 600,
      inning_start_threshold: null,
    });
  });

  it("updates the concrete inning threshold", () => {
    expect(
      buildAlertSettingsPayload(
        {
          alert_type: "inning_start",
          is_enabled: true,
          close_game_margin_threshold: null,
          close_game_time_threshold_seconds: null,
          inning_start_threshold: 7,
        },
        { fieldKey: "inning_start_threshold", fieldValue: 5 },
      ),
    ).toEqual({
      is_enabled: true,
      close_game_margin_threshold: null,
      close_game_time_threshold_seconds: null,
      inning_start_threshold: 5,
    });
  });
});
