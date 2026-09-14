"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { toUserMessage } from "@/lib/errors";
import { systemKeys } from "@/hooks/use-systems";

export const policyCheckKeys = {
  list: (id: string, latestOnly: boolean) => ["policy-checks", id, { latestOnly }] as const,
};

export function usePolicyChecks(systemId: string | undefined, latestOnly = true) {
  return useQuery({
    queryKey: policyCheckKeys.list(systemId ?? "", latestOnly),
    queryFn: () => api.systems.policyChecks(systemId!, { latest_only: latestOnly, page_size: 100 }),
    enabled: !!systemId,
  });
}

export function useRunPolicyChecks(systemId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { jurisdictions?: string[] | null; reclassify?: boolean } = {}) =>
      api.systems.checkPolicies(systemId, input),
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: ["policy-checks", systemId] });
      queryClient.invalidateQueries({ queryKey: ["classifications", systemId] });
      queryClient.invalidateQueries({ queryKey: systemKeys.detail(systemId) });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });

      const { summary } = run;
      if (summary.total === 0) {
        toast.info("No policies applied", {
          description: "No active policy matches this system's jurisdictions and risk tier.",
        });
      } else if (summary.compliant) {
        toast.success(`All ${summary.total} checks passed`);
      } else {
        toast.warning(`${summary.failed} of ${summary.total} checks failed`, {
          description: "Open the Policy checks tab for the findings and remediation.",
        });
      }
    },
    onError: (error) => toast.error(toUserMessage(error)),
  });
}

export function usePolicies(params: { jurisdiction?: string; is_active?: boolean } = {}) {
  return useQuery({
    queryKey: ["policies", params],
    queryFn: () => api.policies.list({ ...params, page_size: 100 }),
  });
}
