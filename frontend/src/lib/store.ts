import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AppState {
  // Auth
  token: string | null;
  user: any | null;
  setAuth: (token: string, user: any) => void;
  logout: () => void;

  // Feed filters
  chain: string | null;
  minScore: number;
  minSources: number;
  setChain: (chain: string | null) => void;
  setMinScore: (score: number) => void;
  setMinSources: (sources: number) => void;

  // UI state
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
}

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      // Auth
      token: null,
      user: null,
      setAuth: (token, user) => {
        localStorage.setItem("auth_token", token);
        set({ token, user });
      },
      logout: () => {
        localStorage.removeItem("auth_token");
        set({ token: null, user: null });
      },

      // Feed filters
      chain: null,
      minScore: 0,
      minSources: 1,
      setChain: (chain) => set({ chain }),
      setMinScore: (minScore) => set({ minScore }),
      setMinSources: (minSources) => set({ minSources }),

      // UI
      sidebarOpen: false,
      setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
    }),
    {
      name: "bloomberg-telegram-store",
      partialize: (state) => ({
        chain: state.chain,
        minScore: state.minScore,
        minSources: state.minSources,
      }),
    }
  )
);
