import {
  FileCheck2,
  Gavel,
  LayoutDashboard,
  ScrollText,
  Server,
  ShieldCheck,
  Users,
} from "lucide-react";

import type { UserRole } from "@/types/api";

export interface NavItem {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  /** Omitted means every signed-in role may see it. */
  roles?: UserRole[];
  section: "Compliance" | "Configuration" | "Administration";
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, section: "Compliance" },
  { href: "/systems", label: "AI systems", icon: Server, section: "Compliance" },
  { href: "/evidence", label: "Evidence", icon: FileCheck2, section: "Compliance" },
  { href: "/policies", label: "Policies", icon: ShieldCheck, section: "Configuration" },
  { href: "/jurisdictions", label: "Jurisdictions", icon: Gavel, section: "Configuration" },
  { href: "/audit-logs", label: "Audit logs", icon: ScrollText, roles: ["admin"], section: "Administration" },
  { href: "/users", label: "Users", icon: Users, roles: ["admin"], section: "Administration" },
];

export const NAV_SECTIONS = ["Compliance", "Configuration", "Administration"] as const;
