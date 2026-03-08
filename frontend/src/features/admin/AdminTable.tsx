import { fmtDate } from "@/utils/format";
import type { UserSummary } from "@/api/types";

interface Props {
  users: UserSummary[];
  onPatch: (id: string, patch: Partial<Pick<UserSummary, "is_active" | "is_admin">>) => void;
  onDelete: (id: string, email: string) => void;
}

function Avatar({ u }: { u: UserSummary }) {
  if (u.avatar_url) {
    return <img className="avatar" src={u.avatar_url} alt="" />;
  }
  const initial = (u.display_name || u.email || "?")[0].toUpperCase();
  return <span className="avatar-placeholder">{initial}</span>;
}

export function AdminTable({ users, onPatch, onDelete }: Props) {
  if (!users.length) {
    return <div className="empty-msg">No users yet.</div>;
  }

  return (
    <table>
      <thead>
        <tr>
          <th>User</th>
          <th>Email</th>
          <th>Joined</th>
          <th>Jobs</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {users.map((u) => (
          <tr key={u.id}>
            <td>
              <Avatar u={u} />
              <strong>{u.display_name ?? "—"}</strong>
            </td>
            <td>{u.email}</td>
            <td>{fmtDate(u.created_at)}</td>
            <td>{u.job_count}</td>
            <td>
              <span className={`badge ${u.is_active ? "badge-active" : "badge-disabled"}`}>
                {u.is_active ? "Active" : "Disabled"}
              </span>
              {u.is_admin && (
                <>&nbsp;<span className="badge badge-admin">Admin</span></>
              )}
            </td>
            <td>
              <div className="action-cell">
                {u.is_active ? (
                  <button
                    className="btn-sm btn-disable"
                    onClick={() => onPatch(u.id, { is_active: false })}
                  >
                    Disable
                  </button>
                ) : (
                  <button
                    className="btn-sm btn-enable"
                    onClick={() => onPatch(u.id, { is_active: true })}
                  >
                    Enable
                  </button>
                )}
                {u.is_admin ? (
                  <button
                    className="btn-sm btn-rmadmin"
                    onClick={() => onPatch(u.id, { is_admin: false })}
                  >
                    Revoke admin
                  </button>
                ) : (
                  <button
                    className="btn-sm btn-mkadmin"
                    onClick={() => onPatch(u.id, { is_admin: true })}
                  >
                    Make admin
                  </button>
                )}
                <button
                  className="btn-sm btn-delete"
                  onClick={() => onDelete(u.id, u.email)}
                >
                  Delete
                </button>
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
