import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { GameAlertSettingsModal } from "./GameAlertSettingsModal";

describe("GameAlertSettingsModal", () => {
  it("labels the dialog and closes on Escape", () => {
    const onClose = vi.fn();
    render(
      <GameAlertSettingsModal
        isOpen
        matchupLabel="NY at LV"
        alertsBusy
        gameAlertState={null}
        onClose={onClose}
        onUpdateGameAlertSettings={vi.fn(async () => undefined)}
        onResetGameAlertSettings={vi.fn(async () => undefined)}
      />,
    );

    expect(
      screen.getByRole("dialog", { name: "Game Alert Settings", description: "NY at LV" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Loading alert settings");

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("keeps shared rule rows interactive and accessibly labeled", () => {
    const onUpdateGameAlertSettings = vi.fn(async () => undefined);
    const onResetGameAlertSettings = vi.fn(async () => undefined);
    render(
      <GameAlertSettingsModal
        isOpen
        matchupLabel="NY at LV"
        alertsBusy={false}
        gameAlertState={{
          game_id: 12,
          competition: "WNBA",
          sport: "basketball",
          items: [
            {
              sport: "basketball",
              alert_type: "game_start",
              uses_sport_defaults: false,
              is_enabled: true,
              close_game_margin_threshold: null,
              close_game_time_threshold_seconds: null,
              inning_start_threshold: null,
            },
          ],
        }}
        onClose={vi.fn()}
        onUpdateGameAlertSettings={onUpdateGameAlertSettings}
        onResetGameAlertSettings={onResetGameAlertSettings}
      />,
    );

    const toggle = screen.getByRole("switch", { name: "Game start alerts for this game" });
    expect(screen.getByRole("listitem")).toHaveClass("alert-rule-row", "game-alert-row");
    expect(toggle).toHaveAttribute("aria-checked", "true");
    expect(toggle).toHaveTextContent("On");

    fireEvent.click(toggle);
    expect(onUpdateGameAlertSettings).toHaveBeenCalledWith(12, "game_start", {
      is_enabled: false,
      close_game_margin_threshold: null,
      close_game_time_threshold_seconds: null,
      inning_start_threshold: null,
    });

    fireEvent.click(screen.getByRole("button", { name: "Use sport settings" }));
    expect(onResetGameAlertSettings).toHaveBeenCalledWith(12, "game_start");
  });

  it("hides reset for game alerts already using sport settings", () => {
    render(
      <GameAlertSettingsModal
        isOpen
        matchupLabel="NY at LV"
        alertsBusy={false}
        gameAlertState={{
          game_id: 12,
          competition: "WNBA",
          sport: "basketball",
          items: [
            {
              sport: "basketball",
              alert_type: "game_start",
              uses_sport_defaults: true,
              is_enabled: true,
              close_game_margin_threshold: null,
              close_game_time_threshold_seconds: null,
              inning_start_threshold: null,
            },
          ],
        }}
        onClose={vi.fn()}
        onUpdateGameAlertSettings={vi.fn(async () => undefined)}
        onResetGameAlertSettings={vi.fn(async () => undefined)}
      />,
    );

    expect(screen.queryByRole("button", { name: "Use sport settings" })).toBeNull();
  });

  it("shows football score and lead rules as disabled by default", () => {
    render(
      <GameAlertSettingsModal
        isOpen
        matchupLabel="KC at BUF"
        alertsBusy={false}
        gameAlertState={{
          game_id: 24,
          competition: "NFL",
          sport: "football",
          items: (["score_changed", "lead_change"] as const).map((alertType) => ({
            sport: "football",
            alert_type: alertType,
            uses_sport_defaults: true,
            is_enabled: false,
            close_game_margin_threshold: null,
            close_game_time_threshold_seconds: null,
            inning_start_threshold: null,
          })),
        }}
        onClose={vi.fn()}
        onUpdateGameAlertSettings={vi.fn(async () => undefined)}
        onResetGameAlertSettings={vi.fn(async () => undefined)}
      />,
    );

    expect(
      screen.getByRole("switch", { name: "Score update alerts for this game" }),
    ).toHaveAttribute("aria-checked", "false");
    expect(
      screen.getByRole("switch", { name: "Lead change alerts for this game" }),
    ).toHaveAttribute("aria-checked", "false");
  });
});
