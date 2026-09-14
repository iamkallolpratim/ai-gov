"use client";

import { ChevronDown, Download, FileCheck2, FileJson, RotateCcw } from "lucide-react";
import { useState } from "react";

import { RoleGate } from "@/components/shared/role-gate";
import { EmptyState, ErrorState, TableSkeleton } from "@/components/shared/states";
import { EvidenceStatusBadge, JurisdictionBadge } from "@/components/shared/status-badges";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
  canRetry,
  isStalled,
  useDownloadEvidence,
  useRetryEvidence,
  useSystemEvidence,
} from "@/hooks/use-evidence";
import { formatDateTime, formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { EvidencePackage } from "@/types/api";

export function EvidenceTab({
  systemId,
  onGenerate,
}: {
  systemId: string;
  onGenerate?: () => void;
}) {
  const { data, isLoading, isError, error, refetch } = useSystemEvidence(systemId);
  const [showFailed, setShowFailed] = useState(false);

  if (isLoading) return <TableSkeleton rows={3} columns={4} />;
  if (isError) return <ErrorState error={error} onRetry={() => refetch()} />;

  const packages = data?.items ?? [];
  if (!packages.length) {
    return (
      <EmptyState
        icon={FileCheck2}
        title="No evidence packages yet"
        description="Generate a package to bundle this system's metadata, classifications and policy results into an audit-ready PDF and JSON manifest."
        action={onGenerate ? { label: "Generate evidence package", onClick: onGenerate } : undefined}
      />
    );
  }

  // Lead with what is usable; failed attempts stay one click away.
  const active = packages.filter((p) => p.status !== "failed");
  const failed = packages.filter((p) => p.status === "failed");

  return (
    <div className="space-y-3">
      {active.map((pkg) => (
        <PackageCard key={pkg.id} pkg={pkg} systemId={systemId} />
      ))}

      {active.length === 0 ? (
        <p className="px-1 text-sm text-muted-foreground">
          No package has completed yet. Retry a failed attempt below, or generate a new one.
        </p>
      ) : null}

      {failed.length ? (
        <Collapsible open={showFailed} onOpenChange={setShowFailed}>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="gap-2 px-2 text-muted-foreground">
              <ChevronDown
                className={cn("h-4 w-4 transition-transform", showFailed && "rotate-180")}
              />
              {failed.length} failed {failed.length === 1 ? "attempt" : "attempts"}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-3 space-y-3">
            {failed.map((pkg) => (
              <PackageCard key={pkg.id} pkg={pkg} systemId={systemId} />
            ))}
          </CollapsibleContent>
        </Collapsible>
      ) : null}
    </div>
  );
}

function PackageCard({ pkg, systemId }: { pkg: EvidencePackage; systemId: string }) {
  const download = useDownloadEvidence();
  const retry = useRetryEvidence();
  const stalled = isStalled(pkg);

  return (
    <Card>
      <CardContent className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <EvidenceStatusBadge status={pkg.status} stalled={stalled} />
            {pkg.jurisdictions.map((code) => (
              <JurisdictionBadge key={code} code={code} />
            ))}
          </div>
          <p className="text-sm text-muted-foreground">
            Requested {formatRelative(pkg.created_at)}
            {pkg.generated_at ? ` · completed ${formatDateTime(pkg.generated_at)}` : ""}
          </p>
          {pkg.checksum_sha256 ? (
            <p className="truncate font-mono text-xs text-muted-foreground">
              sha256 {pkg.checksum_sha256.slice(0, 32)}…
            </p>
          ) : null}
          {stalled ? (
            <p className="text-xs text-status-warn-foreground">
              This package stopped progressing and will not finish on its own.
            </p>
          ) : null}
          {pkg.status === "failed" && pkg.error_message ? (
            <Alert variant="destructive" className="mt-2">
              <AlertDescription className="text-xs">{pkg.error_message}</AlertDescription>
            </Alert>
          ) : null}
        </div>

        {pkg.status === "completed" ? (
          <div className="flex shrink-0 gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={download.isPending}
              onClick={() => download.mutate({ systemId, packageId: pkg.id, kind: "pdf" })}
            >
              <Download className="mr-2 h-4 w-4" />
              PDF
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={download.isPending}
              onClick={() => download.mutate({ systemId, packageId: pkg.id, kind: "json" })}
            >
              <FileJson className="mr-2 h-4 w-4" />
              JSON
            </Button>
          </div>
        ) : canRetry(pkg) ? (
          <RoleGate allow={["admin", "risk_officer"]}>
            <Button
              size="sm"
              variant="outline"
              className="shrink-0"
              disabled={retry.isPending}
              onClick={() => retry.mutate({ systemId, packageId: pkg.id })}
            >
              <RotateCcw className={cn("mr-2 h-4 w-4", retry.isPending && "animate-spin")} />
              Retry
            </Button>
          </RoleGate>
        ) : (
          <p className="shrink-0 text-sm text-muted-foreground">Generating…</p>
        )}
      </CardContent>
    </Card>
  );
}
