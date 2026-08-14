type LeagueTabOption<T extends string> = {
  value: T;
  label: string;
  ariaLabel?: string;
};

export function ScopeToggle({
  ariaLabel,
  allLabel,
  value,
  followingCount,
  onChange,
}: {
  ariaLabel: string;
  allLabel: string;
  value: "all" | "following";
  followingCount: number;
  onChange: (value: "all" | "following") => void;
}) {
  return (
    <div className="scope-toggle" role="group" aria-label={ariaLabel}>
      <button
        className={`scope-toggle-button ${value === "all" ? "active" : ""}`.trim()}
        type="button"
        aria-pressed={value === "all"}
        onClick={() => onChange("all")}
      >
        {allLabel}
      </button>
      <button
        className={`scope-toggle-button ${value === "following" ? "active" : ""}`.trim()}
        type="button"
        aria-pressed={value === "following"}
        onClick={() => onChange("following")}
      >
        Following <span>{followingCount}</span>
      </button>
    </div>
  );
}

export function LeagueTabs<T extends string>({
  ariaLabel,
  options,
  value,
  onChange,
}: {
  ariaLabel: string;
  options: Array<LeagueTabOption<T>>;
  value: T | null;
  onChange: (value: T) => void;
}) {
  return (
    <div className="league-tabs" role="group" aria-label={ariaLabel}>
      {options.map((option) => (
        <button
          key={option.value}
          className={`league-tab ${value === option.value ? "active" : ""}`.trim()}
          type="button"
          aria-label={option.ariaLabel}
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
