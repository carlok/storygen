// ── Shared domain types mirroring FastAPI Pydantic schemas ────────────────────

export interface Block {
  index: number;
  image: string;
  start: number;
  end: number;
  text: string;
  align_center: boolean;
  center_x: boolean;
  bw: boolean;
  fade_in: boolean;
  fade_out: boolean;
  text_position: [number, number];
}

export interface BlocksResponse {
  blocks: Block[];
  video_width: number;
  video_height: number;
  font_size: number;
}

export interface BlockUpdate {
  index: number;
  text: string;
  align_center: boolean;
  center_x: boolean;
  bw: boolean;
  fade_in: boolean;
  fade_out: boolean;
  text_position: [number, number];
}

export interface GenerateResponse {
  status: string;
  filename: string;
}

export interface Me {
  id: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  is_admin: boolean;
  is_active: boolean;
}

export interface UserSummary {
  id: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
  job_count: number;
}

export interface AdminStats {
  total_users: number;
  total_jobs: number;
  disk_bytes: number;
}
