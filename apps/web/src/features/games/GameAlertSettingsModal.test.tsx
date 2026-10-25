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
          items: [
            {
              competition: "WNBA",
              alert_type: "game_start",
              uses_league_defaults: false,
              is_enabled: true,
              close_game_margin_threshold: null,
              close_game_time_threshold_seconds: null,
              periods: null,
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
      periods: null,
    });

    fireEvent.click(screen.getByRole("button", { name: "Use league settings" }));
    expect(onResetGameAlertSettings).toHaveBeenCalledWith(12, "game_start");
  });

  it.each([
    ["NBA", "quarter_start", "Q", [2, 4]],
    ["NHL", "period_start", "P", [2]],
    ["MLB", "inning_start", "Inning ", [2, 9]],
  ] as const)(
    "selects starts for a %s game override",
    (competition, alertType, prefix, periods) => {
      const onUpdate = vi.fn(async () => undefined);
      render(
        <GameAlertSettingsModal
          isOpen
          matchupLabel="Away at Home"
          alertsBusy={false}
          gameAlertState={{
            game_id: 12,
            competition,
            items: [
              {
                competition,
                alert_type: alertType,
                uses_league_defaults: true,
                is_enabled: true,
                close_game_margin_threshold: null,
                close_game_time_threshold_seconds: null,
                periods: [...periods],
              },
            ],
          }}
          onClose={vi.fn()}
          onUpdateGameAlertSettings={onUpdate}
          onResetGameAlertSettings={vi.fn(async () => undefined)}
        />,
      );
      expect(screen.getByRole("checkbox", { name: `${prefix}2` })).toBeChecked();
      expect(screen.getByRole("checkbox", { name: `${prefix}3` })).not.toBeChecked();
      fireEvent.click(screen.getByRole("checkbox", { name: `${prefix}2` }));
      expect(onUpdate).toHaveBeenCalledWith(
        12,
        alertType,
        expect.objectContaining({ periods: periods.filter((period) => period !== 2) }),
      );
    },
  );

  it("hides reset for game alerts already using league settings", () => {
    render(
      <GameAlertSettingsModal
        isOpen
        matchupLabel="NY at LV"
        alertsBusy={false}
        gameAlertState={{
          game_id: 12,
          competition: "WNBA",
          items: [
            {
              competition: "WNBA",
              alert_type: "game_start",
              uses_league_defaults: true,
              is_enabled: true,
              close_game_margin_threshold: null,
              close_game_time_threshold_seconds: null,
              periods: null,
            },
          ],
        }}
        onClose={vi.fn()}
        onUpdateGameAlertSettings={vi.fn(async () => undefined)}
        onResetGameAlertSettings={vi.fn(async () => undefined)}
      />,
    );

    expect(screen.queryByRole("button", { name: "Use league settings" })).toBeNull();
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
          items: (["score_changed", "lead_change"] as const).map((alertType) => ({
            competition: "NFL",
            alert_type: alertType,
            uses_league_defaults: true,
            is_enabled: false,
            close_game_margin_threshold: null,
            close_game_time_threshold_seconds: null,
            periods: null,
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
