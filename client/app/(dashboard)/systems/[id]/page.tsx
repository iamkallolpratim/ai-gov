"use client";

import {
  ArrowLeft,
  ClipboardCheck,
  FileCheck2,
  Loader2,
  Pencil,
  Scale,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { RoleGate } from "@/components/shared/role-gate";
import { DetailSkeleton, ErrorState } from "@/components/shared/states";
import {
  JurisdictionBadge,
  RiskTierBadge,
  SystemStatusBadge,
} from "@/components/shared/status-badges";
import { GenerateEvidenceDialog } from "@/components/systems/generate-evidence-dialog";
import { ActivityTab } from "@/components/systems/tab-activity";
import { EvidenceTab } from "@/components/systems/tab-evidence";
import { JurisdictionsTab } from "@/components/systems/tab-jurisdictions";
import { OverviewTab } from "@/components/systems/tab-overview";
import { PoliciesTab } from "@/components/systems/tab-policies";
import { RiskTab } from "@/components/systems/tab-risk";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useClassifications, useRunClassification } from "@/hooks/use-classification";
import { useGenerateEvidence } from "@/hooks/use-evidence";
import { useRunPolicyChecks } from "@/hooks/use-policy-checks";
import { useDeleteSystem, useSystem } from "@/hooks/use-systems";
import { RISK_TIER_ORDER } from "@/lib/risk";
import { formatRelative } from "@/lib/format";
import type { RiskTier } from "@/types/api";

const TABS = ["overview", "jurisdictions", "risk", "policies", "evidence", "activity"] as const;
type TabValue = (typeof TABS)[number];

export default function SystemDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const systemId = params.id;

  const requestedTab = searchParams.get("tab");
  const initialTab: TabValue = TABS.includes(requestedTab as TabValue)
    ? (requestedTab as TabValue)
    : "overview";
  const [tab, setTab] = useState<TabValue>(initialTab);
  const [evidenceOpen, setEvidenceOpen] = useState(false);

  const { data: system, isLoading, isError, error, refetch } = useSystem(systemId);
  const latestClassifications = useClassifications(systemId, true);
  const classify = useRunClassification(systemId);
  const checkPolicies = useRunPolicyChecks(systemId);
  const generateEvidence = useGenerateEvidence(systemId);
  const deleteSystem = useDeleteSystem();

  if (isLoading) return <DetailSkeleton />;
  if (isError) return <ErrorState error={error} onRetry={() => refetch()} />;
  if (!system) return null;

  // The headline tier is the strictest one across every applicable jurisdiction.
  const applicable = (latestClassifications.data ?? []).filter((c) => c.is_applicable);
  const headlineTier: RiskTier | null = applicable.length
    ? applicable.reduce((worst, current) =>
        RISK_TIER_ORDER[current.risk_tier] > RISK_TIER_ORDER[worst.risk_tier] ? current : worst,
      ).risk_tier
    : null;
  const jurisdictionCodes = applicable.map((c) => c.jurisdiction_code);

  return (
    <>
      <Button variant="ghost" size="sm" asChild className="mb-3 -ml-2">
        <Link href="/systems">
          <ArrowLeft className="mr-2 h-4 w-4" />
          All systems
        </Link>
      </Button>

      <PageHeader
        title={system.name}
        description={
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <SystemStatusBadge status={system.status} />
            {headlineTier ? <RiskTierBadge tier={headlineTier} /> : null}
            {jurisdictionCodes.map((code) => (
              <JurisdictionBadge key={code} code={code} />
            ))}
            <span className="text-xs text-muted-foreground">
              Owner {system.owner?.full_name ?? "—"} · updated {formatRelative(system.updated_at)}
            </span>
          </div>
        }
        actions={
          <RoleGate allow={["admin", "risk_officer"]}>
            <Button
              variant="outline"
              onClick={() => classify.mutate({})}
              disabled={classify.isPending}
            >
              {classify.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Scale className="mr-2 h-4 w-4" />
              )}
              Classify
            </Button>
            <Button
              variant="outline"
              onClick={() => checkPolicies.mutate({})}
              disabled={checkPolicies.isPending}
            >
              {checkPolicies.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <ClipboardCheck className="mr-2 h-4 w-4" />
              )}
              Run policy checks
            </Button>
            <Button onClick={() => setEvidenceOpen(true)}>
              <FileCheck2 className="mr-2 h-4 w-4" />
              Generate evidence
            </Button>
            <Button variant="outline" size="icon" asChild aria-label="Edit system">
              <Link href={`/systems/${system.id}/edit`}>
                <Pencil className="h-4 w-4" />
              </Link>
            </Button>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="outline" size="icon" aria-label="Archive system">
                  <Trash2 className="h-4 w-4" />
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Archive {system.name}?</AlertDialogTitle>
                  <AlertDialogDescription>
                    The system is soft-deleted and hidden from the inventory. Its classifications,
                    policy checks and audit history are retained, and it can be restored.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={() => deleteSystem.mutate(system.id)}>
                    Archive
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </RoleGate>
        }
      />

      <Tabs
        value={tab}
        onValueChange={(value) => {
          setTab(value as TabValue);
          // Keep the tab in the URL so a link to a failing check lands in the right place.
          router.replace(`/systems/${systemId}?tab=${value}`, { scroll: false });
        }}
      >
        <TabsList className="mb-6 flex h-auto w-full flex-wrap justify-start gap-1">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="jurisdictions">Jurisdictions</TabsTrigger>
          <TabsTrigger value="risk">Risk</TabsTrigger>
          <TabsTrigger value="policies">Policy checks</TabsTrigger>
          <TabsTrigger value="evidence">Evidence</TabsTrigger>
          <TabsTrigger value="activity">Activity</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <OverviewTab system={system} />
        </TabsContent>
        <TabsContent value="jurisdictions">
          <JurisdictionsTab systemId={systemId} />
        </TabsContent>
        <TabsContent value="risk">
          <RiskTab systemId={systemId} onRunClassification={() => classify.mutate({})} />
        </TabsContent>
        <TabsContent value="policies">
          <PoliciesTab systemId={systemId} onRunChecks={() => checkPolicies.mutate({})} />
        </TabsContent>
        <TabsContent value="evidence">
          <EvidenceTab systemId={systemId} onGenerate={() => setEvidenceOpen(true)} />
        </TabsContent>
        <TabsContent value="activity">
          <ActivityTab systemId={systemId} />
        </TabsContent>
      </Tabs>

      <GenerateEvidenceDialog
        open={evidenceOpen}
        onOpenChange={setEvidenceOpen}
        isPending={generateEvidence.isPending}
        onGenerate={(input) => {
          generateEvidence.mutate(input, {
            onSuccess: () => {
              setEvidenceOpen(false);
              setTab("evidence");
            },
          });
        }}
      />
    </>
  );
}
