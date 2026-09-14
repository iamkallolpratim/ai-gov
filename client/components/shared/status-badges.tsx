import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  CircleDashed,
  HelpCircle,
  Info,
  ShieldAlert,
  XCircle,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { RISK_TIER_LABELS, SEVERITY_LABELS, STATUS_LABELS } from "@/lib/constants";
import type {
  EvidenceStatus,
  PolicyResult,
  PolicySeverity,
  RiskTier,
  SystemStatus,
} from "@/types/api";

/**
 * Every status colour in the product comes from here. Call sites pass a domain value,
 * never a colour, so "red means fail" stays true across the app and in both themes.
 */
const base =
  "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium whitespace-nowrap";

const TONE = {
  pass: "border-transparent bg-status-pass text-status-pass-foreground",
  warn: "border-transparent bg-status-warn text-status-warn-foreground",
  fail: "border-transparent bg-status-fail text-status-fail-foreground",
  info: "border-transparent bg-status-info text-status-info-foreground",
  neutral: "border-border bg-muted text-muted-foreground",
} as const;

type Tone = keyof typeof TONE;

const RISK_TONE: Record<RiskTier, Tone> = {
  prohibited: "fail",
  high: "fail",
  limited: "warn",
  minimal: "pass",
  unknown: "neutral",
};

const RISK_ICON: Record<RiskTier, typeof Ban> = {
  prohibited: Ban,
  high: ShieldAlert,
  limited: AlertTriangle,
  minimal: CheckCircle2,
  unknown: HelpCircle,
};

export function RiskTierBadge({ tier, className }: { tier: RiskTier; className?: string }) {
  const Icon = RISK_ICON[tier];
  return (
    <span className={cn(base, TONE[RISK_TONE[tier]], className)}>
      <Icon className="h-3.5 w-3.5" aria-hidden />
      {RISK_TIER_LABELS[tier]}
    </span>
  );
}

const RESULT_TONE: Record<PolicyResult, Tone> = {
  pass: "pass",
  warning: "warn",
  fail: "fail",
  error: "neutral",
};

const RESULT_ICON: Record<PolicyResult, typeof CheckCircle2> = {
  pass: CheckCircle2,
  warning: AlertTriangle,
  fail: XCircle,
  error: HelpCircle,
};

const RESULT_LABEL: Record<PolicyResult, string> = {
  pass: "Pass",
  warning: "Warning",
  fail: "Fail",
  error: "Not evaluated",
};

export function PolicyResultBadge({ result, className }: { result: PolicyResult; className?: string }) {
  const Icon = RESULT_ICON[result];
  return (
    <span className={cn(base, TONE[RESULT_TONE[result]], className)}>
      <Icon className="h-3.5 w-3.5" aria-hidden />
      {RESULT_LABEL[result]}
    </span>
  );
}

const SEVERITY_TONE: Record<PolicySeverity, Tone> = {
  critical: "fail",
  high: "fail",
  medium: "warn",
  low: "info",
  info: "neutral",
};

export function SeverityBadge({ severity, className }: { severity: PolicySeverity; className?: string }) {
  return (
    <span className={cn(base, TONE[SEVERITY_TONE[severity]], className)}>
      {SEVERITY_LABELS[severity]}
    </span>
  );
}

const SYSTEM_STATUS_TONE: Record<SystemStatus, Tone> = {
  active: "info",
  draft: "neutral",
  retired: "neutral",
};

export function SystemStatusBadge({ status, className }: { status: SystemStatus; className?: string }) {
  return (
    <span className={cn(base, TONE[SYSTEM_STATUS_TONE[status]], className)}>
      {STATUS_LABELS[status]}
    </span>
  );
}

const EVIDENCE_TONE: Record<EvidenceStatus, Tone> = {
  completed: "pass",
  running: "info",
  pending: "neutral",
  failed: "fail",
};

const EVIDENCE_ICON: Record<EvidenceStatus, typeof CheckCircle2> = {
  completed: CheckCircle2,
  running: CircleDashed,
  pending: CircleDashed,
  failed: XCircle,
};

export function EvidenceStatusBadge({
  status,
  stalled = false,
  className,
}: {
  status: EvidenceStatus;
  /** In flight far longer than a real job takes; will not finish on its own. */
  stalled?: boolean;
  className?: string;
}) {
  if (stalled) {
    return (
      <span className={cn(base, TONE.warn, className)}>
        <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
        Stalled
      </span>
    );
  }
  const Icon = EVIDENCE_ICON[status];
  const spinning = status === "pending" || status === "running";
  return (
    <span className={cn(base, TONE[EVIDENCE_TONE[status]], className)}>
      <Icon className={cn("h-3.5 w-3.5", spinning && "animate-spin")} aria-hidden />
      {status[0].toUpperCase() + status.slice(1)}
    </span>
  );
}

export function ComplianceBadge({ compliant, className }: { compliant: boolean; className?: string }) {
  return (
    <span className={cn(base, TONE[compliant ? "pass" : "fail"], className)}>
      {compliant ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
      {compliant ? "Compliant" : "Non-compliant"}
    </span>
  );
}

export function InfoBadge({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn(base, TONE.info, className)}>
      <Info className="h-3.5 w-3.5" aria-hidden />
      {children}
    </span>
  );
}

export function JurisdictionBadge({ code, className }: { code: string; className?: string }) {
  return <span className={cn(base, TONE.neutral, "font-mono", className)}>{code}</span>;
}
