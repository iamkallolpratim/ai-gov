"use client";

import { ChevronDown, ScrollText, ShieldAlert } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { EmptyState, ErrorState, ForbiddenState, TableSkeleton } from "@/components/shared/states";
import { Badge } from "@/components/ui/badge";
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
import { usePermissions } from "@/hooks/use-auth";
import { useAuditLogs } from "@/hooks/use-audit-logs";
import { useDebounced } from "@/hooks/use-debounced";
import { formatDateTime, humanize } from "@/lib/format";
import { cn } from "@/lib/utils";
import { AUDIT_ACTIONS, type ActorType, type AuditAction } from "@/types/api";

const ALL = "__all__";
const PAGE_SIZE = 25;
const RESOURCE_TYPES = ["ai_system", "policy", "user", "evidence_package"];

export default function AuditLogsPage() {
  const { isAdmin } = usePermissions();
  const [action, setAction] = useState<string>(ALL);
  const [resourceType, setResourceType] = useState<string>(ALL);
  const [actorType, setActorType] = useState<string>(ALL);
  const [requestId, setRequestId] = useState("");
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<string | null>(null);

  const debouncedRequestId = useDebounced(requestId, 300);

  const { data, isLoading, isError, error, refetch } = useAuditLogs(
    {
      action: action === ALL ? undefined : (action as AuditAction),
      resource_type: resourceType === ALL ? undefined : resourceType,
      actor_type: actorType === ALL ? undefined : (actorType as ActorType),
      request_id: debouncedRequestId || undefined,
      page,
      page_size: PAGE_SIZE,
    },
    isAdmin,
  );

  if (!isAdmin) return <ForbiddenState />;

  return (
    <>
      <PageHeader
        title="Audit logs"
        description="Append-only record of every mutating action. Enforced by database triggers — entries cannot be edited or deleted."
      />

      <Card>
        <CardContent className="space-y-4 p-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Select value={action} onValueChange={(v) => { setAction(v); setPage(1); }}>
              <SelectTrigger aria-label="Filter by action">
                <SelectValue placeholder="Action" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All actions</SelectItem>
                {AUDIT_ACTIONS.map((value) => (
                  <SelectItem key={value} value={value}>
                    {humanize(value)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={resourceType} onValueChange={(v) => { setResourceType(v); setPage(1); }}>
              <SelectTrigger aria-label="Filter by resource">
                <SelectValue placeholder="Resource" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All resources</SelectItem>
                {RESOURCE_TYPES.map((value) => (
                  <SelectItem key={value} value={value}>
                    {humanize(value)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={actorType} onValueChange={(v) => { setActorType(v); setPage(1); }}>
              <SelectTrigger aria-label="Filter by actor type">
                <SelectValue placeholder="Actor" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All actors</SelectItem>
                <SelectItem value="user">Authenticated user</SelectItem>
                <SelectItem value="system">System (auth disabled)</SelectItem>
              </SelectContent>
            </Select>

            <Input
              value={requestId}
              onChange={(event) => { setRequestId(event.target.value); setPage(1); }}
              placeholder="Filter by request ID…"
              aria-label="Filter by request ID"
            />
          </div>

          {isLoading ? (
            <TableSkeleton rows={8} columns={5} />
          ) : isError ? (
            <ErrorState error={error} onRetry={() => refetch()} />
          ) : !data || data.items.length === 0 ? (
            <EmptyState icon={ScrollText} title="No audit entries match these filters" />
          ) : (
            <>
              <div className="overflow-x-auto rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[180px]">When</TableHead>
                      <TableHead>Action</TableHead>
                      <TableHead>Resource</TableHead>
                      <TableHead>Actor</TableHead>
                      <TableHead className="w-10" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.items.map((log) => {
                      const isOpen = expanded === log.id;
                      const hasDetail =
                        Object.keys(log.old_values).length > 0 ||
                        Object.keys(log.new_values).length > 0 ||
                        Object.keys(log.context).length > 0;

                      return (
                        <>
                          <TableRow
                            key={log.id}
                            className={cn(hasDetail && "cursor-pointer")}
                            onClick={() => hasDetail && setExpanded(isOpen ? null : log.id)}
                          >
                            <TableCell className="text-sm text-muted-foreground">
                              {formatDateTime(log.created_at)}
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant={
                                  log.action === "delete" || log.action === "login_failed"
                                    ? "destructive"
                                    : "secondary"
                                }
                              >
                                {humanize(log.action)}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-sm">
                              <span>{humanize(log.resource_type)}</span>
                              {log.resource_id ? (
                                <code className="ml-2 text-xs text-muted-foreground">
                                  {log.resource_id.slice(0, 8)}
                                </code>
                              ) : null}
                            </TableCell>
                            <TableCell className="text-sm">
                              {log.actor_type === "system" ? (
                                <span className="inline-flex items-center gap-1.5 text-status-warn-foreground">
                                  <ShieldAlert className="h-3.5 w-3.5" />
                                  system
                                </span>
                              ) : (
                                <span className="text-muted-foreground">
                                  {log.actor_email ?? log.actor_label}
                                </span>
                              )}
                            </TableCell>
                            <TableCell>
                              {hasDetail ? (
                                <ChevronDown
                                  className={cn(
                                    "h-4 w-4 text-muted-foreground transition-transform",
                                    isOpen && "rotate-180",
                                  )}
                                />
                              ) : null}
                            </TableCell>
                          </TableRow>

                          {isOpen ? (
                            <TableRow key={`${log.id}-detail`} className="bg-muted/40 hover:bg-muted/40">
                              <TableCell colSpan={5} className="p-4">
                                <dl className="grid gap-4 text-sm md:grid-cols-2">
                                  {Object.keys(log.old_values).length ? (
                                    <div>
                                      <dt className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                                        Before
                                      </dt>
                                      <dd>
                                        <pre className="overflow-x-auto rounded-md bg-background p-3 text-xs">
                                          {JSON.stringify(log.old_values, null, 2)}
                                        </pre>
                                      </dd>
                                    </div>
                                  ) : null}
                                  {Object.keys(log.new_values).length ? (
                                    <div>
                                      <dt className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                                        After
                                      </dt>
                                      <dd>
                                        <pre className="overflow-x-auto rounded-md bg-background p-3 text-xs">
                                          {JSON.stringify(log.new_values, null, 2)}
                                        </pre>
                                      </dd>
                                    </div>
                                  ) : null}
                                  <div className="md:col-span-2 grid gap-2 sm:grid-cols-3">
                                    <div>
                                      <dt className="text-xs uppercase text-muted-foreground">Request ID</dt>
                                      <dd className="font-mono text-xs">{log.request_id ?? "—"}</dd>
                                    </div>
                                    <div>
                                      <dt className="text-xs uppercase text-muted-foreground">IP address</dt>
                                      <dd className="font-mono text-xs">{log.ip_address ?? "—"}</dd>
                                    </div>
                                    <div>
                                      <dt className="text-xs uppercase text-muted-foreground">User agent</dt>
                                      <dd className="truncate text-xs">{log.user_agent ?? "—"}</dd>
                                    </div>
                                  </div>
                                </dl>
                              </TableCell>
                            </TableRow>
                          ) : null}
                        </>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>

              <div className="flex items-center justify-between gap-4">
                <p className="text-sm text-muted-foreground">
                  Page {data.meta.page} of {data.meta.pages} · {data.meta.total} entries
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
