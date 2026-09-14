import type { RiskTier } from "@/types/api";

/** Mirrors RISK_TIER_ORDER in the backend, so "most restrictive" means the same thing. */
export const RISK_TIER_ORDER: Record<RiskTier, number> = {
  unknown: 0,
  minimal: 1,
  limited: 2,
  high: 3,
  prohibited: 4,
};
