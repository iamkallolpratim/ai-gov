"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { toUserMessage } from "@/lib/errors";
import type { UserCreateInput } from "@/types/api";

export function useUsers(enabled = true) {
  return useQuery({
    queryKey: ["users"],
    queryFn: () => api.auth.users({ page_size: 100 }),
    enabled,
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: UserCreateInput) => api.auth.createUser(input),
    onSuccess: (user) => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success(`${user.email} created`);
    },
    onError: (error) => toast.error(toUserMessage(error)),
  });
}
