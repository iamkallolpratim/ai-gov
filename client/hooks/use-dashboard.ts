"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

export function useDashboardSummary() {
  return useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: () => api.dashboard.summary(),
  });
}

export function useJurisdictionDashboard() {
  return useQuery({
    queryKey: ["dashboard", "by-jurisdiction"],
    queryFn: () => api.dashboard.byJurisdiction(),
  });
}
