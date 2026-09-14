"use client";

import {
  AlertTriangle,
  ArrowRight,
  ClipboardCheck,
  FileCheck2,
  Server,
  ShieldAlert,
} from "lucide-react";
import Link from "next/link";

import {
  JurisdictionComplianceChart,
  RiskTierChart,
} from "@/components/dashboard/charts";
import { StatCard } from "@/components/dashboard/stat-cards";
import { PageHeader } from "@/components/shared/page-header";
import {
  CardsSkeleton,
  EmptyState,
  ErrorState,
  TableSkeleton,
} from "@/components/shared/states";
import {
  JurisdictionBadge,
  SeverityBadge,
} from "@/components/shared/status-badges";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboardSummary, useJurisdictionDashboard } from "@/hooks/use-dashboard";
import { formatRelative, truncate } from "@/lib/format";

export default function DashboardPage() {
  const summary = useDashboardSummary();
  const jurisdictions = useJurisdictionDashboard();

  return (
    <>
      <PageHeader
        title="Compliance overview"
        description={
          summary.data
            ? `Across ${summary.data.total_systems} AI ${
                summary.data.total_systems === 1 ? "system" : "systems"
              } in ${summary.data.jurisdictions_in_scope} ${
                summary.data.jurisdictions_in_scope === 1 ? "jurisdiction" : "jurisdictions"
              }`
            : "Portfolio-wide compliance posture"
        }
        actions={
          <Button asChild variant="outline">
            <Link href="/systems">
              View inventory
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        }
      />

      {summary.isLoading ? (
        <CardsSkeleton />
      ) : summary.isError ? (
        <ErrorState error={summary.error} onRetry={() => summary.refetch()} />
      ) : summary.data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Compliance score"
              value={`${summary.data.overall_compliance_score}%`}
              hint={`${summary.data.systems_assessed} of ${summary.data.total_systems} systems assessed`}
              icon={ClipboardCheck}
              tone={
                summary.data.overall_compliance_score >= 80
                  ? "pass"
                  : summary.data.overall_compliance_score >= 50
                    ? "warn"
                    : "fail"
              }
            />
            <StatCard
              label="AI systems"
              value={summary.data.total_systems}
              hint={`${summary.data.active_systems} active · ${summary.data.draft_systems} draft`}
              icon={Server}
              href="/systems"
            />
            <StatCard
              label="Open failures"
              value={summary.data.open_failures}
              hint={`${summary.data.critical_failures} critical`}
              icon={ShieldAlert}
              tone={summary.data.open_failures > 0 ? "fail" : "pass"}
            />
            <StatCard
              label="Evidence packages"
              value={summary.data.evidence_packages_30d}
              hint="Generated in the last 30 days"
              icon={FileCheck2}
              href="/evidence"
            />
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-base">Compliance by jurisdiction</CardTitle>
                <CardDescription>
                  Systems in scope for each regime, split by their latest check result.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {jurisdictions.isLoading ? (
                  <Skeleton className="h-[280px] w-full" />
                ) : jurisdictions.isError ? (
                  <ErrorState error={jurisdictions.error} onRetry={() => jurisdictions.refetch()} />
                ) : (
                  <JurisdictionComplianceChart data={jurisdictions.data?.jurisdictions ?? []} />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Risk distribution</CardTitle>
                <CardDescription>Latest tier per system, most restrictive regime.</CardDescription>
              </CardHeader>
              <CardContent>
                <RiskTierChart data={summary.data.risk_tiers} />
              </CardContent>
            </Card>
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Recent failures</CardTitle>
                <CardDescription>Most recent failing policy checks.</CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                {summary.data.recent_failures.length === 0 ? (
                  <EmptyState
                    icon={ClipboardCheck}
                    title="No failing checks"
                    description="Every policy check on record is currently passing."
                    className="py-12"
                  />
                ) : (
                  <ul className="divide-y">
                    {summary.data.recent_failures.slice(0, 6).map((failure) => (
                      <li key={failure.check_id}>
                        <Link
                          href={`/systems/${failure.ai_system_id}?tab=policies`}
                          className="flex items-start gap-3 px-6 py-3.5 transition-colors hover:bg-muted/50"
                        >
                          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-status-fail-foreground" />
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="truncate text-sm font-medium">
                                {failure.ai_system_name}
                              </span>
                              <JurisdictionBadge code={failure.jurisdiction_code} />
                              <SeverityBadge severity={failure.severity} />
                            </div>
                            <p className="mt-1 text-xs text-muted-foreground">
                              {truncate(failure.explanation, 130)}
                            </p>
                            <p className="mt-1 text-xs text-muted-foreground">
                              {formatRelative(failure.checked_at)}
                            </p>
                          </div>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Needs attention</CardTitle>
                <CardDescription>Systems awaiting classification or reassessment.</CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                {summary.data.pending_reviews.length === 0 ? (
                  <EmptyState
                    icon={ClipboardCheck}
                    title="Everything is up to date"
                    description="No system is waiting on a classification."
                    className="py-12"
                  />
                ) : (
                  <ul className="divide-y">
                    {summary.data.pending_reviews.slice(0, 6).map((review) => (
                      <li key={review.ai_system_id}>
                        <Link
                          href={`/systems/${review.ai_system_id}`}
                          className="flex items-center justify-between gap-3 px-6 py-3.5 transition-colors hover:bg-muted/50"
                        >
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium">{review.ai_system_name}</p>
                            <p className="text-xs text-muted-foreground">{review.reason}</p>
                          </div>
                          <span className="shrink-0 text-xs text-muted-foreground">
                            {review.last_evaluated_at
                              ? formatRelative(review.last_evaluated_at)
                              : "never assessed"}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      ) : (
        <TableSkeleton />
      )}
    </>
  );
}
