"use client";

import { Globe2, Info, ShieldAlert } from "lucide-react";

import { EmptyState, ErrorState, TableSkeleton } from "@/components/shared/states";
import { JurisdictionBadge } from "@/components/shared/status-badges";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useJurisdictionDetection } from "@/hooks/use-classification";
import { formatPercent, humanize } from "@/lib/format";
import { cn } from "@/lib/utils";

export function JurisdictionsTab({ systemId }: { systemId: string }) {
  const { data, isLoading, isError, error, refetch } = useJurisdictionDetection(systemId);

  if (isLoading) return <TableSkeleton rows={4} columns={3} />;
  if (isError) return <ErrorState error={error} onRetry={() => refetch()} />;
  if (!data) return null;

  const applicable = data.matches.filter((m) => m.applicable);
  const notApplicable = data.matches.filter((m) => !m.applicable);

  return (
    <div className="space-y-6">
      {applicable.length === 0 ? (
        <EmptyState
          icon={Globe2}
          title="No jurisdiction applies to this system"
          description="Nothing in the recorded metadata creates a deployment, offering, data-subject, residency or accessibility nexus. Add the regions the system reaches to change this."
        />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Card>
              <CardContent className="p-5">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Applicable
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {(data.applicable_jurisdictions ?? []).map((code) => (
                    <JurisdictionBadge key={code} code={code} />
                  ))}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-5">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Assessment order
                </p>
                <p className="mt-2 font-mono text-sm">
                  {(data.evaluation_order ?? []).join(" → ") || "—"}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">Strictest regime first.</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-5">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Takes priority
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {(data.most_restrictive_jurisdictions ?? []).map((code) => (
                    <JurisdictionBadge key={code} code={code} />
                  ))}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Wins where obligations conflict.
                </p>
              </CardContent>
            </Card>
          </div>

          {data.apply_most_restrictive && data.conflict_notes?.length ? (
            <Alert>
              <ShieldAlert className="h-4 w-4" />
              <AlertTitle>Most-restrictive mode applies</AlertTitle>
              <AlertDescription>
                <ul className="mt-1 list-inside list-disc space-y-1">
                  {data.conflict_notes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          ) : null}
        </>
      )}

      <div className="space-y-4">
        {[...applicable, ...notApplicable].map((match) => (
          <Card key={match.code} className={cn(!match.applicable && "opacity-70")}>
            <CardHeader className="pb-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <JurisdictionBadge code={match.code} />
                    {match.name}
                  </CardTitle>
                  {match.regulation_name ? (
                    <CardDescription className="mt-1">{match.regulation_name}</CardDescription>
                  ) : null}
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  {match.applicable ? (
                    <>
                      <span>Confidence {formatPercent(match.confidence)}</span>
                      {typeof match.strictness === "number" ? (
                        <span>· Strictness {match.strictness}</span>
                      ) : null}
                    </>
                  ) : (
                    <Badge variant="outline">Not applicable</Badge>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Why
                </p>
                <ul className="space-y-1.5">
                  {match.reasons.map((reason) => (
                    <li key={reason} className="flex items-start gap-2 text-sm">
                      <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                      {reason}
                    </li>
                  ))}
                </ul>
              </div>

              {match.applicable && match.signals?.length ? (
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-xs text-muted-foreground">Signals:</span>
                  {match.signals.map((signal) => (
                    <Badge key={signal} variant="secondary" className="font-mono text-xs">
                      {humanize(signal)}
                    </Badge>
                  ))}
                </div>
              ) : null}

              {match.matched_territories?.length ? (
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-xs text-muted-foreground">Territories:</span>
                  {match.matched_territories.map((territory) => (
                    <JurisdictionBadge key={territory} code={territory} />
                  ))}
                </div>
              ) : null}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
