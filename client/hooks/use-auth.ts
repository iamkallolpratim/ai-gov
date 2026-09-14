"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { toUserMessage } from "@/lib/errors";
import { hasRole, useAuthStore, WRITE_ROLES } from "@/stores/auth-store";
import type { UserRole } from "@/types/api";

/**
 * Boots the session.
 *
 * The server decides whether credentials are required, so the client asks
 * `/auth/mode` first. With auth disabled there is no login step at all: the backend
 * serves every request as a system principal with the admin role.
 */
export function useAuthBootstrap() {
  const { setMode, setUser, setInitialized, accessToken, initialized } = useAuthStore();

  const modeQuery = useQuery({
    queryKey: ["auth", "mode"],
    queryFn: api.auth.mode,
    staleTime: Infinity,
    retry: 1,
  });

  useEffect(() => {
    if (!modeQuery.data) return;
    setMode(modeQuery.data);

    const needsToken = modeQuery.data.auth_enabled && !accessToken;
    if (needsToken) {
      setUser(null);
      setInitialized(true);
      return;
    }

    let cancelled = false;
    api.auth
      .me()
      .then((user) => {
        if (!cancelled) setUser(user);
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      })
      .finally(() => {
        // `initialized` is a one-way latch, so it is set even for a superseded run.
        // A 401 here triggers a token refresh, which changes `accessToken` and re-runs
        // this effect — guarding the latch behind `cancelled` left the app spinning
        // forever on exactly the path where the session was successfully renewed.
        setInitialized(true);
      });
    return () => {
      cancelled = true;
    };
  }, [modeQuery.data, accessToken, setMode, setUser, setInitialized]);

  // A failed mode probe means the API is unreachable; stop blocking the UI so the
  // error state can render instead of an endless spinner.
  useEffect(() => {
    if (modeQuery.isError && !initialized) setInitialized(true);
  }, [modeQuery.isError, initialized, setInitialized]);

  return {
    isLoading: !initialized,
    isApiUnreachable: modeQuery.isError,
    retry: modeQuery.refetch,
  };
}

export function useLogin() {
  const router = useRouter();
  const { setTokens, setUser } = useAuthStore();

  return useMutation({
    mutationFn: async ({ email, password }: { email: string; password: string }) => {
      const tokens = await api.auth.login(email, password);
      setTokens(tokens);
      const user = await api.auth.me();
      setUser(user);
      return user;
    },
    onSuccess: (user) => {
      toast.success(`Signed in as ${user.full_name}`);
      router.push("/dashboard");
    },
    onError: (error) => toast.error(toUserMessage(error)),
  });
}

export function useLogout() {
  const router = useRouter();
  const logout = useAuthStore((s) => s.logout);
  return () => {
    logout();
    router.push("/login");
  };
}

export function useCurrentUser() {
  return useAuthStore((s) => s.user);
}

export function useAuthMode() {
  return useAuthStore((s) => s.mode);
}

/** Role helpers. With auth disabled the principal is an admin, so everything is allowed. */
export function usePermissions() {
  const user = useAuthStore((s) => s.user);
  const mode = useAuthStore((s) => s.mode);
  const authDisabled = !!mode?.auth_disabled;

  return {
    user,
    authDisabled,
    isAdmin: authDisabled || hasRole(user, ["admin"]),
    canWrite: authDisabled || hasRole(user, WRITE_ROLES),
    can: (allowed: UserRole[]) => authDisabled || hasRole(user, allowed),
  };
}
