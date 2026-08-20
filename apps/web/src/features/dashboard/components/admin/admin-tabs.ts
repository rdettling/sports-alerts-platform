import { type OpsAdminOverviewWindow } from "../../../../shared/api";

export const ADMIN_TABS = [
  { key: "overview", label: "Overview" },
  { key: "tools", label: "Tools" },
] as const;

export type AdminTab = (typeof ADMIN_TABS)[number]["key"];

export type AdminTabsHeaderProps = {
  tab: AdminTab;
  onTabChange: (tab: AdminTab) => void;
  windowValue: OpsAdminOverviewWindow;
  onWindowChange: (value: OpsAdminOverviewWindow) => void;
  updatedAtLabel: string | null;
  isRefreshing: boolean;
  refreshFailed: boolean;
};
