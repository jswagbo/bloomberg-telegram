"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { useStore } from "@/lib/store";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 1000 * 60, // 1 minute - data stays fresh longer
            refetchOnWindowFocus: false, // Don't refetch when user returns to tab
            retry: 1, // Only retry once on failure
          },
        },
      })
  );

  // Hydrate zustand store on client and restore auth token
  useEffect(() => {
    useStore.persist.rehydrate();
    const unsubscribe = useStore.persist.onFinishHydration(() => {
      if (typeof window === "undefined") return;
      const token = localStorage.getItem("auth_token");
      const state = useStore.getState();
      if (token && !state.token) {
        state.setAuth(token, state.user);
      }
    });
    return () => {
      unsubscribe();
    };
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}
