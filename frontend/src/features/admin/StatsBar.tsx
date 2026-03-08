import { fmtBytes } from "@/utils/format";
import type { AdminStats } from "@/api/types";

export function StatsBar({ stats }: { stats: AdminStats }) {
  return (
    <div className="stats-bar">
      <div className="stat-card">
        <div className="stat-val">{stats.total_users}</div>
        <div className="stat-lbl">Users</div>
      </div>
      <div className="stat-card">
        <div className="stat-val">{stats.total_jobs}</div>
        <div className="stat-lbl">Videos generated</div>
      </div>
      <div className="stat-card">
        <div className="stat-val">{fmtBytes(stats.disk_bytes)}</div>
        <div className="stat-lbl">Disk used</div>
      </div>
    </div>
  );
}
