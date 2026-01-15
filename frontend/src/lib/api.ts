import axios from "axios";

// Use relative path to go through Next.js rewrites in next.config.js
// This ensures the API calls work in both dev and production
const apiClient = axios.create({
  baseURL: "/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
});

// Add auth token to requests
apiClient.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("auth_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

export interface SignalFeedParams {
  chain?: string | null;
  minScore?: number;
  minSources?: number;
  limit?: number;
}

export interface TokenInfo {
  address: string;
  symbol: string;
  name: string;
  chain: string;
  price_usd: number;
  price_change_24h: number;
  volume_24h: number;
  liquidity_usd: number;
  market_cap: number;
}

export interface WhyMovingResponse {
  token: {
    address: string;
    symbol: string;
    chain: string;
  };
  price_change: {
    percent: number;
    from: number;
    to: number;
    timeframe_minutes: number;
  };
  reasons: Array<{
    rank: number;
    description: string;
  }>;
  timeline: Array<{
    timestamp: string;
    type: string;
    description: string;
    source: string;
    confidence: number;
  }>;
  confidence: number;
  summary: string;
}

export const api = {
  // Auth
  login: async (email: string, password: string) => {
    const response = await apiClient.post("/auth/login", { email, password });
    return response.data;
  },

  register: async (email: string, password: string, username?: string) => {
    const response = await apiClient.post("/auth/register", { email, password, username });
    return response.data;
  },

  // Signals
  getSignalFeed: async (params: SignalFeedParams = {}) => {
    const response = await apiClient.get("/signals/feed", { params });
    return response.data;
  },

  getTrendingSignals: async (chain?: string, limit: number = 10) => {
    const response = await apiClient.get("/signals/trending", { params: { chain, limit } });
    return response.data;
  },

  getNewSignals: async (chain?: string, maxAgeMinutes: number = 10) => {
    const response = await apiClient.get("/signals/new", { params: { chain, max_age_minutes: maxAgeMinutes } });
    return response.data;
  },

  getWhaleAlerts: async (chain?: string) => {
    const response = await apiClient.get("/signals/whale-alerts", { params: { chain } });
    return response.data;
  },

  getClusterDetail: async (clusterId: string) => {
    const response = await apiClient.get(`/signals/clusters/${clusterId}`);
    return response.data;
  },

  // Why Moving
  getWhyMoving: async (chain: string, tokenAddress: string, windowMinutes: number = 30): Promise<WhyMovingResponse> => {
    const response = await apiClient.get(`/signals/why-moving/${chain}/${tokenAddress}`, {
      params: { window_minutes: windowMinutes },
    });
    return response.data;
  },

  // Tokens
  getTokenInfo: async (chain: string, tokenAddress: string): Promise<TokenInfo> => {
    const response = await apiClient.get(`/tokens/info/${chain}/${tokenAddress}`);
    return response.data;
  },

  getTokenHistory: async (chain: string, tokenAddress: string, days: number = 7) => {
    const response = await apiClient.get(`/tokens/history/${chain}/${tokenAddress}`, { params: { days } });
    return response.data;
  },

  searchTokens: async (query: string, chain?: string) => {
    const response = await apiClient.get("/tokens/search", { params: { query, chain } });
    return response.data.results;
  },

  getTokenCallers: async (chain: string, tokenAddress: string) => {
    const response = await apiClient.get(`/tokens/callers/${chain}/${tokenAddress}`);
    return response.data;
  },

  // Sources
  getSourceLeaderboard: async (minCalls: number = 5, limit: number = 20) => {
    const response = await apiClient.get("/sources/leaderboard", { params: { min_calls: minCalls, limit } });
    return response.data;
  },

  getSourceReputation: async (telegramId: string) => {
    const response = await apiClient.get(`/sources/reputation/${telegramId}`);
    return response.data;
  },

  getSourcePerformance: async (telegramId: string, timeframe: string = "30d") => {
    const response = await apiClient.get(`/sources/performance/${telegramId}`, { params: { timeframe } });
    return response.data;
  },

  getFlaggedSources: async () => {
    const response = await apiClient.get("/sources/flagged");
    return response.data;
  },

  // Wallets
  getWalletProfile: async (chain: string, address: string) => {
    const response = await apiClient.get(`/wallets/profile/${chain}/${address}`);
    return response.data;
  },

  getWhaleActivity: async (chain: string, hours: number = 24) => {
    const response = await apiClient.get(`/wallets/activity/${chain}`, { params: { hours } });
    return response.data;
  },

  // Feed stats
  getFeedStats: async () => {
    const response = await apiClient.get("/feed/stats");
    return response.data;
  },

  // User
  getCurrentUser: async () => {
    const response = await apiClient.get("/users/me");
    return response.data;
  },

  getTrackedTokens: async () => {
    const response = await apiClient.get("/users/me/tracked-tokens");
    return response.data;
  },

  trackToken: async (tokenAddress: string, chain: string) => {
    const response = await apiClient.post("/users/me/tracked-tokens", { token_address: tokenAddress, chain });
    return response.data;
  },

  untrackToken: async (tokenId: string) => {
    await apiClient.delete(`/users/me/tracked-tokens/${tokenId}`);
  },

  getAlerts: async (unreadOnly: boolean = false) => {
    const response = await apiClient.get("/users/me/alerts", { params: { unread_only: unreadOnly } });
    return response.data;
  },

  // Telegram
  startTelegramAuth: async (apiId: number, apiHash: string, phone: string) => {
    const response = await apiClient.post("/telegram/auth/start", { api_id: apiId, api_hash: apiHash, phone });
    return response.data;
  },

  verifyTelegramCode: async (sessionName: string, code: string) => {
    const response = await apiClient.post(`/telegram/auth/verify-code?session_name=${sessionName}`, { code });
    return response.data;
  },

  verifyTelegram2FA: async (sessionName: string, password: string) => {
    const response = await apiClient.post(`/telegram/auth/verify-2fa?session_name=${sessionName}`, { password });
    return response.data;
  },

  completeTelegramAuth: async (sessionName: string, apiId: number, apiHash: string, phone: string) => {
    const params = new URLSearchParams({
      session_name: sessionName,
      api_id: String(apiId),
      api_hash: apiHash,
      phone,
    });
    const response = await apiClient.post(`/telegram/auth/complete?${params.toString()}`);
    return response.data;
  },

  getTelegramAccounts: async () => {
    const response = await apiClient.get("/telegram/accounts");
    return response.data;
  },

  deleteTelegramAccount: async (accountId: string) => {
    await apiClient.delete(`/telegram/accounts/${accountId}`);
  },

  // Telegram Dialogs (channels/groups the user can add as sources)
  getTelegramDialogs: async (accountId: string) => {
    const response = await apiClient.get(`/telegram/accounts/${accountId}/dialogs`);
    return response.data;
  },

  // Telegram Sources (channels/groups being monitored)
  getTelegramSources: async (accountId: string) => {
    const response = await apiClient.get(`/telegram/accounts/${accountId}/sources`);
    return response.data;
  },

  addTelegramSource: async (accountId: string, source: {
    telegram_id: string;
    source_type: string;
    name: string;
    username?: string;
    priority?: string;
  }) => {
    const response = await apiClient.post(`/telegram/accounts/${accountId}/sources`, source);
    return response.data;
  },

  deleteTelegramSource: async (sourceId: string) => {
    await apiClient.delete(`/telegram/sources/${sourceId}`);
  },

  // Ingest messages from sources
  ingestMessages: async (accountId: string, limit: number = 50) => {
    const response = await apiClient.post(`/telegram/accounts/${accountId}/ingest`, { limit });
    return response.data;
  },
};

export default api;
