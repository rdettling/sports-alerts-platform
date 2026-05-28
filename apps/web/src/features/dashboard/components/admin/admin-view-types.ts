import { type OpsAdminOverviewWindow } from "../../../../shared/api";

export type AdminTab = "espn" | "odds" | "resend" | "db" | "tools";

export type ProviderKey = "espn" | "odds" | "resend";

export type AdminTabsHeaderProps = {
  tab: AdminTab;
  onTabChange: (tab: AdminTab) => void;
  windowValue: OpsAdminOverviewWindow;
  onWindowChange: (value: OpsAdminOverviewWindow) => void;
  updatedAtLabel: string | null;
};
