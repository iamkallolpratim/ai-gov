"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldCheck } from "lucide-react";

import { NAV_ITEMS, NAV_SECTIONS } from "@/components/layout/nav-items";
import { usePermissions } from "@/hooks/use-auth";
import { cn } from "@/lib/utils";

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { can } = usePermissions();

  return (
    <nav className="flex flex-1 flex-col gap-6 px-3 py-4">
      {NAV_SECTIONS.map((section) => {
        const items = NAV_ITEMS.filter(
          (item) => item.section === section && (!item.roles || can(item.roles)),
        );
        if (!items.length) return null;

        return (
          <div key={section}>
            <p className="px-3 pb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
              {section}
            </p>
            <ul className="space-y-1">
              {items.map((item) => {
                // `/systems` must not stay highlighted while on `/systems/new`'s sibling
                // routes only by prefix — but nested detail pages should keep it lit.
                const active =
                  pathname === item.href || pathname.startsWith(`${item.href}/`);
                const Icon = item.icon;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                        active
                          ? "bg-primary text-primary-foreground"
                          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0" aria-hidden />
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}

export function SidebarBrand({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <Link
      href="/dashboard"
      onClick={onNavigate}
      className="flex items-center gap-2.5 px-5 py-4 text-sm font-semibold"
    >
      <span className="rounded-md bg-primary p-1.5 text-primary-foreground">
        <ShieldCheck className="h-4 w-4" aria-hidden />
      </span>
      <span className="leading-tight">
        AI Governance
        <span className="block text-xs font-normal text-muted-foreground">Console</span>
      </span>
    </Link>
  );
}

export function Sidebar() {
  return (
    <aside className="hidden w-64 shrink-0 border-r bg-card lg:flex lg:flex-col">
      <SidebarBrand />
      <SidebarNav />
      <p className="px-5 py-4 text-xs text-muted-foreground">
        Not legal advice. Findings cite their source for review.
      </p>
    </aside>
  );
}
