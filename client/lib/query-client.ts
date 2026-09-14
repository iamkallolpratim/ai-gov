import { QueryCache, QueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { ApiError, toUserMessage } from "@/lib/errors";

/**
 * One place for read-path error reporting. Mutations surface their own toasts, because
 * the message depends on the action ("Classification complete", "Evidence queued").
 */
export function createQueryClient() {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (error) => {
        // 401 is handled by the API client (refresh, then redirect); a toast would just
        // race the redirect. 404 is rendered inline by the page.
        if (error instanceof ApiError && (error.isAuth || error.isNotFound)) return;
        toast.error(toUserMessage(error));
      },
    }),
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          // Client errors will not fix themselves; only retry transient failures.
          if (error instanceof ApiError && error.status < 500) return false;
          return failureCount < 2;
        },
      },
      mutations: { retry: false },
    },
  });
}
