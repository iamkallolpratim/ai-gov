"use client";

import { LogOut, Menu, ShieldAlert } from "lucide-react";
import Link from "next/link";

import { SidebarBrand, SidebarNav } from "@/components/layout/sidebar";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useAuthMode, useCurrentUser, useLogout } from "@/hooks/use-auth";
import { ROLE_LABELS } from "@/stores/auth-store";
import { initials } from "@/lib/format";
import { useState } from "react";

export function Topbar() {
  const user = useCurrentUser();
  const mode = useAuthMode();
  const logout = useLogout();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetTrigger asChild>
          <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open navigation">
            <Menu className="h-5 w-5" />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-64 p-0">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <SidebarBrand onNavigate={() => setMobileOpen(false)} />
          <SidebarNav onNavigate={() => setMobileOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="flex-1" />

      {mode?.auth_disabled ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-flex items-center gap-1.5 rounded-md border border-status-warn-foreground/30 bg-status-warn px-2.5 py-1 text-xs font-medium text-status-warn-foreground">
              <ShieldAlert className="h-3.5 w-3.5" aria-hidden />
              Authentication disabled
            </span>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs">
            This server runs with AUTH_DISABLED. Every request has full admin rights and is
            audited as the system principal. Safe only on a trusted private network.
          </TooltipContent>
        </Tooltip>
      ) : null}

      <ThemeToggle />

      {user ? (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="gap-2 px-2">
              <Avatar className="h-7 w-7">
                <AvatarFallback className="text-xs">{initials(user.full_name)}</AvatarFallback>
              </Avatar>
              <span className="hidden text-sm font-medium sm:inline">{user.full_name}</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-64">
            <DropdownMenuLabel className="space-y-1">
              <p className="text-sm font-medium">{user.full_name}</p>
              <p className="truncate text-xs font-normal text-muted-foreground">{user.email}</p>
              <p className="text-xs font-normal text-muted-foreground">
                {ROLE_LABELS[user.role]}
                {user.is_system ? " · system principal" : ""}
              </p>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/dashboard">Dashboard</Link>
            </DropdownMenuItem>
            {mode?.auth_enabled ? (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={logout}>
                  <LogOut className="mr-2 h-4 w-4" />
                  Sign out
                </DropdownMenuItem>
              </>
            ) : null}
          </DropdownMenuContent>
        </DropdownMenu>
      ) : null}
    </header>
  );
}
