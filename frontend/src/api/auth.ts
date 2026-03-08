import { apiFetch, ApiError } from "./client";
import type { Me } from "./types";

export interface MeResult {
  user: Me | null;
  /** true when DATABASE_URL is set server-side (multi-user mode) */
  isMultiUser: boolean;
}

/**
 * Probe /api/me and return both the user and whether multi-user mode is active.
 *
 * Status mapping:
 *   200  → multi-user, logged in       { user, isMultiUser: true }
 *   401  → multi-user, not logged in   { user: null, isMultiUser: true }
 *   403  → multi-user, account disabled{ user: null, isMultiUser: true }
 *   404  → personal mode (no endpoint) { user: null, isMultiUser: false }
 */
export async function getMe(): Promise<MeResult> {
  try {
    const user = await apiFetch<Me>("/api/me");
    return { user, isMultiUser: true };
  } catch (e) {
    if (e instanceof ApiError) {
      // 401/403 = endpoint exists (multi-user mode) but user is not authenticated/active
      if (e.status === 401 || e.status === 403) {
        return { user: null, isMultiUser: true };
      }
      // 404/405 = endpoint does not exist = personal mode
      return { user: null, isMultiUser: false };
    }
    throw e;
  }
}

export async function logout(): Promise<void> {
  await apiFetch("/auth/logout", { method: "POST" });
}
