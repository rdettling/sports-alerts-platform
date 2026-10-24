import { type Competition } from "../../shared/api";

type BasketballTiming = {
  regulationPeriods: number;
  periodSeconds: number;
};

export const BASKETBALL_TIMING: Partial<Record<Competition, BasketballTiming>> = {
  NCAAB: { regulationPeriods: 2, periodSeconds: 20 * 60 },
  NBA: { regulationPeriods: 4, periodSeconds: 12 * 60 },
  WNBA: { regulationPeriods: 4, periodSeconds: 10 * 60 },
};
