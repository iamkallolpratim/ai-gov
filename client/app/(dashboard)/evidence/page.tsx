"use client";

import { Download, FileCheck2, FileJson, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { RoleGate } from "@/components/shared/role-gate";
import { EmptyState, ErrorState, TableSkeleton } from "@/components/shared/states";
import { EvidenceStatusBadge, JurisdictionBadge } from "@/components/shared/status-badges";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  canRetry,
  isStalled,
  useAllEvidence,
  useDownloadEvidence,
  useRetryEvidence,
} from "@/hooks/use-evidence";
import { useSystems } from "@/hooks/use-systems";
import { formatRelative } from "@/lib/format";
import { EVIDENCE_STATUSES } from "@/types/api";

const ALL = "__all__";

export default function EvidencePage() {
  const [status, setStatus] = useState<string>(ALL);
  const systemsQuery = useSystems({ page_size: 100 });
  const systems = useMemo(() => systemsQuery.data?.items ?? [], [systemsQuery.data]);
  const systemIds = useMemo(() => systems.map((s) => s.id), [systems]);
  const systemNames = useMemo(
    () => Object.fromEntries(systems.map((s) => [s.id, s.name])),
    [systems],
  );

  const evidence = useAllEvidence(systemIds);
  const download = useDownloadEvidence();
  const retry = useRetryEvidence();

  const packages = evidence.packages.filter((pkg) => status === ALL || pkg.status === status);

  return (
    <>
      <PageHeader
        title="Evidence packages"
        description="Audit-ready PDF reports and JSON manifests generated across the portfolio."
        actions={
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="w-[180px]" aria-label="Filter by status">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All statuses</SelectItem>
              {EVIDENCE_STATUSES.map((value) => (
                <SelectItem key={value} value={value}>
                  {value[0].toUpperCase() + value.slice(1)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        }
      />

      <Card>
        <CardContent className="p-0">
          {systemsQuery.isLoading || evidence.isLoading ? (
            <TableSkeleton rows={5} columns={5} />
          ) : systemsQuery.isError ? (
            <ErrorState error={systemsQuery.error} onRetry={() => systemsQuery.refetch()} />
          ) : packages.length === 0 ? (
            <EmptyState
              icon={FileCheck2}
              title={status === ALL ? "No evidence packages yet" : "No packages with this status"}
              description={
                status === ALL
                  ? "Open a system and generate a package to bundle its compliance record into a signed report."
                  : "Try a different status filter."
              }
              action={
                status === ALL && systems.length > 0
                  ? { label: "Go to systems", href: "/systems" }
                  : undefined
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>System</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="hidden md:table-cell">Jurisdictions</TableHead>
                    <TableHead className="hidden sm:table-cell">Generated</TableHead>
                    <TableHead className="text-right">Download</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {packages.map((pkg) => (
                    <TableRow key={pkg.id}>
                      <TableCell className="font-medium">
                        <Link
                          href={`/systems/${pkg.ai_system_id}?tab=evidence`}
                          className="hover:underline"
                        >
                          {systemNames[pkg.ai_system_id] ?? "Unknown system"}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <EvidenceStatusBadge status={pkg.status} stalled={isStalled(pkg)} />
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        <div className="flex flex-wrap gap-1">
                          {pkg.jurisdictions.map((code) => (
                            <JurisdictionBadge key={code} code={code} />
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className="hidden sm:table-cell text-sm text-muted-foreground">
                        {formatRelative(pkg.generated_at ?? pkg.created_at)}
                      </TableCell>
                      <TableCell className="text-right">
                        {pkg.status === "completed" ? (
                          <div className="flex justify-end gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={download.isPending}
                              onClick={() =>
                                download.mutate({
                                  systemId: pkg.ai_system_id,
                                  packageId: pkg.id,
                                  kind: "pdf",
                                })
                              }
                            >
                              <Download className="mr-1.5 h-3.5 w-3.5" />
                              PDF
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={download.isPending}
                              onClick={() =>
                                download.mutate({
                                  systemId: pkg.ai_system_id,
                                  packageId: pkg.id,
                                  kind: "json",
                                })
                              }
                            >
                              <FileJson className="mr-1.5 h-3.5 w-3.5" />
                              JSON
                            </Button>
                          </div>
                        ) : canRetry(pkg) ? (
                          <RoleGate
                            allow={["admin", "risk_officer"]}
                            fallback={<span className="text-sm text-muted-foreground">—</span>}
                          >
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={retry.isPending}
                              onClick={() =>
                                retry.mutate({ systemId: pkg.ai_system_id, packageId: pkg.id })
                              }
                            >
                              <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                              Retry
                            </Button>
                          </RoleGate>
                        ) : (
                          <span className="text-sm text-muted-foreground">—</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </>
  );
}
