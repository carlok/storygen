import { useNavigate } from "react-router-dom";
import { logout } from "@/api/auth";
import { useAuth } from "@/context/AuthContext";

export function Header() {
  const { me, isMultiUser, refresh } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    await refresh();
    navigate("/login");
  };

  return (
    <div className="app-header">
      <h1>Story Video Generator</h1>
      {isMultiUser && me && (
        <div className="header-user">
          {me.avatar_url && (
            <img className="header-avatar" src={me.avatar_url} alt="" />
          )}
          <span>{me.display_name ?? me.email}</span>
          {me.is_admin && (
            <a href="/admin" style={{ fontSize: "0.7rem", color: "var(--accent)", textDecoration: "none" }}>
              Admin
            </a>
          )}
          <button className="btn-logout" onClick={handleLogout}>
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
