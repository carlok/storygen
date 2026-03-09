import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { HomePage }  from "@/pages/HomePage";
import { LoginPage } from "@/pages/LoginPage";
import { AdminPage } from "@/pages/AdminPage";

/**
 * Wraps routes that require an authenticated user.
 * - Loading: renders nothing (avoids flash).
 * - Not logged in: redirects to /login.
 * - Logged in: renders children.
 */
function ProtectedRoute({ children }: { children: ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) return null;
  if (!me) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export function App() {
  return (
    <Routes>
      <Route path="/"      element={<ProtectedRoute><HomePage /></ProtectedRoute>} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/admin" element={<ProtectedRoute><AdminPage /></ProtectedRoute>} />
      <Route path="*"      element={<Navigate to="/" replace />} />
    </Routes>
  );
}
