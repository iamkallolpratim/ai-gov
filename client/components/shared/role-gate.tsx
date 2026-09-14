"use client";

import { usePermissions } from "@/hooks/use-auth";
import type { UserRole } from "@/types/api";

/**
 * Hides actions the current role cannot perform. Presentation only — the backend
 * enforces the same matrix and would answer 403 regardless.
 */
export function RoleGate({
  allow,
  children,
  fallback = null,
}: {
  allow: UserRole[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}) {
  const { can } = usePermissions();
  return <>{can(allow) ? children : fallback}</>;
}
