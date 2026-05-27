import { createContext, useContext } from "react";

export type DashboardRouteKey = "games" | "following" | "alerts" | "admin";

export type DashboardRouteMeta = {
  key: DashboardRouteKey;
  path: string;
  label: string;
  subtitle: string;
  adminOnly?: boolean;
};

export const DASHBOARD_ROUTES: DashboardRouteMeta[] = [
  { key: "games", path: "games", label: "Games", subtitle: "NBA game slate and follow actions" },
  { key: "following", path: "following", label: "Following", subtitle: "Manage your followed teams and games" },
  { key: "alerts", path: "alerts", label: "Alerts", subtitle: "Configure rules and review delivery history" },
  { key: "admin", path: "admin", label: "Admin", subtitle: "Operational telemetry and test tools", adminOnly: true },
];

type DashboardShellContextValue = {
  setLastSync: (value: Date | null) => void;
  setHeaderSyncItems: (items: HeaderSyncItem[] | null) => void;
};

export type HeaderSyncItem = {
  key: string;
  label: string;
  value: string;
  tone: "fresh" | "stale" | "idle";
};

const DashboardShellContext = createContext<DashboardShellContextValue | undefined>(undefined);

export function DashboardShellProvider({
  value,
  children,
}: {
  value: DashboardShellContextValue;
  children: React.ReactNode;
}) {
  return <DashboardShellContext.Provider value={value}>{children}</DashboardShellContext.Provider>;
}

export function useDashboardShell() {
  const ctx = useContext(DashboardShellContext);
  if (!ctx) {
    throw new Error("useDashboardShell must be used inside DashboardShellProvider");
  }
  return ctx;
}
