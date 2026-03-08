import React, { createContext, useContext, useEffect, useState } from "react";
import { getMe } from "@/api/auth";
import type { Me } from "@/api/types";

interface AuthCtx {
  me: Me | null;
  loading: boolean;
  /** true only when DATABASE_URL is set and /api/me responds with 200 */
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
      const user = await getMe();
      // getMe() returns null in personal mode OR when not logged in.
      // We distinguish: if we got a non-null user, we're definitely in multi-user.
      // If null, we stay agnostic — the UI treats personal mode as the default.
      if (user !== null) {
        setIsMultiUser(true);
        setMe(user);
      } else {
        // Could be personal mode OR not logged in. Check by probing /api/me for 401 vs 404/405.
        // getMe() already catches ApiError — null means either case.
        setMe(null);
      }
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
