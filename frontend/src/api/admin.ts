import { apiFetch } from "./client";
import type { AdminStats, UserSummary } from "./types";

export const getAdminStats = (): Promise<AdminStats> =>
  apiFetch<AdminStats>("/api/admin/stats");

export const listUsers = (limit = 200): Promise<UserSummary[]> =>
  apiFetch<UserSummary[]>(`/api/admin/users?limit=${limit}`);

export const patchUser = (
  id: string,
  patch: Partial<Pick<UserSummary, "is_active" | "is_admin">>,
): Promise<UserSummary> =>
  apiFetch<UserSummary>(`/api/admin/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });

export const deleteUser = (id: string): Promise<void> =>
  apiFetch<void>(`/api/admin/users/${id}`, { method: "DELETE" });
