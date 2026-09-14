"use client";

import { ChevronDown, ClipboardCheck, Wrench } from "lucide-react";
import { useState } from "react";

import { EmptyState, ErrorState, TableSkeleton } from "@/components/shared/states";
import {
  ComplianceBadge,
  JurisdictionBadge,
  PolicyResultBadge,
  SeverityBadge,
} from "@/components/shared/status-badges";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Separator } from "@/components/ui/separator";
import { usePolicyChecks } from "@/hooks/use-policy-checks";
import { formatRelative, humanize } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { PolicyCheck } from "@/types/api";

export function PoliciesTab({
  systemId,
  onRunChecks,
}: {
  systemId: string;
  onRunChecks?: () => void;
}) {
  const { data, isLoading, isError, error, refetch } = usePolicyChecks(systemId, true);

  if (isLoading) return <TableSkeleton rows={5} columns={4} />;
  if (isError) return <ErrorState error={error} onRetry={() => refetch()} />;

  const checks = data?.items ?? [];
  if (!checks.length) {
    return (
      <EmptyState
        icon={ClipboardCheck}
        title="No policy checks yet"
        description="Run the policy checks to evaluate this system against every applicable rule, with the article and remediation for each finding."
        action={onRunChecks ? { label: "Run policy checks", onClick: onRunChecks } : undefined}
      />
    );
  }

  const passed = checks.filter((c) => c.result === "pass").length;
  const failed = checks.filter((c) => c.result === "fail").length;
  const warnings = checks.filter((c) => c.result === "warning").length;
  const errors = checks.filter((c) => c.result === "error").length;
  const compliant = failed === 0 && errors === 0;

  // Failures first: the point of this screen is what needs fixing.
  const order = { fail: 0, error: 1, warning: 2, pass: 3 } as const;
  const sorted = [...checks].sort((a, b) => order[a.result] - order[b.result]);
  const lastChecked = checks.reduce<string | null>(
    (latest, check) => (!latest || check.checked_at > latest ? check.checked_at : latest),
    null,
  );

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base">Latest results</CardTitle>
              <CardDescription>Checked {formatRelative(lastChecked)}</CardDescription>
            </div>
            <ComplianceBadge compliant={compliant} />
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
            <Stat label="Total" value={checks.length} />
            <Stat label="Passed" value={passed} tone="pass" />
            <Stat label="Failed" value={failed} tone="fail" />
            <Stat label="Warnings" value={warnings} tone="warn" />
            <Stat label="Not evaluated" value={errors} />
          </div>
        </CardContent>
      </Card>

      <div className="space-y-3">
        {sorted.map((check) => (
          <CheckRow key={check.id} check={check} />
        ))}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: number;
  tone?: "default" | "pass" | "warn" | "fail";
}) {
  const toneClass = {
    default: "text-foreground",
    pass: "text-status-pass-foreground",
    warn: "text-status-warn-foreground",
    fail: "text-status-fail-foreground",
  }[tone];

  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={cn("mt-1 text-2xl font-semibold tabular-nums", toneClass)}>{value}</p>
    </div>
  );
}

function CheckRow({ check }: { check: PolicyCheck }) {
  // Failures start open: a compliance officer should not have to hunt for the problem.
  const [open, setOpen] = useState(check.result === "fail" || check.result === "error");
  const hasDetail = check.violations.length > 0 || check.remediation.length > 0;

  return (
    <Card
      className={cn(
        check.result === "fail" && "border-status-fail-foreground/30",
        check.result === "warning" && "border-status-warn-foreground/30",
      )}
    >
      <Collapsible open={open} onOpenChange={setOpen}>
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="flex w-full items-start gap-3 p-4 text-left transition-colors hover:bg-muted/40"
          >
            <div className="min-w-0 flex-1 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <PolicyResultBadge result={check.result} />
                <SeverityBadge severity={check.severity} />
                <JurisdictionBadge code={check.jurisdiction_code} />
                <span className="font-mono text-xs text-muted-foreground">
                  {check.policy_key} v{check.policy_version}
                </span>
                {check.engine !== "opa" ? (
                  <Badge variant="outline" className="text-xs">
                    {check.engine === "rules" ? "declarative fallback" : "not evaluated"}
                  </Badge>
                ) : null}
              </div>
              <p className="text-sm leading-relaxed">{check.explanation}</p>
            </div>
            {hasDetail ? (
              <ChevronDown
                className={cn(
                  "mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                  open && "rotate-180",
                )}
              />
            ) : null}
          </button>
        </CollapsibleTrigger>

        {hasDetail ? (
          <CollapsibleContent>
            <Separator />
            <div className="space-y-4 p-4">
              {check.violations.map((violation, index) => (
                <div key={`${violation.rule_id}-${index}`} className="rounded-lg border bg-muted/30 p-4">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    {violation.article ? (
                      <Badge variant="secondary" className="font-medium">
                        {violation.article}
                      </Badge>
                    ) : null}
                    <SeverityBadge severity={violation.severity} />
                    <code className="text-xs text-muted-foreground">{violation.rule_id}</code>
                  </div>
                  <p className="text-sm leading-relaxed">{violation.msg}</p>
                  {violation.remediation ? (
                    <div className="mt-3 flex items-start gap-2 rounded-md bg-status-info px-3 py-2.5">
                      <Wrench className="mt-0.5 h-4 w-4 shrink-0 text-status-info-foreground" />
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-status-info-foreground">
                          How to fix
                        </p>
                        <p className="mt-0.5 text-sm leading-relaxed text-status-info-foreground">
                          {violation.remediation}
                        </p>
                      </div>
                    </div>
                  ) : null}
                </div>
              ))}

              {check.violations.length === 0 && check.remediation.length > 0 ? (
                <ul className="list-inside list-disc space-y-1 text-sm">
                  {check.remediation.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : null}

              <p className="text-xs text-muted-foreground">
                Evaluated by {humanize(check.engine)} · {formatRelative(check.checked_at)}
              </p>
            </div>
          </CollapsibleContent>
        ) : null}
      </Collapsible>
    </Card>
  );
}
