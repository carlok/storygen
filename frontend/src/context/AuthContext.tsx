import React, { createContext, useContext, useEffect, useState } from "react";
import { getMe } from "@/api/auth";
import type { Me } from "@/api/types";

interface AuthCtx {
  me: Me | null;
  loading: boolean;
  /** true when DATABASE_URL is set server-side (multi-user mode) */
  isMultiUser: boolean;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthCtx>({
  me: null,
  loading: true,
  isMultiUser: false,
  refresh: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [isMultiUser, setIsMultiUser] = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      const { user, isMultiUser: multi } = await getMe();
      setIsMultiUser(multi);
      setMe(user);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  return (
    <AuthContext.Provider value={{ me, loading, isMultiUser, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
