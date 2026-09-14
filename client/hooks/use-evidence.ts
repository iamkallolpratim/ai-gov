"use client";

import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { toUserMessage } from "@/lib/errors";
import { useAuthStore } from "@/stores/auth-store";
import type { EvidenceGenerateInput, EvidencePackage } from "@/types/api";

export const evidenceKeys = {
  forSystem: (id: string) => ["evidence", "system", id] as const,
};

/** Mirrors EVIDENCE_STALE_AFTER_SECONDS in the backend settings. */
export const EVIDENCE_STALE_AFTER_MS = 15 * 60 * 1000;

export function isInFlight(pkg: EvidencePackage) {
  return pkg.status === "pending" || pkg.status === "running";
}

/**
 * Still pending/running long after any real job would have finished. The backend expires
 * these on a schedule; the client also recognises them itself so a stranded row stops the
 * polling and offers Retry even when that schedule is not running.
 */
export function isStalled(pkg: EvidencePackage, now = Date.now()) {
  // From the last activity, not the original request: a package retried seconds ago
  // must count as in flight even if it was first requested weeks earlier.
  return isInFlight(pkg) && now - Date.parse(pkg.updated_at ?? pkg.created_at) > EVIDENCE_STALE_AFTER_MS;
}

export function canRetry(pkg: EvidencePackage, now = Date.now()) {
  return pkg.status === "failed" || isStalled(pkg, now);
}

/** Poll only for packages that can still genuinely complete. */
function hasPending(packages: EvidencePackage[] | undefined) {
  const now = Date.now();
  return !!packages?.some((p) => isInFlight(p) && !isStalled(p, now));
}

/**
 * Generation runs in a Celery worker, so a fresh package arrives `pending`. Poll while
 * anything is in flight and stop as soon as everything has settled — an always-on
 * interval would hammer the API for a page that is usually static.
 */
export function useSystemEvidence(systemId: string | undefined) {
  return useQuery({
    queryKey: evidenceKeys.forSystem(systemId ?? ""),
    queryFn: () => api.systems.evidence(systemId!, { page_size: 50 }),
    enabled: !!systemId,
    refetchInterval: (query) => (hasPending(query.state.data?.items) ? 3000 : false),
    // Generation runs in a worker and can finish while the user is in another tab.
    // Without this, TanStack pauses the interval and the row is stuck on "Pending"
    // until something else forces a refetch.
    refetchIntervalInBackground: true,
  });
}

export function useGenerateEvidence(systemId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: EvidenceGenerateInput = {}) => api.systems.generateEvidence(systemId, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: evidenceKeys.forSystem(systemId) });
      queryClient.invalidateQueries({ queryKey: ["evidence", "all"] });
      toast.success("Evidence package queued", {
        description: "It is being generated in the background and will appear when ready.",
      });
    },
    onError: (error) => toast.error(toUserMessage(error)),
  });
}

/** Re-queues a failed or stalled package, keeping one record per request. */
export function useRetryEvidence() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ systemId, packageId }: { systemId: string; packageId: string }) =>
      api.systems.retryEvidence(systemId, packageId),
    onSuccess: (_result, { systemId }) => {
      queryClient.invalidateQueries({ queryKey: evidenceKeys.forSystem(systemId) });
      toast.success("Retrying evidence package", {
        description: "It has been queued again and will update when ready.",
      });
    },
    onError: (error) => toast.error(toUserMessage(error)),
  });
}

/**
 * Portfolio-wide evidence view. The API only exposes packages per system, so this fans
 * out across the systems the user can see and flattens the result.
 */
export function useAllEvidence(systemIds: string[]) {
  const results = useQueries({
    queries: systemIds.map((id) => ({
      queryKey: evidenceKeys.forSystem(id),
      queryFn: () => api.systems.evidence(id, { page_size: 50 }),
      refetchInterval: (query: { state: { data?: { items: EvidencePackage[] } } }) =>
        hasPending(query.state.data?.items) ? 3000 : (false as const),
      refetchIntervalInBackground: true,
    })),
  });

  const packages = results.flatMap((r) => r.data?.items ?? []);
  packages.sort((a, b) => (a.created_at < b.created_at ? 1 : -1));

  return {
    packages,
    isLoading: results.some((r) => r.isLoading),
    isError: results.some((r) => r.isError),
    refetch: () => results.forEach((r) => r.refetch()),
  };
}

/** Downloads stream through a Next route handler; see app/api/evidence/… for why. */
export function evidenceDownloadUrl(
  systemId: string,
  packageId: string,
  kind: "pdf" | "json" = "pdf",
) {
  return `/api/evidence/${systemId}/${packageId}?kind=${kind}`;
}

/**
 * Downloads a package through the proxy route.
 *
 * A plain link cannot carry the bearer token — it lives in localStorage, not a cookie —
 * so the request is made with fetch and the response saved as a blob.
 */
export function useDownloadEvidence() {
  return useMutation({
    mutationFn: async ({
      systemId,
      packageId,
      kind,
    }: {
      systemId: string;
      packageId: string;
      kind: "pdf" | "json";
    }) => {
      const { accessToken } = useAuthStore.getState();
      const response = await fetch(evidenceDownloadUrl(systemId, packageId, kind), {
        headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
      });

      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { error?: string } | null;
        throw new Error(body?.error ?? "The download failed.");
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `evidence-${packageId.slice(0, 8)}.${kind}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      // Revoked on the next tick so the click has already started the save.
      setTimeout(() => URL.revokeObjectURL(url), 0);
    },
    onError: (error) => toast.error(toUserMessage(error)),
  });
}
