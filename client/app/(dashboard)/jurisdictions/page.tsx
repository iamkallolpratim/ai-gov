"use client";

import { Gavel } from "lucide-react";

import { PageHeader } from "@/components/shared/page-header";
import { EmptyState, ErrorState, TableSkeleton } from "@/components/shared/states";
import { JurisdictionBadge } from "@/components/shared/status-badges";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useJurisdictions } from "@/hooks/use-jurisdictions";

export default function JurisdictionsPage() {
  const { data, isLoading, isError, error, refetch } = useJurisdictions(false);

  return (
    <>
      <PageHeader
        title="Jurisdictions"
        description="Regulatory regimes the console evaluates. Strictness decides which regime wins when obligations conflict."
      />

      {isLoading ? (
        <TableSkeleton rows={4} columns={3} />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !data?.length ? (
        <EmptyState icon={Gavel} title="No jurisdictions configured" />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {[...data]
            .sort(
              (a, b) =>
                Number((b.overlay_config as { strictness?: number })?.strictness ?? 0) -
                Number((a.overlay_config as { strictness?: number })?.strictness ?? 0),
            )
            .map((jurisdiction) => {
              const strictness = (jurisdiction.overlay_config as { strictness?: number })
                ?.strictness;
              const triggers = (jurisdiction.overlay_config as { triggers?: string[] })?.triggers;

              return (
                <Card key={jurisdiction.id}>
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <CardTitle className="flex items-center gap-2 text-base">
                          <JurisdictionBadge code={jurisdiction.code} />
                          {jurisdiction.name}
                        </CardTitle>
                        {jurisdiction.regulation_name ? (
                          <CardDescription className="mt-1">
                            {jurisdiction.regulation_name}
                          </CardDescription>
                        ) : null}
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1">
                        {typeof strictness === "number" ? (
                          <Badge variant="secondary">Strictness {strictness}</Badge>
                        ) : null}
                        {!jurisdiction.is_active ? (
                          <Badge variant="outline">Inactive</Badge>
                        ) : null}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {jurisdiction.description ? (
                      <p className="text-sm text-muted-foreground">{jurisdiction.description}</p>
                    ) : null}

                    {jurisdiction.territories.length ? (
                      <div>
                        <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                          Territories
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {jurisdiction.territories.slice(0, 12).map((code) => (
                            <JurisdictionBadge key={code} code={code} />
                          ))}
                          {jurisdiction.territories.length > 12 ? (
                            <span className="self-center text-xs text-muted-foreground">
                              +{jurisdiction.territories.length - 12} more
                            </span>
                          ) : null}
                        </div>
                      </div>
                    ) : null}

                    {triggers?.length ? (
                      <div>
                        <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                          Applicability triggers
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {triggers.map((trigger) => (
                            <Badge key={trigger} variant="outline" className="font-mono text-xs">
                              {trigger}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </CardContent>
                </Card>
              );
            })}
        </div>
      )}
    </>
  );
}
