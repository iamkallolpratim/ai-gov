"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

export function useJurisdictions(activeOnly = true) {
  return useQuery({
    queryKey: ["jurisdictions", { activeOnly }],
    queryFn: () => api.jurisdictions.list(activeOnly ? true : undefined),
    staleTime: 5 * 60_000, // configuration data; rarely changes during a session
  });
}
