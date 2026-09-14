"use client";

import { Scale } from "lucide-react";

import { EmptyState, ErrorState, TableSkeleton } from "@/components/shared/states";
import { JurisdictionBadge, RiskTierBadge } from "@/components/shared/status-badges";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useClassifications } from "@/hooks/use-classification";
import { formatDateTime, formatRelative } from "@/lib/format";
import type { RiskClassification } from "@/types/api";

export function RiskTab({ systemId, onRunClassification }: { systemId: string; onRunClassification?: () => void }) {
  const latest = useClassifications(systemId, true);
  const history = useClassifications(systemId, false);

  if (latest.isLoading) return <TableSkeleton rows={4} columns={4} />;
  if (latest.isError) return <ErrorState error={latest.error} onRetry={() => latest.refetch()} />;

  const records = latest.data ?? [];
  if (!records.length) {
    return (
      <EmptyState
        icon={Scale}
        title="Not classified yet"
        description="Run a classification to score this system against every applicable jurisdiction."
        action={onRunClassification ? { label: "Run classification", onClick: onRunClassification } : undefined}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        {records.map((record) => (
          <ClassificationCard key={record.id} record={record} />
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Classification history</CardTitle>
          <CardDescription>
            Append-only. Every run writes a new record; nothing is ever overwritten.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Evaluated</TableHead>
                  <TableHead>Jurisdiction</TableHead>
                  <TableHead>Tier</TableHead>
                  <TableHead className="text-right">Score</TableHead>
                  <TableHead className="hidden sm:table-cell text-right">Metadata v</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(history.data ?? []).map((record) => (
                  <TableRow key={record.id}>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDateTime(record.evaluated_at)}
                    </TableCell>
                    <TableCell>
                      <JurisdictionBadge code={record.jurisdiction_code} />
                    </TableCell>
                    <TableCell>
                      <RiskTierBadge tier={record.risk_tier} />
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{record.score.toFixed(1)}</TableCell>
                    <TableCell className="hidden sm:table-cell text-right tabular-nums text-muted-foreground">
                      v{record.metadata_version}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function ClassificationCard({ record }: { record: RiskClassification }) {
  const baseline = record.details?.baseline;
  const overlay = record.details?.overlay;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <JurisdictionBadge code={record.jurisdiction_code} />
            {overlay?.tier_label ?? "Risk classification"}
          </CardTitle>
          <RiskTierBadge tier={record.risk_tier} />
        </div>
        <CardDescription>Assessed {formatRelative(record.evaluated_at)}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <div className="mb-1.5 flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Risk score</span>
            <span className="font-medium tabular-nums">{record.score.toFixed(1)} / 100</span>
          </div>
          <Progress value={record.score} className="h-2" />
        </div>

        {baseline?.signals?.length ? (
          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Contributing signals
            </p>
            <ul className="space-y-1">
              {baseline.signals.map((signal) => (
                <li key={signal.signal} className="flex items-start justify-between gap-3 text-sm">
                  <span>{signal.rationale}</span>
                  <span className="shrink-0 tabular-nums text-muted-foreground">
                    +{signal.weight}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {overlay?.notes?.length ? (
          <>
            <Separator />
            <div>
              <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Jurisdiction overlay
              </p>
              <ul className="list-inside list-disc space-y-1 text-sm">
                {overlay.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </div>
          </>
        ) : null}

        {overlay?.obligations?.length ? (
          <>
            <Separator />
            <div>
              <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Obligations at this tier
              </p>
              <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
                {overlay.obligations.map((obligation) => (
                  <li key={obligation}>{obligation}</li>
                ))}
              </ul>
            </div>
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}
