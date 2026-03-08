import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { logout } from "@/api/auth";
import { getAdminStats, listUsers, patchUser, deleteUser } from "@/api/admin";
import { Modal } from "@/components/Modal";
import { StatsBar } from "@/features/admin/StatsBar";
import { AdminTable } from "@/features/admin/AdminTable";
import type { AdminStats, UserSummary } from "@/api/types";

export function AdminPage() {
  const { me, loading: authLoading, refresh } = useAuth();
  const navigate = useNavigate();

  const [stats, setStats]       = useState<AdminStats | null>(null);
  const [users, setUsers]       = useState<UserSummary[]>([]);
  const [loading, setLoading]   = useState(true);
  const [modalMsg, setModalMsg] = useState<string | null>(null);

  // Switch body to full-width admin layout
  useEffect(() => {
    document.body.classList.add("admin-layout");
    return () => document.body.classList.remove("admin-layout");
  }, []);

  const reload = async () => {
    const [s, u] = await Promise.all([getAdminStats(), listUsers()]);
    setStats(s);
    setUsers(u);
  };

  useEffect(() => {
    if (authLoading) return;
    if (!me?.is_admin) { navigate("/", { replace: true }); return; }
    reload().finally(() => setLoading(false));
  }, [authLoading, me, navigate]);

  const handlePatch = async (
    id: string,
    patch: Partial<Pick<UserSummary, "is_active" | "is_admin">>,
  ) => {
    setModalMsg("Updating…");
    try { await patchUser(id, patch); await reload(); }
    finally { setModalMsg(null); }
  };

  const handleDelete = async (id: string, email: string) => {
    if (!window.confirm(`Permanently delete ${email} and all their data?\nThis cannot be undone.`)) return;
    setModalMsg("Deleting…");
    try { await deleteUser(id); await reload(); }
    finally { setModalMsg(null); }
  };

  const handleLogout = async () => {
    await logout();
    await refresh();
    navigate("/login");
  };

  return (
    <div className="admin-shell">

      {/* ── Sticky top bar ── */}
      <header className="admin-topbar">
        <div className="admin-topbar-left">
          <span className="admin-topbar-wordmark">storygen</span>
          <div className="admin-topbar-sep" />
          <span className="admin-topbar-label">Admin</span>
        </div>

        <div className="admin-topbar-right">
          {me?.avatar_url && (
            <img className="admin-topbar-avatar" src={me.avatar_url} alt="" />
          )}
          <span className="admin-topbar-name">{me?.display_name ?? me?.email}</span>
          <a href="/" className="btn-topbar">← Back to app</a>
          <button className="btn-topbar btn-topbar-danger" onClick={handleLogout}>
            Sign out
          </button>
        </div>
      </header>

      {/* ── Main content ── */}
      <main className="admin-content">
        {loading ? (
          <div className="admin-loading">Loading…</div>
        ) : (
          <>
            {/* Stats */}
            {stats && (
              <section>
                <div className="admin-section-head">
                  <h2 className="admin-section-title">Overview</h2>
                </div>
                <StatsBar stats={stats} />
              </section>
            )}

            {/* Users */}
            <section>
              <div className="admin-section-head">
                <h2 className="admin-section-title">Users</h2>
                <span className="admin-count-badge">{users.length}</span>
              </div>
              <AdminTable users={users} onPatch={handlePatch} onDelete={handleDelete} />
            </section>
          </>
        )}
      </main>

      <Modal visible={modalMsg !== null} message={modalMsg ?? ""} />
    </div>
  );
}
