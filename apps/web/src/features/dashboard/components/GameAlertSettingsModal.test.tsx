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
        onApplyAlertOverride={vi.fn(async () => undefined)}
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
    const onApplyAlertOverride = vi.fn(async () => undefined);
    render(
      <GameAlertSettingsModal
        isOpen
        matchupLabel="NY at LV"
        alertsBusy={false}
        gameAlertState={{
          game_id: 12,
          league: "WNBA",
          items: [
            {
              league: "WNBA",
              alert_type: "game_start",
              use_league_default: true,
              is_enabled: true,
              close_game_margin_threshold: null,
              close_game_time_threshold_seconds: null,
              inning_start_threshold: null,
              override: null,
            },
          ],
        }}
        onClose={vi.fn()}
        onApplyAlertOverride={onApplyAlertOverride}
      />,
    );

    const toggle = screen.getByRole("switch", { name: "Game start alerts for this game" });
    expect(screen.getByRole("listitem")).toHaveClass("alert-rule-row", "game-alert-row");
    expect(toggle).toHaveAttribute("aria-checked", "true");
    expect(toggle).toHaveTextContent("On");

    fireEvent.click(toggle);
    expect(onApplyAlertOverride).toHaveBeenCalledWith(
      12,
      "game_start",
      expect.objectContaining({ is_enabled_override: false }),
    );
  });
});
