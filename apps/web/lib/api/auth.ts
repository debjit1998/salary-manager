import { api } from "./client";
import type { LoginRequest, User } from "@/types/api";

export const authApi = {
  login: (body: LoginRequest) =>
    api.post<User>("/auth/login", body).then((r) => r.data),
  logout: () => api.post<{ ok: boolean }>("/auth/logout").then((r) => r.data),
  me: () => api.get<User>("/auth/me").then((r) => r.data),
};
