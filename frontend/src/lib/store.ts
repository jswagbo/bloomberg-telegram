import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

interface AppState {
  // Auth
  token: string | null;
  user: any | null;
  setAuth: (token: string, user: any) => void;
  logout: () => void;

  // Telegram credentials
  telegramApiId: string;
  telegramApiHash: string;
  telegramPhone: string;
  setTelegramCredentials: (apiId: string, apiHash: string, phone: string) => void;

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
        if (typeof window !== "undefined") {
          localStorage.setItem("auth_token", token);
        }
        set({ token, user });
      },
      logout: () => {
        if (typeof window !== "undefined") {
          localStorage.removeItem("auth_token");
        }
        set({ token: null, user: null });
      },

      // Telegram credentials
      telegramApiId: "",
      telegramApiHash: "",
      telegramPhone: "",
      setTelegramCredentials: (apiId, apiHash, phone) =>
        set({ telegramApiId: apiId, telegramApiHash: apiHash, telegramPhone: phone }),

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
      storage: createJSONStorage(() => {
        if (typeof window !== "undefined") {
          return localStorage;
        }
        // Return a noop storage for SSR
        return {
          getItem: () => null,
          setItem: () => {},
          removeItem: () => {},
        };
      }),
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        telegramApiId: state.telegramApiId,
        telegramApiHash: state.telegramApiHash,
        telegramPhone: state.telegramPhone,
        chain: state.chain,
        minScore: state.minScore,
        minSources: state.minSources,
      }),
      skipHydration: true,
    }
  )
);
