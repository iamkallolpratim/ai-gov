"use client";

import { SystemForm, toPayload } from "@/components/systems/system-form";
import { PageHeader } from "@/components/shared/page-header";
import { ForbiddenState } from "@/components/shared/states";
import { usePermissions } from "@/hooks/use-auth";
import { useCreateSystem } from "@/hooks/use-systems";

export default function NewSystemPage() {
  const { canWrite } = usePermissions();
  const createSystem = useCreateSystem();

  if (!canWrite) return <ForbiddenState />;

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title="Register an AI system"
        description="Describe the system once. Jurisdiction detection, risk classification and policy checks all read from this record."
      />
      <SystemForm
        mode="create"
        isSubmitting={createSystem.isPending}
        onSubmit={(values) => createSystem.mutate(toPayload(values))}
      />
    </div>
  );
}
