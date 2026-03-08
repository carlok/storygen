import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { getAdminStats, listUsers, patchUser, deleteUser } from "@/api/admin";
import { Modal } from "@/components/Modal";
import { Footer } from "@/components/Footer";
import { StatsBar } from "@/features/admin/StatsBar";
import { AdminTable } from "@/features/admin/AdminTable";
import type { AdminStats, UserSummary } from "@/api/types";

export function AdminPage() {
  const { me, loading: authLoading } = useAuth();
  const navigate = useNavigate();

  const [stats, setStats]   = useState<AdminStats | null>(null);
  const [users, setUsers]   = useState<UserSummary[]>([]);
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

  return (
    <>
      <h1>Admin Panel</h1>
      <div className="container">
        {loading ? (
          <p style={{ color: "var(--text-muted)" }}>Loading…</p>
        ) : (
          <>
            {stats && <StatsBar stats={stats} />}
            <div className="user-table-wrap">
              <div className="section-title">Users</div>
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
