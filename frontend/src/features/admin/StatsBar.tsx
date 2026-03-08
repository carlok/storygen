import { fmtBytes } from "@/utils/format";
import type { AdminStats } from "@/api/types";

export function StatsBar({ stats }: { stats: AdminStats }) {
  return (
    <div className="stats-bar">
      <div className="stat-card">
        <div className="stat-label">Total users</div>
        <div className="stat-value">{stats.total_users}</div>
      </div>
      <div className="stat-card">
        <div className="stat-label">Videos generated</div>
        <div className="stat-value">{stats.total_jobs}</div>
      </div>
      <div className="stat-card">
        <div className="stat-label">Disk used</div>
        <div className="stat-value">{fmtBytes(stats.disk_bytes)}</div>
      </div>
    </div>
  );
}
