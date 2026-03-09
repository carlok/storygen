import { apiFetch } from "./client";
import type { Me } from "./types";

export async function getMe(): Promise<Me> {
  return apiFetch<Me>("/api/me");
}

export async function logout(): Promise<void> {
  await apiFetch("/auth/logout", { method: "POST" });
}
