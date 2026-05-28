import { createContext, useContext } from "react";

export type HeaderSyncItem = {
  key: string;
  label: string;
  value: string;
  tone: "fresh" | "stale" | "idle";
};

type DashboardShellContextValue = {
  setLastSync: (value: Date | null) => void;
  setHeaderSyncItems: (items: HeaderSyncItem[] | null) => void;
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
