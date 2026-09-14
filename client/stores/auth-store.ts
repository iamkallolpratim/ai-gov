"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

import { registerAuthBridge } from "@/lib/api";
import type { AuthMode, TokenResponse, User, UserRole } from "@/types/api";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  mode: AuthMode | null;
  /** False until the auth mode has been probed and any stored session validated. */
  initialized: boolean;

  setTokens: (tokens: TokenResponse) => void;
  setUser: (user: User | null) => void;
  setMode: (mode: AuthMode) => void;
  setInitialized: (value: boolean) => void;
  logout: () => void;
}

/**
 * Tokens live in localStorage. For a bearer-token SPA that is the usual trade-off: it
 * survives a refresh, at the cost of being readable by injected script. The backend
 * keeps access tokens short-lived (30 minutes) to bound that exposure.
 */
export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      mode: null,
      initialized: false,

      setTokens: (tokens) =>
        set({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token }),
      setUser: (user) => set({ user }),
      setMode: (mode) => set({ mode }),
      setInitialized: (value) => set({ initialized: value }),
      logout: () => set({ accessToken: null, refreshToken: null, user: null }),
    }),
    {
      name: "aigov-auth",
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
      }),
    },
  ),
);

// Give the API client access to the tokens without importing the store (which would be
// circular). Registered once, at module load.
registerAuthBridge({
  getTokens: () => {
    const { accessToken, refreshToken } = useAuthStore.getState();
    return { accessToken, refreshToken };
  },
  setTokens: (tokens) => useAuthStore.getState().setTokens(tokens),
  onFailure: () => {
    const { mode, logout } = useAuthStore.getState();
    // With auth disabled a 401 cannot mean "signed out"; never bounce to a login page
    // that the deployment does not use.
    if (mode?.auth_disabled) return;
    logout();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
  },
});

// --- role helpers ----------------------------------------------------------

export const ROLE_LABELS: Record<UserRole, string> = {
  admin: "Admin",
  risk_officer: "Risk officer",
  viewer: "Viewer",
};

/** Roles allowed to mutate inventory, run assessments and generate evidence. */
export const WRITE_ROLES: UserRole[] = ["admin", "risk_officer"];

export function hasRole(user: User | null, allowed: UserRole[]): boolean {
  return !!user && allowed.includes(user.role);
}
