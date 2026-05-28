import { type ReactNode } from "react";

type AlertRuleCardProps = {
  title: string;
  isDisabled?: boolean;
  cardClassName?: string;
  contentClassName?: string;
  headerClassName?: string;
  controlsClassName?: string;
  endSlot?: ReactNode;
  controls?: ReactNode;
};

export function AlertRuleCard({
  title,
  isDisabled = false,
  cardClassName,
  contentClassName,
  headerClassName,
  controlsClassName,
  endSlot,
  controls,
}: AlertRuleCardProps) {
  const cardClasses = ["row-card", "alert-rule-row", isDisabled ? "alert-rule-disabled" : "", cardClassName ?? ""].filter(Boolean).join(" ");
  const contentClasses = ["alert-rule-content", contentClassName ?? ""].filter(Boolean).join(" ");
  const headerClasses = ["alert-rule-header", headerClassName ?? ""].filter(Boolean).join(" ");
  const controlsClasses = ["alert-rule-controls", controlsClassName ?? ""].filter(Boolean).join(" ");

  return (
    <li className={cardClasses}>
      <div className={contentClasses}>
        <div className={headerClasses}>
          <div className="alert-rule-title-wrap">
            <strong>{title}</strong>
          </div>
          {endSlot}
        </div>
        {controls ? <div className={controlsClasses}>{controls}</div> : null}
      </div>
    </li>
  );
}
