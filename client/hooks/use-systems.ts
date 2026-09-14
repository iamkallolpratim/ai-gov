"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { toUserMessage } from "@/lib/errors";
import type { AISystemCreateInput, AISystemUpdateInput, SystemListParams } from "@/types/api";

export const systemKeys = {
  all: ["systems"] as const,
  list: (params: SystemListParams) => ["systems", "list", params] as const,
  detail: (id: string) => ["systems", "detail", id] as const,
  versions: (id: string) => ["systems", "versions", id] as const,
};

export function useSystems(params: SystemListParams = {}) {
  return useQuery({
    queryKey: systemKeys.list(params),
    queryFn: () => api.systems.list(params),
    placeholderData: (previous) => previous, // keeps the table stable while filtering
  });
}

export function useSystem(id: string | undefined) {
  return useQuery({
    queryKey: systemKeys.detail(id ?? ""),
    queryFn: () => api.systems.get(id!),
    enabled: !!id,
  });
}

export function useSystemVersions(id: string | undefined) {
  return useQuery({
    queryKey: systemKeys.versions(id ?? ""),
    queryFn: () => api.systems.versions(id!),
    enabled: !!id,
  });
}

export function useCreateSystem() {
  const queryClient = useQueryClient();
  const router = useRouter();
  return useMutation({
    mutationFn: (input: AISystemCreateInput) => api.systems.create(input),
    onSuccess: (system) => {
      queryClient.invalidateQueries({ queryKey: systemKeys.all });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success(`${system.name} registered`, {
        description: "Run a classification to see which jurisdictions apply.",
      });
      router.push(`/systems/${system.id}`);
    },
    onError: (error) => toast.error(toUserMessage(error)),
  });
}

export function useUpdateSystem(id: string) {
  const queryClient = useQueryClient();
  const router = useRouter();
  return useMutation({
    mutationFn: (input: AISystemUpdateInput) => api.systems.update(id, input),
    onSuccess: (system) => {
      queryClient.invalidateQueries({ queryKey: systemKeys.all });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success("Changes saved", {
        description: `Metadata version ${system.metadata_version}. Re-run classification to reassess.`,
      });
      router.push(`/systems/${system.id}`);
    },
    onError: (error) => toast.error(toUserMessage(error)),
  });
}

export function useDeleteSystem() {
  const queryClient = useQueryClient();
  const router = useRouter();
  return useMutation({
    mutationFn: (id: string) => api.systems.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: systemKeys.all });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success("System archived", { description: "Its history is retained and it can be restored." });
      router.push("/systems");
    },
    onError: (error) => toast.error(toUserMessage(error)),
  });
}
