"use client";

import { History } from "lucide-react";

import { EmptyState, ErrorState, TableSkeleton } from "@/components/shared/states";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { useSystemVersions } from "@/hooks/use-systems";
import { formatDateTime, humanize } from "@/lib/format";

/** Renders one `{field: [old, new]}` entry from the backend's version diff. */
function DiffRow({ field, change }: { field: string; change: unknown }) {
  if (Array.isArray(change) && change.length === 2) {
    return (
      <li className="flex flex-wrap items-baseline gap-2 text-sm">
        <span className="font-medium">{humanize(field)}</span>
        <span className="font-mono text-xs text-muted-foreground line-through">
          {formatValue(change[0])}
        </span>
        <span className="text-muted-foreground">→</span>
        <span className="font-mono text-xs">{formatValue(change[1])}</span>
      </li>
    );
  }

  // Nested diffs (system_metadata) arrive as an object of field → [old, new].
  if (change && typeof change === "object") {
    return (
      <li className="text-sm">
        <span className="font-medium">{humanize(field)}</span>
        <ul className="mt-1 space-y-1 border-l pl-4">
          {Object.entries(change as Record<string, unknown>).map(([nested, nestedChange]) => (
            <DiffRow key={nested} field={nested} change={nestedChange} />
          ))}
        </ul>
      </li>
    );
  }

  return null;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "empty";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "empty";
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
}

export function ActivityTab({ systemId }: { systemId: string }) {
  const { data, isLoading, isError, error, refetch } = useSystemVersions(systemId);

  if (isLoading) return <TableSkeleton rows={4} columns={3} />;
  if (isError) return <ErrorState error={error} onRetry={() => refetch()} />;

  const versions = data ?? [];
  if (!versions.length) {
    return <EmptyState icon={History} title="No recorded changes" />;
  }

  return (
    <div className="space-y-3">
      {versions.map((version) => {
        const entries = Object.entries(version.diff ?? {});
        return (
          <Card key={version.id}>
            <CardContent className="p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">v{version.version}</Badge>
                  <span className="text-sm font-medium">
                    {version.change_summary || "Metadata updated"}
                  </span>
                </div>
                <span className="text-xs text-muted-foreground">
                  {formatDateTime(version.created_at)}
                </span>
              </div>

              {entries.length ? (
                <ul className="mt-3 space-y-1.5 border-t pt-3">
                  {entries.map(([field, change]) => (
                    <DiffRow key={field} field={field} change={change} />
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-xs text-muted-foreground">
                  Initial version — no prior state to compare against.
                </p>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
