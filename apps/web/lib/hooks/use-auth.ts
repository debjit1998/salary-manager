"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { authApi } from "@/lib/api/auth";

/** The /auth/me query — the single source of truth for "am I logged in?". */
export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: authApi.me,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}

export function useLogin() {
  const router = useRouter();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: authApi.login,
    onSuccess: (user) => {
      qc.setQueryData(["me"], user);
      router.push("/dashboard");
    },
  });
}

export function useLogout() {
  const router = useRouter();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => {
      qc.clear();
      router.push("/login");
    },
  });
}
