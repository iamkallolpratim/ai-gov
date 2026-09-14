"use client";

import { ShieldCheck } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { EmptyState, ErrorState, TableSkeleton } from "@/components/shared/states";
import { JurisdictionBadge, SeverityBadge } from "@/components/shared/status-badges";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { usePolicies } from "@/hooks/use-policy-checks";
import { RISK_TIER_LABELS } from "@/lib/constants";

export default function PoliciesPage() {
  const { data, isLoading, isError, error, refetch } = usePolicies();
  const [openId, setOpenId] = useState<string | null>(null);

  return (
    <>
      <PageHeader
        title="Policies"
        description="Policy-as-code rules evaluated by Open Policy Agent. Versioned, so historical checks stay meaningful."
      />

      {isLoading ? (
        <TableSkeleton rows={4} columns={3} />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !data?.items.length ? (
        <EmptyState icon={ShieldCheck} title="No policies configured" />
      ) : (
        <div className="space-y-3">
          {data.items.map((policy) => (
            <Card key={policy.id}>
              <Collapsible
                open={openId === policy.id}
                onOpenChange={(open) => setOpenId(open ? policy.id : null)}
              >
                <CollapsibleTrigger asChild>
                  <button type="button" className="w-full p-4 text-left hover:bg-muted/40">
                    <div className="flex flex-wrap items-center gap-2">
                      <JurisdictionBadge code={policy.jurisdiction_code} />
                      <span className="font-medium">{policy.name}</span>
                      <SeverityBadge severity={policy.severity} />
                      <Badge variant="outline" className="font-mono text-xs">
                        v{policy.version}
                      </Badge>
                      {!policy.is_active ? <Badge variant="secondary">Inactive</Badge> : null}
                    </div>
                    {policy.description ? (
                      <p className="mt-1.5 text-sm text-muted-foreground">{policy.description}</p>
                    ) : null}
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <code>{policy.opa_package}</code>
                      {policy.applies_to_risk_tiers.length ? (
                        <span>
                          · applies to{" "}
                          {policy.applies_to_risk_tiers
                            .map((tier) => RISK_TIER_LABELS[tier])
                            .join(", ")}
                        </span>
                      ) : (
                        <span>· applies to all risk tiers</span>
                      )}
                    </div>
                  </button>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <div className="border-t p-4">
                    {policy.remediation ? (
                      <p className="mb-3 text-sm">
                        <span className="font-medium">Default remediation: </span>
                        {policy.remediation}
                      </p>
                    ) : null}
                    {policy.rego_code ? (
                      <ScrollArea className="h-80 rounded-md border bg-muted/40">
                        <pre className="p-4 text-xs leading-relaxed">{policy.rego_code}</pre>
                      </ScrollArea>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        No Rego stored; this policy uses declarative rules only.
                      </p>
                    )}
                  </div>
                </CollapsibleContent>
              </Collapsible>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
