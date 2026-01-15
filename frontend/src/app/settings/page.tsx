"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { 
  Settings, 
  Key, 
  Bell, 
  MessageSquare,
  Plus,
  Trash2,
  Check,
  Loader2
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useStore } from "@/lib/store";

export default function SettingsPage() {
  return (
    <div className="max-w-3xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Settings className="w-6 h-6" />
          Settings
        </h1>
        <p className="text-terminal-muted mt-1">
          Configure your Telegram connections and preferences
        </p>
      </div>

      {/* Telegram Accounts */}
      <TelegramSettings />

      {/* Notification Settings */}
      <NotificationSettings />
    </div>
  );
}

function TelegramSettings() {
  const { telegramApiId, telegramApiHash, telegramPhone, setTelegramCredentials, token } = useStore();
  const [isAdding, setIsAdding] = useState(false);
  const [authStep, setAuthStep] = useState<"credentials" | "code" | "2fa" | null>(null);
  const [sessionName, setSessionName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    apiId: telegramApiId || "",
    apiHash: telegramApiHash || "",
    phone: telegramPhone || "",
    code: "",
    password: "",
  });

  useEffect(() => {
    setFormData((prev) => ({
      ...prev,
      apiId: telegramApiId || "",
      apiHash: telegramApiHash || "",
      phone: telegramPhone || "",
    }));
  }, [telegramApiId, telegramApiHash, telegramPhone]);

  useEffect(() => {
    setTelegramCredentials(formData.apiId, formData.apiHash, formData.phone);
  }, [formData.apiId, formData.apiHash, formData.phone, setTelegramCredentials]);

  const { data: accounts, refetch } = useQuery({
    queryKey: ["telegram-accounts"],
    queryFn: () => api.getTelegramAccounts(),
    enabled: Boolean(token), // Only fetch when logged in
  });

  useEffect(() => {
    if (token) {
      refetch();
    }
  }, [token, refetch]);

  const completeAuth = useMutation({
    mutationFn: () =>
      api.completeTelegramAuth(
        sessionName,
        parseInt(formData.apiId),
        formData.apiHash,
        formData.phone
      ),
    onSuccess: () => {
      setIsAdding(false);
      setAuthStep(null);
      setError(null);
      refetch();
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || "Failed to save Telegram account");
    },
  });

  const startAuth = useMutation({
    mutationFn: () => api.startTelegramAuth(
      parseInt(formData.apiId),
      formData.apiHash,
      formData.phone
    ),
    onSuccess: (data) => {
      setSessionName(data.session_name);
      if (data.state === "awaiting_code") {
        setAuthStep("code");
      } else if (data.state === "authenticated") {
        completeAuth.mutate();
      }
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || "Failed to start Telegram auth");
    },
  });

  const verifyCode = useMutation({
    mutationFn: () => api.verifyTelegramCode(sessionName, formData.code),
    onSuccess: (data) => {
      if (data.state === "awaiting_2fa") {
        setAuthStep("2fa");
      } else if (data.state === "authenticated") {
        completeAuth.mutate();
      }
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || "Verification failed");
    },
  });

  const verify2FA = useMutation({
    mutationFn: () => api.verifyTelegram2FA(sessionName, formData.password),
    onSuccess: (data) => {
      if (data.state === "authenticated") {
        completeAuth.mutate();
      }
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || "2FA verification failed");
    },
  });

  return (
    <div className="bg-terminal-card border border-terminal-border rounded-xl">
      <div className="px-6 py-4 border-b border-terminal-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-primary-400" />
          <h2 className="font-medium">Telegram Accounts</h2>
        </div>
        {!isAdding && (
          <button
            onClick={() => {
              setIsAdding(true);
              setAuthStep("credentials");
            }}
            className="flex items-center gap-2 px-3 py-1.5 bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors text-sm"
          >
            <Plus className="w-4 h-4" />
            Add Account
          </button>
        )}
      </div>

      <div className="p-6">
        {isAdding ? (
          <div className="space-y-4">
            {error && (
              <div className="p-3 bg-bearish/20 border border-bearish/30 rounded-lg text-bearish text-sm">
                {error}
              </div>
            )}
            {authStep === "credentials" && (
              <>
                <p className="text-sm text-terminal-muted mb-4">
                  Get your API credentials from{" "}
                  <a 
                    href="https://my.telegram.org/apps" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-primary-400 hover:underline"
                  >
                    my.telegram.org/apps
                  </a>
                </p>
                <div>
                  <label className="block text-sm font-medium mb-1">API ID</label>
                  <input
                    type="text"
                    value={formData.apiId}
                    onChange={(e) => setFormData({ ...formData, apiId: e.target.value })}
                    className="w-full px-3 py-2 bg-terminal-bg border border-terminal-border rounded-lg focus:border-primary-600 focus:outline-none"
                    placeholder="12345678"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">API Hash</label>
                  <input
                    type="password"
                    value={formData.apiHash}
                    onChange={(e) => setFormData({ ...formData, apiHash: e.target.value })}
                    className="w-full px-3 py-2 bg-terminal-bg border border-terminal-border rounded-lg focus:border-primary-600 focus:outline-none"
                    placeholder="Enter your API hash"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Phone Number</label>
                  <input
                    type="tel"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    className="w-full px-3 py-2 bg-terminal-bg border border-terminal-border rounded-lg focus:border-primary-600 focus:outline-none"
                    placeholder="+1234567890"
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setIsAdding(false)}
                    className="px-4 py-2 bg-terminal-border rounded-lg hover:bg-terminal-border/80 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => startAuth.mutate()}
                    disabled={startAuth.isPending || completeAuth.isPending}
                    className="flex items-center gap-2 px-4 py-2 bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50"
                  >
                    {startAuth.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                    Continue
                  </button>
                </div>
              </>
            )}

            {authStep === "code" && (
              <>
                <p className="text-sm text-terminal-muted mb-4">
                  Enter the code sent to your Telegram app
                </p>
                <div>
                  <label className="block text-sm font-medium mb-1">Verification Code</label>
                  <input
                    type="text"
                    value={formData.code}
                    onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                    className="w-full px-3 py-2 bg-terminal-bg border border-terminal-border rounded-lg focus:border-primary-600 focus:outline-none"
                    placeholder="12345"
                  />
                </div>
                <button
                  onClick={() => verifyCode.mutate()}
                  disabled={verifyCode.isPending || completeAuth.isPending}
                  className="flex items-center gap-2 px-4 py-2 bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50"
                >
                  {verifyCode.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                  Verify
                </button>
              </>
            )}

            {authStep === "2fa" && (
              <>
                <p className="text-sm text-terminal-muted mb-4">
                  Enter your 2FA password
                </p>
                <div>
                  <label className="block text-sm font-medium mb-1">Password</label>
                  <input
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    className="w-full px-3 py-2 bg-terminal-bg border border-terminal-border rounded-lg focus:border-primary-600 focus:outline-none"
                    placeholder="Enter 2FA password"
                  />
                </div>
                <button
                  onClick={() => verify2FA.mutate()}
                  disabled={verify2FA.isPending || completeAuth.isPending}
                  className="flex items-center gap-2 px-4 py-2 bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors"
                >
                  {verify2FA.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                  Verify
                </button>
              </>
            )}
          </div>
        ) : accounts?.length > 0 ? (
          <div className="space-y-3">
            {accounts.map((account: any) => (
              <div 
                key={account.id}
                className="flex items-center justify-between p-3 bg-terminal-bg rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <div className={cn(
                    "w-2 h-2 rounded-full",
                    account.is_connected ? "bg-bullish" : "bg-terminal-muted"
                  )} />
                  <div>
                    <div className="font-medium">{account.session_name}</div>
                    <div className="text-sm text-terminal-muted">
                      {account.is_connected ? "Connected" : "Disconnected"}
                    </div>
                  </div>
                </div>
                <button className="p-2 hover:bg-terminal-border rounded-lg transition-colors">
                  <Trash2 className="w-4 h-4 text-bearish" />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-terminal-muted text-sm text-center py-8">
            No Telegram accounts connected. Add one to start receiving signals.
          </p>
        )}
      </div>
    </div>
  );
}

function NotificationSettings() {
  const [settings, setSettings] = useState({
    newSignals: true,
    priceAlerts: true,
    whaleAlerts: true,
    emailNotifications: false,
  });

  return (
    <div className="bg-terminal-card border border-terminal-border rounded-xl">
      <div className="px-6 py-4 border-b border-terminal-border flex items-center gap-2">
        <Bell className="w-5 h-5 text-primary-400" />
        <h2 className="font-medium">Notifications</h2>
      </div>

      <div className="p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-medium">New High-Score Signals</div>
            <div className="text-sm text-terminal-muted">
              Get notified when signals score above 70
            </div>
          </div>
          <button
            onClick={() => setSettings({ ...settings, newSignals: !settings.newSignals })}
            className={cn(
              "w-12 h-6 rounded-full transition-colors relative",
              settings.newSignals ? "bg-primary-600" : "bg-terminal-border"
            )}
          >
            <div className={cn(
              "w-5 h-5 rounded-full bg-white absolute top-0.5 transition-transform",
              settings.newSignals ? "translate-x-6" : "translate-x-0.5"
            )} />
          </button>
        </div>

        <div className="flex items-center justify-between">
          <div>
            <div className="font-medium">Price Alerts</div>
            <div className="text-sm text-terminal-muted">
              Alerts for tracked tokens
            </div>
          </div>
          <button
            onClick={() => setSettings({ ...settings, priceAlerts: !settings.priceAlerts })}
            className={cn(
              "w-12 h-6 rounded-full transition-colors relative",
              settings.priceAlerts ? "bg-primary-600" : "bg-terminal-border"
            )}
          >
            <div className={cn(
              "w-5 h-5 rounded-full bg-white absolute top-0.5 transition-transform",
              settings.priceAlerts ? "translate-x-6" : "translate-x-0.5"
            )} />
          </button>
        </div>

        <div className="flex items-center justify-between">
          <div>
            <div className="font-medium">Whale Alerts</div>
            <div className="text-sm text-terminal-muted">
              Large wallet activity notifications
            </div>
          </div>
          <button
            onClick={() => setSettings({ ...settings, whaleAlerts: !settings.whaleAlerts })}
            className={cn(
              "w-12 h-6 rounded-full transition-colors relative",
              settings.whaleAlerts ? "bg-primary-600" : "bg-terminal-border"
            )}
          >
            <div className={cn(
              "w-5 h-5 rounded-full bg-white absolute top-0.5 transition-transform",
              settings.whaleAlerts ? "translate-x-6" : "translate-x-0.5"
            )} />
          </button>
        </div>
      </div>
    </div>
  );
}
