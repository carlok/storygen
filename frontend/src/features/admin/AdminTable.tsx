import { fmtDate } from "@/utils/format";
import type { UserSummary } from "@/api/types";

interface Props {
  users: UserSummary[];
  onPatch: (id: string, patch: Partial<Pick<UserSummary, "is_active" | "is_admin">>) => void;
  onDelete: (id: string, email: string) => void;
}

function Avatar({ u }: { u: UserSummary }) {
  if (u.avatar_url) return <img className="avatar" src={u.avatar_url} alt="" />;
  const initial = (u.display_name || u.email || "?")[0].toUpperCase();
  return <span className="avatar-initials">{initial}</span>;
}

export function AdminTable({ users, onPatch, onDelete }: Props) {
  if (!users.length) {
    return <div className="admin-table-card"><div className="admin-empty">No users yet.</div></div>;
  }

  return (
    <div className="admin-table-card">
      <table className="admin-table">
        <thead>
          <tr>
            <th>User</th>
            <th>Joined</th>
            <th style={{ textAlign: "center" }}>Jobs</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>

              {/* Avatar + name + email stacked */}
              <td>
                <div className="user-cell">
                  <Avatar u={u} />
                  <div className="user-info">
                    <span className="user-name">{u.display_name ?? "—"}</span>
                    <span className="user-email">{u.email}</span>
                  </div>
                </div>
              </td>

              <td>{fmtDate(u.created_at)}</td>

              <td style={{ textAlign: "center" }}>{u.job_count}</td>

              <td>
                <div className="badges-cell">
                  <span className={`badge ${u.is_active ? "badge-active" : "badge-disabled"}`}>
                    {u.is_active ? "Active" : "Disabled"}
                  </span>
                  {u.is_admin && <span className="badge badge-admin">Admin</span>}
                </div>
              </td>

              <td>
                <div className="actions-cell">
                  {u.is_active
                    ? <button className="btn-sm btn-sm-neutral" onClick={() => onPatch(u.id, { is_active: false })}>Disable</button>
                    : <button className="btn-sm btn-sm-accent"  onClick={() => onPatch(u.id, { is_active: true  })}>Enable</button>
                  }
                  {u.is_admin
                    ? <button className="btn-sm btn-sm-neutral" onClick={() => onPatch(u.id, { is_admin: false })}>Revoke admin</button>
                    : <button className="btn-sm btn-sm-neutral" onClick={() => onPatch(u.id, { is_admin: true  })}>Make admin</button>
                  }
                  <button className="btn-sm btn-sm-danger" onClick={() => onDelete(u.id, u.email)}>Delete</button>
                </div>
              </td>

            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
