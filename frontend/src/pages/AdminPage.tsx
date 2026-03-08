import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { logout } from "@/api/auth";
import { getAdminStats, listUsers, patchUser, deleteUser } from "@/api/admin";
import { Modal } from "@/components/Modal";
import { Footer } from "@/components/Footer";
import { StatsBar } from "@/features/admin/StatsBar";
import { AdminTable } from "@/features/admin/AdminTable";
import type { AdminStats, UserSummary } from "@/api/types";

export function AdminPage() {
  const { me, loading: authLoading, refresh } = useAuth();
  const navigate = useNavigate();

  const [stats, setStats]     = useState<AdminStats | null>(null);
  const [users, setUsers]     = useState<UserSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalMsg, setModalMsg] = useState<string | null>(null);

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
    if (!window.confirm(`Permanently delete ${email} and all their data? This cannot be undone.`)) return;
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
    <>
      <div className="admin-container">

        {/* ── Page header ── */}
        <div className="admin-page-header">
          <h1 className="admin-page-title">Admin Panel</h1>
          <div className="admin-page-meta">
            {me?.avatar_url && (
              <img className="header-avatar" src={me.avatar_url} alt="" />
            )}
            <span style={{ fontSize: "0.82rem", color: "var(--text-dim)" }}>
              {me?.display_name ?? me?.email}
            </span>
            <a href="/" className="btn-back">← Back to app</a>
            <button className="btn-logout" onClick={handleLogout}>Sign out</button>
          </div>
        </div>

        {loading ? (
          <p style={{ color: "var(--text-muted)", padding: "2rem 0" }}>Loading…</p>
        ) : (
          <>
            {/* ── Stats ── */}
            {stats && <StatsBar stats={stats} />}

            {/* ── Users table ── */}
            <div>
              <div className="section-header">
                <span className="section-title">Users</span>
                <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                  {users.length} {users.length === 1 ? "user" : "users"}
                </span>
              </div>
              <AdminTable users={users} onPatch={handlePatch} onDelete={handleDelete} />
            </div>
          </>
        )}

      </div>

      <Footer />
      <Modal visible={modalMsg !== null} message={modalMsg ?? ""} />
    </>
  );
}
