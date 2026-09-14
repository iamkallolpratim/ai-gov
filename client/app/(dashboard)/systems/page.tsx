"use client";

import { Plus, Search, Server, X } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { RoleGate } from "@/components/shared/role-gate";
import { EmptyState, ErrorState, TableSkeleton } from "@/components/shared/states";
import { SystemStatusBadge } from "@/components/shared/status-badges";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
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
import { useDebounced } from "@/hooks/use-debounced";
import { useJurisdictions } from "@/hooks/use-jurisdictions";
import { useSystems } from "@/hooks/use-systems";
import { RISK_TIER_LABELS, STATUS_LABELS } from "@/lib/constants";
import { formatRelative, humanize } from "@/lib/format";
import { RISK_TIERS, SYSTEM_STATUSES, type RiskTier, type SystemStatus } from "@/types/api";

const ALL = "__all__";
const PAGE_SIZE = 20;

export default function SystemsPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<string>(ALL);
  const [riskTier, setRiskTier] = useState<string>(ALL);
  const [jurisdiction, setJurisdiction] = useState<string>(ALL);
  const [page, setPage] = useState(1);

  const debouncedSearch = useDebounced(search, 300);
  const jurisdictionsQuery = useJurisdictions();

  const params = useMemo(
    () => ({
      q: debouncedSearch || undefined,
      status: status === ALL ? undefined : [status as SystemStatus],
      risk_tier: riskTier === ALL ? undefined : [riskTier as RiskTier],
      jurisdiction: jurisdiction === ALL ? undefined : [jurisdiction],
      page,
      page_size: PAGE_SIZE,
      sort_by: "updated_at",
      sort_dir: "desc" as const,
    }),
    [debouncedSearch, status, riskTier, jurisdiction, page],
  );

  const { data, isLoading, isError, error, refetch, isPlaceholderData } = useSystems(params);
  const filtersActive = !!debouncedSearch || status !== ALL || riskTier !== ALL || jurisdiction !== ALL;

  function resetFilters() {
    setSearch("");
    setStatus(ALL);
    setRiskTier(ALL);
    setJurisdiction(ALL);
    setPage(1);
  }

  return (
    <>
      <PageHeader
        title="AI systems"
        description="Every AI system in the inventory, with its status and ownership."
        actions={
          <RoleGate allow={["admin", "risk_officer"]}>
            <Button asChild>
              <Link href="/systems/new">
                <Plus className="mr-2 h-4 w-4" />
                Add system
              </Link>
            </Button>
          </RoleGate>
        }
      />

      <Card>
        <CardContent className="space-y-4 p-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value);
                  setPage(1);
                }}
                placeholder="Search by name, description or purpose…"
                className="pl-9"
                aria-label="Search AI systems"
              />
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:flex">
              <Select
                value={status}
                onValueChange={(value) => {
                  setStatus(value);
                  setPage(1);
                }}
              >
                <SelectTrigger className="lg:w-[150px]" aria-label="Filter by status">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>All statuses</SelectItem>
                  {SYSTEM_STATUSES.map((value) => (
                    <SelectItem key={value} value={value}>
                      {STATUS_LABELS[value]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select
                value={riskTier}
                onValueChange={(value) => {
                  setRiskTier(value);
                  setPage(1);
                }}
              >
                <SelectTrigger className="lg:w-[170px]" aria-label="Filter by risk tier">
                  <SelectValue placeholder="Risk tier" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>All risk tiers</SelectItem>
                  {RISK_TIERS.map((value) => (
                    <SelectItem key={value} value={value}>
                      {RISK_TIER_LABELS[value]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select
                value={jurisdiction}
                onValueChange={(value) => {
                  setJurisdiction(value);
                  setPage(1);
                }}
              >
                <SelectTrigger className="lg:w-[170px]" aria-label="Filter by jurisdiction">
                  <SelectValue placeholder="Jurisdiction" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>All jurisdictions</SelectItem>
                  {(jurisdictionsQuery.data ?? []).map((item) => (
                    <SelectItem key={item.code} value={item.code}>
                      {item.code} · {item.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {filtersActive ? (
                <Button variant="ghost" onClick={resetFilters} className="lg:w-auto">
                  <X className="mr-2 h-4 w-4" />
                  Clear
                </Button>
              ) : null}
            </div>
          </div>

          {isLoading ? (
            <TableSkeleton rows={6} columns={5} />
          ) : isError ? (
            <ErrorState error={error} onRetry={() => refetch()} />
          ) : !data || data.items.length === 0 ? (
            filtersActive ? (
              <EmptyState
                icon={Search}
                title="No systems match these filters"
                description="Try a broader search or clear the filters."
                action={{ label: "Clear filters", onClick: resetFilters }}
              />
            ) : (
              <EmptyState
                icon={Server}
                title="No AI systems registered yet"
                description="Register your first system to detect which jurisdictions apply and start assessing risk."
                action={{ label: "Add system", href: "/systems/new" }}
              />
            )
          ) : (
            <>
              <div className="overflow-x-auto rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="min-w-[220px]">Name</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="hidden md:table-cell">Use case</TableHead>
                      <TableHead className="hidden lg:table-cell">Owner</TableHead>
                      <TableHead className="hidden sm:table-cell">Updated</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody className={isPlaceholderData ? "opacity-60" : undefined}>
                    {data.items.map((system) => (
                      <TableRow key={system.id} className="cursor-pointer">
                        <TableCell className="font-medium">
                          <Link href={`/systems/${system.id}`} className="hover:underline">
                            {system.name}
                          </Link>
                          {system.description ? (
                            <p className="mt-0.5 line-clamp-1 text-xs font-normal text-muted-foreground">
                              {system.description}
                            </p>
                          ) : null}
                        </TableCell>
                        <TableCell>
                          <SystemStatusBadge status={system.status} />
                        </TableCell>
                        <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                          {humanize(system.system_metadata?.use_case)}
                        </TableCell>
                        <TableCell className="hidden lg:table-cell text-sm text-muted-foreground">
                          {system.owner?.full_name ?? "—"}
                        </TableCell>
                        <TableCell className="hidden sm:table-cell text-sm text-muted-foreground">
                          {formatRelative(system.updated_at)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              <div className="flex items-center justify-between gap-4 pt-1">
                <p className="text-sm text-muted-foreground">
                  Showing {(data.meta.page - 1) * data.meta.page_size + 1}–
                  {Math.min(data.meta.page * data.meta.page_size, data.meta.total)} of{" "}
                  {data.meta.total}
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={data.meta.page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={data.meta.page >= data.meta.pages}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </>
  );
}
