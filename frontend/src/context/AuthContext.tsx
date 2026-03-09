import React, { createContext, useContext, useEffect, useState } from "react";
import { getMe } from "@/api/auth";
import type { Me } from "@/api/types";

interface AuthCtx {
  me: Me | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthCtx>({
  me: null,
  loading: true,
  refresh: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    try {
      const user = await getMe();
      setMe(user);
    } catch {
      // 401 or network error → not logged in
      setMe(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  return (
    <AuthContext.Provider value={{ me, loading, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
