"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { AuditLogParams } from "@/types/api";

export function useAuditLogs(params: AuditLogParams = {}, enabled = true) {
  return useQuery({
    queryKey: ["audit-logs", params],
    queryFn: () => api.auditLogs.list(params),
    enabled,
    placeholderData: (previous) => previous,
  });
}
