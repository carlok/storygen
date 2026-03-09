import { Link, useNavigate } from "react-router-dom";
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
      {/* Clicking the title always goes home */}
      <Link to="/" className="app-title-link">
        <h1>Story Video Generator</h1>
      </Link>

      {isMultiUser && me && (
        <div className="header-user">
          {me.avatar_url && (
            <img className="header-avatar" src={me.avatar_url} alt="" />
          )}
          <span>{me.display_name ?? me.email}</span>
          {me.is_admin && (
            <Link to="/admin" className="header-admin-link">Admin</Link>
          )}
          <button className="btn-logout" onClick={handleLogout}>
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
