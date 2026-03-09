import { fmtBytes } from "@/utils/format";
import type { AdminStats } from "@/api/types";

export function StatsBar({ stats }: { stats: AdminStats }) {
  return (
    <div className="admin-stats">
      <div className="stat-item">
        <span className="stat-number">{stats.total_users}</span>
        <span className="stat-label">Users</span>
      </div>

      <div className="stat-sep" />

      <div className="stat-item">
        <span className="stat-number">{stats.total_jobs}</span>
        <span className="stat-label">Videos generated</span>
      </div>

      <div className="stat-sep" />

      <div className="stat-item">
        <span className="stat-number">{fmtBytes(stats.disk_bytes)}</span>
        <span className="stat-label">Disk used</span>
      </div>
    </div>
  );
}
