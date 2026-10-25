export function PeriodSelection({
  alertType,
  periods,
  disabled,
  onChange,
}: {
  alertType: "quarter_start" | "period_start" | "inning_start";
  periods: number[];
  disabled: boolean;
  onChange: (periods: number[]) => void;
}) {
  const isQuarter = alertType === "quarter_start";
  const isInning = alertType === "inning_start";
  const options = isInning ? [1, 2, 3, 4, 5, 6, 7, 8, 9] : isQuarter ? [2, 3, 4] : [2, 3];
  return (
    <fieldset
      className="period-selection"
      aria-label={isInning ? "Innings" : isQuarter ? "Quarters" : "Periods"}
      disabled={disabled}
    >
      {options.map((period) => (
        <label key={period}>
          <input
            aria-label={isInning ? `Inning ${period}` : undefined}
            type="checkbox"
            checked={periods.includes(period)}
            onChange={(event) =>
              onChange(
                event.target.checked
                  ? [...periods, period].sort()
                  : periods.filter((value) => value !== period),
              )
            }
          />
          {isInning ? "" : isQuarter ? "Q" : "P"}
          {period}
        </label>
      ))}
    </fieldset>
  );
}
