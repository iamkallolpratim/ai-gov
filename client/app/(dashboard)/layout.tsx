"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { ErrorState } from "@/components/shared/states";
import { useAuthBootstrap } from "@/hooks/use-auth";
import { NetworkError } from "@/lib/errors";
import { useAuthStore } from "@/stores/auth-store";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isLoading, isApiUnreachable, retry } = useAuthBootstrap();
  const mode = useAuthStore((s) => s.mode);
  const user = useAuthStore((s) => s.user);

  // Redirect only once the mode is known: with AUTH_DISABLED there is no login page to
  // send anyone to, and bouncing on a slow /auth/me would flash the login screen.
  const mustSignIn = !isLoading && !!mode?.auth_enabled && !user;
  useEffect(() => {
    if (mustSignIn) router.replace("/login");
  }, [mustSignIn, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" aria-label="Loading" />
      </div>
    );
  }

  if (isApiUnreachable) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <ErrorState
          title="The API is unreachable"
          error={new NetworkError()}
          onRetry={() => retry()}
        />
      </div>
    );
  }

  if (mustSignIn) return null;

  return (
    <div className="flex min-h-screen bg-muted/30">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto w-full max-w-7xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
