import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Footer } from "@/components/Footer";

export function LoginPage() {
  const { me, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (loading) return;
    // Already logged in → go home
    if (me) navigate("/", { replace: true });
  }, [loading, me, navigate]);

  if (loading) return null;

  return (
    <>
      <h1>Story Video Generator</h1>
      <div className="login-card">
        <p className="login-sub">Sign in to access your personal video workspace.</p>
        <a className="btn-google" href="/auth/google">
          Sign in with Google
        </a>
      </div>
      <Footer />
    </>
  );
}
