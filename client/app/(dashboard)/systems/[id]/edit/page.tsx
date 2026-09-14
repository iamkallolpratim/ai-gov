"use client";

import { useParams } from "next/navigation";

import { PageHeader } from "@/components/shared/page-header";
import { DetailSkeleton, ErrorState, ForbiddenState } from "@/components/shared/states";
import { SystemForm, toPayload } from "@/components/systems/system-form";
import { usePermissions } from "@/hooks/use-auth";
import { useSystem, useUpdateSystem } from "@/hooks/use-systems";

export default function EditSystemPage() {
  const params = useParams<{ id: string }>();
  const systemId = params.id;
  const { canWrite } = usePermissions();
  const { data: system, isLoading, isError, error, refetch } = useSystem(systemId);
  const updateSystem = useUpdateSystem(systemId);

  if (!canWrite) return <ForbiddenState />;
  if (isLoading) return <DetailSkeleton />;
  if (isError) return <ErrorState error={error} onRetry={() => refetch()} />;
  if (!system) return null;

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title={`Edit ${system.name}`}
        description="Saving creates a new immutable metadata version. Re-run classification afterwards so assessments reflect the change."
      />
      <SystemForm
        mode="edit"
        system={system}
        isSubmitting={updateSystem.isPending}
        onSubmit={(values) => updateSystem.mutate(toPayload(values))}
      />
    </div>
  );
}
