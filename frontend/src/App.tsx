import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { HomePage }  from "@/pages/HomePage";
import { LoginPage } from "@/pages/LoginPage";
import { AdminPage } from "@/pages/AdminPage";

/**
 * Wraps a route that requires authentication in multi-user mode.
 * - Personal mode (isMultiUser=false): renders children directly, no auth needed.
 * - Multi-user, logged in: renders children.
 * - Multi-user, not logged in: redirects to /login.
 * - Still loading: renders nothing (avoids flash).
 */
function ProtectedRoute({ children }: { children: ReactNode }) {
  const { me, loading, isMultiUser } = useAuth();
  if (loading) return null;
  if (isMultiUser && !me) return <Navigate to="/login" replace />;
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
