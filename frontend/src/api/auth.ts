import { apiFetch, ApiError } from "./client";
import type { Me } from "./types";

/** Returns the current user, or null in personal mode (no DATABASE_URL). */
export async function getMe(): Promise<Me | null> {
  try {
    return await apiFetch<Me>("/api/me");
  } catch (e) {
    // 401 = not logged in (multi-user mode), 404/405 = personal mode
    if (e instanceof ApiError) return null;
    throw e;
  }
}

export async function logout(): Promise<void> {
  await apiFetch("/auth/logout", { method: "POST" });
}
