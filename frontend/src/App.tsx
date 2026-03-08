import { Navigate, Route, Routes } from "react-router-dom";
import { HomePage }  from "@/pages/HomePage";
import { LoginPage } from "@/pages/LoginPage";
import { AdminPage } from "@/pages/AdminPage";

export function App() {
  return (
    <Routes>
      <Route path="/"      element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/admin" element={<AdminPage />} />
      <Route path="*"      element={<Navigate to="/" replace />} />
    </Routes>
  );
}
