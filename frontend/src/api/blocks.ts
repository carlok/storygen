import { apiFetch } from "./client";
import type { BlocksResponse, BlockUpdate, GenerateResponse } from "./types";

export const getBlocks = (): Promise<BlocksResponse> =>
  apiFetch<BlocksResponse>("/api/blocks");

export const generateVideo = (updates: BlockUpdate[]): Promise<GenerateResponse> =>
  apiFetch<GenerateResponse>("/api/generate", {
    method: "POST",
    body: JSON.stringify(updates),
  });

export const sendEmail = (to: string, filename: string): Promise<void> =>
  apiFetch<void>("/api/send-email", {
    method: "POST",
    body: JSON.stringify({ to, filename }),
  });
