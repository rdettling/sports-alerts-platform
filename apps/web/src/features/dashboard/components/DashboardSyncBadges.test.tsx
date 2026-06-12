import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DashboardSyncBadges } from "./DashboardSyncBadges";

describe("DashboardSyncBadges", () => {
  it("renders a two-row sync table with three sources", () => {
    const { container } = render(
      <DashboardSyncBadges
        items={[
          { key: "catalog", label: "Catalog", value: "3h ago", tone: "fresh" },
          { key: "nba", label: "NBA", value: "5m ago", tone: "stale" },
          { key: "mlb", label: "MLB", value: "Sync pending", tone: "idle" },
        ]}
      />,
    );

    expect(screen.getByText("Catalog")).toBeInTheDocument();
    expect(screen.getByText("NBA")).toBeInTheDocument();
    expect(screen.getByText("MLB")).toBeInTheDocument();
    expect(screen.getByText("Last sync")).toBeInTheDocument();
    expect(container.querySelectorAll("th")).toHaveLength(4);
    expect(container.querySelectorAll("td")).toHaveLength(3);
  });

  it("renders all sync items in topbar mode", () => {
    render(
      <DashboardSyncBadges
        variant="topbar"
        items={[
          { key: "catalog", label: "Catalog", value: "3h ago", tone: "fresh" },
          { key: "nba", label: "NBA", value: "5m ago", tone: "stale" },
          { key: "mlb", label: "MLB", value: "2m ago", tone: "fresh" },
          { key: "world-cup", label: "World Cup", value: "4m ago", tone: "fresh" },
        ]}
      />,
    );

    expect(screen.getByText("Last sync")).toBeInTheDocument();
    expect(screen.getByText("Catalog")).toBeInTheDocument();
    expect(screen.getByText("NBA")).toBeInTheDocument();
    expect(screen.getByText("MLB")).toBeInTheDocument();
    expect(screen.getByText("World Cup")).toBeInTheDocument();
    expect(screen.getByText("4m")).toBeInTheDocument();
  });
});
