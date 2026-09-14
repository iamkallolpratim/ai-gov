"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { toUserMessage } from "@/lib/errors";
import { RISK_TIER_LABELS } from "@/lib/constants";
import { systemKeys } from "@/hooks/use-systems";

export const classificationKeys = {
  history: (id: string) => ["classifications", id] as const,
  latest: (id: string) => ["classifications", id, "latest"] as const,
  detection: (id: string) => ["jurisdictions", "detect", id] as const,
};

export function useClassifications(systemId: string | undefined, latestOnly = false) {
  return useQuery({
    queryKey: latestOnly
      ? classificationKeys.latest(systemId ?? "")
      : classificationKeys.history(systemId ?? ""),
    queryFn: () => api.systems.classifications(systemId!, { latest_only: latestOnly }),
    enabled: !!systemId,
  });
}

/** Dry-run detection: shows applicable jurisdictions without writing a classification. */
export function useJurisdictionDetection(systemId: string | undefined) {
  return useQuery({
    queryKey: classificationKeys.detection(systemId ?? ""),
    queryFn: () => api.jurisdictions.detect(systemId!),
    enabled: !!systemId,
  });
}

export function useRunClassification(systemId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { jurisdictions?: string[] | null; force?: boolean } = {}) =>
      api.systems.classify(systemId, input),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["classifications", systemId] });
      queryClient.invalidateQueries({ queryKey: classificationKeys.detection(systemId) });
      queryClient.invalidateQueries({ queryKey: systemKeys.detail(systemId) });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });

      const codes = result.jurisdictions.applicable_jurisdictions ?? [];
      toast.success("Classification complete", {
        description: codes.length
          ? `${codes.join(", ")} · most restrictive: ${RISK_TIER_LABELS[result.most_restrictive_tier]}`
          : "No jurisdiction was found applicable to this system.",
      });
    },
    onError: (error) => toast.error(toUserMessage(error)),
  });
}
