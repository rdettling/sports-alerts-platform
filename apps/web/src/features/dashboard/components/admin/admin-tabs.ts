export const ADMIN_TABS = [
  { key: "leagues", label: "Leagues" },
  { key: "activity-tools", label: "Activity & tools" },
] as const;

export type AdminTab = (typeof ADMIN_TABS)[number]["key"];

export type AdminTabsHeaderProps = {
  tab: AdminTab;
  onTabChange: (tab: AdminTab) => void;
  isRefreshing: boolean;
  refreshFailed: boolean;
  onRefresh: () => void;
};
