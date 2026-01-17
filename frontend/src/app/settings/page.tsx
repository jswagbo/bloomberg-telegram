"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Settings, 
  Bell,
  Moon,
  Zap,
  Save,
  Check,
  MessageSquare,
  Plus,
  Trash2,
  ToggleLeft,
  ToggleRight,
  Loader2,
  RefreshCw,
  Users,
  Radio,
  Bot,
  ChevronDown,
  ChevronUp,
  AlertCircle
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useStore } from "@/lib/store";
import { api } from "@/lib/api";

interface TelegramSource {
  id: string;
  telegram_id: string;
  source_type: string;
  name: string;
  username?: string;
  priority: string;
  is_active: boolean;
  total_messages: number;
  created_at: string;
}

interface TelegramDialog {
  id: number;
  name: string;
  type: string;
  username?: string;
  unread_count: number;
}

interface TelegramAccount {
  id: string;
  session_name: string;
  is_active: boolean;
  is_connected: boolean;
  last_connected?: string;
  created_at: string;
}

export default function SettingsPage() {
  const { minScore, minSources, setMinScore, setMinSources } = useStore();
  const [saved, setSaved] = useState(false);
  const [expandedAccount, setExpandedAccount] = useState<string | null>(null);
  const [showAddSource, setShowAddSource] = useState<string | null>(null);
  const queryClient = useQueryClient();
  
  // Local settings state
  const [notifications, setNotifications] = useState(true);
  const [soundAlerts, setSoundAlerts] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [darkMode, setDarkMode] = useState(true);

  // Fetch Telegram accounts
  const { data: accounts, isLoading: accountsLoading } = useQuery({
    queryKey: ["telegram-accounts"],
    queryFn: () => api.getTelegramAccounts(),
    retry: false,
  });

  // Auto-expand first account
  useEffect(() => {
    if (accounts?.length > 0 && !expandedAccount) {
      setExpandedAccount(accounts[0].id);
    }
  }, [accounts, expandedAccount]);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Settings className="w-6 h-6 text-primary-400" />
          Settings
        </h1>
        <p className="text-terminal-muted mt-1">
          Customize your signal feed experience
        </p>
      </div>

      {/* Telegram Sources Section */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-terminal-card border border-terminal-border rounded-xl p-6"
      >
        <h2 className="font-bold mb-4 flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-primary-400" />
          Telegram Channels
          <span className="text-xs text-terminal-muted font-normal ml-2">
            Select which chats to scan for signals
          </span>
        </h2>

        {accountsLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-primary-400" />
          </div>
        ) : accounts?.length > 0 ? (
          <div className="space-y-4">
            {accounts.map((account: TelegramAccount) => (
              <TelegramAccountCard
                key={account.id}
                account={account}
                isExpanded={expandedAccount === account.id}
                onToggle={() => setExpandedAccount(
                  expandedAccount === account.id ? null : account.id
                )}
                showAddSource={showAddSource === account.id}
                onToggleAddSource={() => setShowAddSource(
                  showAddSource === account.id ? null : account.id
                )}
              />
            ))}
          </div>
        ) : (
          <TelegramConnectFlow onSuccess={() => queryClient.invalidateQueries({ queryKey: ["telegram-accounts"] })} />
        )}
      </motion.div>

      {/* Signal Preferences */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-terminal-card border border-terminal-border rounded-xl p-6"
      >
        <h2 className="font-bold mb-4 flex items-center gap-2">
          <Zap className="w-5 h-5 text-fire" />
          Signal Preferences
        </h2>
        
        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium mb-2">
              Minimum Score Filter
            </label>
            <p className="text-xs text-terminal-muted mb-3">
              Only show signals with score above this threshold
            </p>
            <input
              type="range"
              min="0"
              max="100"
              step="10"
              value={minScore}
              onChange={(e) => setMinScore(parseInt(e.target.value))}
              className="w-full h-2 bg-terminal-border rounded-lg appearance-none cursor-pointer accent-primary-600"
            />
            <div className="flex justify-between text-xs text-terminal-muted mt-1">
              <span>All</span>
              <span className="font-medium text-primary-400">{minScore}+</span>
              <span>100</span>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              Minimum Sources Required
            </label>
            <p className="text-xs text-terminal-muted mb-3">
              Filter signals by number of unique sources mentioning them
            </p>
            <div className="flex gap-2">
              {[1, 2, 3, 5].map((n) => (
                <button
                  key={n}
                  onClick={() => setMinSources(n)}
                  className={cn(
                    "px-4 py-2 rounded-lg text-sm font-medium transition-colors",
                    minSources === n
                      ? "bg-primary-600 text-white"
                      : "bg-terminal-border text-terminal-muted hover:text-terminal-text"
                  )}
                >
                  {n}+
                </button>
              ))}
            </div>
          </div>
        </div>
      </motion.div>

      {/* Notifications */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-terminal-card border border-terminal-border rounded-xl p-6"
      >
        <h2 className="font-bold mb-4 flex items-center gap-2">
          <Bell className="w-5 h-5 text-primary-400" />
          Notifications
        </h2>
        
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">Push Notifications</div>
              <div className="text-xs text-terminal-muted">Get alerts for high-score signals</div>
            </div>
            <button
              onClick={() => setNotifications(!notifications)}
              className={cn(
                "w-12 h-6 rounded-full transition-colors relative",
                notifications ? "bg-primary-600" : "bg-terminal-border"
              )}
            >
              <div className={cn(
                "w-5 h-5 rounded-full bg-white absolute top-0.5 transition-transform",
                notifications ? "translate-x-6" : "translate-x-0.5"
              )} />
            </button>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">Sound Alerts</div>
              <div className="text-xs text-terminal-muted">Play sound for new signals</div>
            </div>
            <button
              onClick={() => setSoundAlerts(!soundAlerts)}
              className={cn(
                "w-12 h-6 rounded-full transition-colors relative",
                soundAlerts ? "bg-primary-600" : "bg-terminal-border"
              )}
            >
              <div className={cn(
                "w-5 h-5 rounded-full bg-white absolute top-0.5 transition-transform",
                soundAlerts ? "translate-x-6" : "translate-x-0.5"
              )} />
            </button>
          </div>
        </div>
      </motion.div>

      {/* Display */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="bg-terminal-card border border-terminal-border rounded-xl p-6"
      >
        <h2 className="font-bold mb-4 flex items-center gap-2">
          <Moon className="w-5 h-5 text-primary-400" />
          Display
        </h2>
        
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">Dark Mode</div>
              <div className="text-xs text-terminal-muted">Use dark terminal theme</div>
            </div>
            <button
              onClick={() => setDarkMode(!darkMode)}
              className={cn(
                "w-12 h-6 rounded-full transition-colors relative",
                darkMode ? "bg-primary-600" : "bg-terminal-border"
              )}
            >
              <div className={cn(
                "w-5 h-5 rounded-full bg-white absolute top-0.5 transition-transform",
                darkMode ? "translate-x-6" : "translate-x-0.5"
              )} />
            </button>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">Auto Refresh</div>
              <div className="text-xs text-terminal-muted">Automatically update feed every 30s</div>
            </div>
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={cn(
                "w-12 h-6 rounded-full transition-colors relative",
                autoRefresh ? "bg-primary-600" : "bg-terminal-border"
              )}
            >
              <div className={cn(
                "w-5 h-5 rounded-full bg-white absolute top-0.5 transition-transform",
                autoRefresh ? "translate-x-6" : "translate-x-0.5"
              )} />
            </button>
          </div>
        </div>
      </motion.div>

      {/* Save Button */}
      <motion.button
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        onClick={handleSave}
        className={cn(
          "w-full flex items-center justify-center gap-2 py-3 rounded-xl font-medium transition-colors",
          saved
            ? "bg-bullish text-white"
            : "bg-primary-600 hover:bg-primary-700 text-white"
        )}
      >
        {saved ? (
          <>
            <Check className="w-5 h-5" />
            Saved!
          </>
        ) : (
          <>
            <Save className="w-5 h-5" />
            Save Settings
          </>
        )}
      </motion.button>
    </div>
  );
}

// Telegram Account Card Component
function TelegramAccountCard({ 
  account, 
  isExpanded, 
  onToggle,
  showAddSource,
  onToggleAddSource,
}: { 
  account: TelegramAccount;
  isExpanded: boolean;
  onToggle: () => void;
  showAddSource: boolean;
  onToggleAddSource: () => void;
}) {
  const queryClient = useQueryClient();
  const [showReconnectConfirm, setShowReconnectConfirm] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);

  // Check session health on mount
  useEffect(() => {
    const checkSession = async () => {
      try {
        const result = await api.refreshTrendingMessages();
        if (result?.errors?.length > 0 && result.errors[0].includes("session may have expired")) {
          setSessionError("Session expired - click Reconnect to fix");
        } else if (result?.messages > 0) {
          setSessionError(null);
        }
      } catch (e) {
        // Ignore errors
      }
    };
    checkSession();
  }, []);

  // Delete account mutation (for reconnect)
  const deleteAccountMutation = useMutation({
    mutationFn: () => api.deleteTelegramAccount(account.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["telegram-accounts"] });
      setShowReconnectConfirm(false);
      // Show success and reload to show "Connect Telegram" UI
      alert("Telegram disconnected. The page will reload - you can then reconnect your Telegram account.");
      window.location.reload();
    },
    onError: (error: any) => {
      alert(`Failed to disconnect: ${error?.message || "Unknown error"}`);
    },
  });

  // Fetch sources for this account
  const { data: sources, isLoading: sourcesLoading, refetch: refetchSources } = useQuery({
    queryKey: ["telegram-sources", account.id],
    queryFn: () => api.getTelegramSources(account.id),
    enabled: isExpanded,
  });

  // Fetch available dialogs
  const { data: dialogs, isLoading: dialogsLoading, refetch: refetchDialogs } = useQuery({
    queryKey: ["telegram-dialogs", account.id],
    queryFn: () => api.getTelegramDialogs(account.id),
    enabled: showAddSource,
  });

  // Add source mutation
  const addSourceMutation = useMutation({
    mutationFn: (dialog: TelegramDialog) => api.addTelegramSource(account.id, {
      telegram_id: String(dialog.id),
      source_type: dialog.type,
      name: dialog.name,
      username: dialog.username,
      priority: "medium",
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["telegram-sources", account.id] });
      onToggleAddSource();
    },
  });

  // Delete source mutation
  const deleteSourceMutation = useMutation({
    mutationFn: (sourceId: string) => api.deleteTelegramSource(sourceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["telegram-sources", account.id] });
    },
  });

  // Get source IDs that are already added
  const addedSourceIds = new Set(sources?.map((s: TelegramSource) => String(s.telegram_id)) || []);

  // Filter dialogs to only show ones not already added
  const availableDialogs = dialogs?.filter((d: TelegramDialog) => !addedSourceIds.has(String(d.id))) || [];

  const getTypeIcon = (type: string) => {
    switch (type) {
      case "channel": return <Radio className="w-4 h-4" />;
      case "group": return <Users className="w-4 h-4" />;
      case "bot": return <Bot className="w-4 h-4" />;
      default: return <MessageSquare className="w-4 h-4" />;
    }
  };

  return (
    <div className={cn(
      "border rounded-lg overflow-hidden",
      sessionError ? "border-orange-500/50" : "border-terminal-border"
    )}>
      {/* Session Error Banner */}
      {sessionError && (
        <div className="px-4 py-2 bg-orange-500/20 border-b border-orange-500/30 flex items-center justify-between">
          <div className="flex items-center gap-2 text-orange-400 text-sm">
            <AlertCircle className="w-4 h-4" />
            <span>{sessionError}</span>
          </div>
          <button
            onClick={() => setShowReconnectConfirm(true)}
            className="px-3 py-1 bg-orange-500 hover:bg-orange-600 text-white text-xs font-medium rounded transition-colors"
          >
            Reconnect
          </button>
        </div>
      )}

      {/* Reconnect Confirmation Modal */}
      {showReconnectConfirm && (
        <div className="px-4 py-3 bg-terminal-bg border-b border-terminal-border">
          <p className="text-sm mb-3">
            This will disconnect your Telegram and require you to sign in again with your phone number.
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => deleteAccountMutation.mutate()}
              disabled={deleteAccountMutation.isPending}
              className="flex-1 px-3 py-2 bg-orange-500 hover:bg-orange-600 text-white text-sm font-medium rounded transition-colors disabled:opacity-50"
            >
              {deleteAccountMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin mx-auto" />
              ) : (
                "Yes, Reconnect"
              )}
            </button>
            <button
              onClick={() => setShowReconnectConfirm(false)}
              className="flex-1 px-3 py-2 bg-terminal-border hover:bg-terminal-border/80 text-terminal-text text-sm font-medium rounded transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Account Header */}
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-3 bg-terminal-bg hover:bg-terminal-border/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className={cn(
            "w-2 h-2 rounded-full",
            sessionError ? "bg-orange-500" : account.is_connected ? "bg-bullish" : "bg-terminal-muted"
          )} />
          <span className="font-medium">{account.session_name}</span>
          {sources && (
            <span className="text-xs text-terminal-muted">
              {sources.filter((s: TelegramSource) => s.is_active).length} active sources
            </span>
          )}
        </div>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 text-terminal-muted" />
        ) : (
          <ChevronDown className="w-4 h-4 text-terminal-muted" />
        )}
      </button>

      {/* Sources List */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="px-4 py-3 space-y-2 border-t border-terminal-border">
              {sourcesLoading ? (
                <div className="flex items-center justify-center py-4">
                  <Loader2 className="w-5 h-5 animate-spin text-terminal-muted" />
                </div>
              ) : sources?.length > 0 ? (
                <>
                  {sources.map((source: TelegramSource) => (
                    <div
                      key={source.id}
                      className={cn(
                        "flex items-center justify-between p-3 rounded-lg transition-colors",
                        source.is_active ? "bg-terminal-bg" : "bg-terminal-bg/50 opacity-60"
                      )}
                    >
                      <div className="flex items-center gap-3">
                        <div className={cn(
                          "w-8 h-8 rounded-lg flex items-center justify-center",
                          source.source_type === "channel" ? "bg-purple-500/20 text-purple-400" :
                          source.source_type === "group" ? "bg-blue-500/20 text-blue-400" :
                          "bg-terminal-border text-terminal-muted"
                        )}>
                          {getTypeIcon(source.source_type)}
                        </div>
                        <div>
                          <div className="font-medium text-sm">{source.name}</div>
                          <div className="text-xs text-terminal-muted">
                            {source.username && `@${source.username} • `}
                            {source.total_messages} messages
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={cn(
                          "text-xs px-2 py-0.5 rounded",
                          source.is_active 
                            ? "bg-bullish/20 text-bullish" 
                            : "bg-terminal-border text-terminal-muted"
                        )}>
                          {source.is_active ? "Active" : "Paused"}
                        </span>
                        <button
                          onClick={() => deleteSourceMutation.mutate(source.id)}
                          disabled={deleteSourceMutation.isPending}
                          className="p-1.5 hover:bg-bearish/20 rounded transition-colors text-terminal-muted hover:text-bearish"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </>
              ) : (
                <p className="text-center text-terminal-muted text-sm py-4">
                  No sources added yet
                </p>
              )}

              {/* Add Source Button / Dialog List */}
              {/* Reconnect button - always visible */}
              <div className="mt-4 pt-4 border-t border-terminal-border">
                <button
                  onClick={() => setShowReconnectConfirm(true)}
                  className="w-full flex items-center justify-center gap-2 py-2 text-sm text-orange-400 hover:text-orange-300 hover:bg-orange-500/10 rounded-lg transition-colors"
                >
                  <RefreshCw className="w-4 h-4" />
                  Reconnect Telegram Session
                </button>
              </div>

              {showAddSource ? (
                <div className="mt-4 p-4 bg-terminal-bg rounded-lg border border-terminal-border">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-medium text-sm">Add a channel or group</h4>
                    <button
                      onClick={() => refetchDialogs()}
                      disabled={dialogsLoading}
                      className="p-1 hover:bg-terminal-border rounded"
                    >
                      <RefreshCw className={cn("w-4 h-4", dialogsLoading && "animate-spin")} />
                    </button>
                  </div>
                  
                  {dialogsLoading ? (
                    <div className="flex items-center justify-center py-4">
                      <Loader2 className="w-5 h-5 animate-spin text-terminal-muted" />
                    </div>
                  ) : availableDialogs.length > 0 ? (
                    <div className="space-y-1 max-h-60 overflow-y-auto">
                      {availableDialogs.map((dialog: TelegramDialog) => (
                        <button
                          key={dialog.id}
                          onClick={() => addSourceMutation.mutate(dialog)}
                          disabled={addSourceMutation.isPending}
                          className="w-full flex items-center gap-3 p-2 rounded hover:bg-terminal-border transition-colors text-left"
                        >
                          <div className={cn(
                            "w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0",
                            dialog.type === "channel" ? "bg-purple-500/20 text-purple-400" :
                            dialog.type === "group" ? "bg-blue-500/20 text-blue-400" :
                            "bg-terminal-border text-terminal-muted"
                          )}>
                            {getTypeIcon(dialog.type)}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="font-medium text-sm truncate">{dialog.name}</div>
                            <div className="text-xs text-terminal-muted">
                              {dialog.username && `@${dialog.username}`}
                            </div>
                          </div>
                          <Plus className="w-4 h-4 text-primary-400 flex-shrink-0" />
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-4 text-terminal-muted text-sm">
                      <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      No more channels available to add
                    </div>
                  )}

                  <button
                    onClick={onToggleAddSource}
                    className="w-full mt-3 py-2 text-sm text-terminal-muted hover:text-terminal-text transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={onToggleAddSource}
                  className="w-full flex items-center justify-center gap-2 py-3 border border-dashed border-terminal-border rounded-lg text-terminal-muted hover:text-terminal-text hover:border-primary-600/50 transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  Add Channel or Group
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Telegram Connect Flow Component
function TelegramConnectFlow({ onSuccess }: { onSuccess: () => void }) {
  const [step, setStep] = useState<"start" | "code" | "2fa">("start");
  const [formData, setFormData] = useState({
    apiId: "",
    apiHash: "",
    phone: "",
    code: "",
    password: "",
  });
  const [sessionName, setSessionName] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleStartAuth = async () => {
    setError("");
    setIsLoading(true);
    try {
      const result = await api.startTelegramAuth(
        parseInt(formData.apiId),
        formData.apiHash,
        formData.phone
      );
      console.log("Auth start result:", result);
      setSessionName(result.session_name);
      // Backend returns "state" not "status"
      if (result.state === "awaiting_code") {
        setStep("code");
      } else {
        setError(`Unexpected state: ${result.state}`);
      }
    } catch (err: any) {
      console.error("Auth start error:", err);
      setError(err.response?.data?.detail || err.message || "Failed to start auth");
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyCode = async () => {
    setError("");
    setIsLoading(true);
    try {
      const result = await api.verifyTelegramCode(sessionName, formData.code);
      console.log("Verify code result:", result);
      // Backend returns "state" - handle various success states
      if (result.state === "awaiting_2fa") {
        setStep("2fa");
      } else if (result.state === "completed" || result.state === "authenticated") {
        // Both "completed" and "authenticated" mean success
        await handleComplete();
      } else {
        setError(`Unexpected state: ${result.state}`);
      }
    } catch (err: any) {
      console.error("Verify code error:", err);
      setError(err.response?.data?.detail || err.message || "Invalid code");
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerify2FA = async () => {
    setError("");
    setIsLoading(true);
    try {
      const result = await api.verifyTelegram2FA(sessionName, formData.password);
      console.log("Verify 2FA result:", result);
      // Backend returns "state" not "status"
      if (result.state === "completed") {
        await handleComplete();
      } else {
        setError(`Unexpected state: ${result.state}`);
      }
    } catch (err: any) {
      console.error("Verify 2FA error:", err);
      setError(err.response?.data?.detail || err.message || "Invalid password");
    } finally {
      setIsLoading(false);
    }
  };

  const handleComplete = async () => {
    setIsLoading(true);
    try {
      console.log("Completing auth with session:", sessionName);
      const result = await api.completeTelegramAuth(
        sessionName,
        parseInt(formData.apiId),
        formData.apiHash,
        formData.phone
      );
      console.log("Complete auth result:", result);
      alert("Telegram connected successfully! The page will reload.");
      onSuccess();
      window.location.reload();
    } catch (err: any) {
      console.error("Complete auth error:", err);
      setError(err.response?.data?.detail || err.message || "Failed to complete auth");
      setIsLoading(false);
    }
  };

  return (
    <div className="text-center py-6">
      <MessageSquare className="w-12 h-12 mx-auto text-terminal-muted mb-3" />
      
      {step === "start" && (
        <>
          <p className="text-terminal-muted mb-4">Connect your Telegram to monitor channels</p>
          
          <div className="text-left space-y-3 max-w-sm mx-auto">
            {error && (
              <div className="p-3 bg-bearish/20 border border-bearish/30 rounded-lg text-bearish text-sm">
                {error}
              </div>
            )}
            
            <div className="text-xs text-terminal-muted mb-2">
              Get your API credentials from{" "}
              <a href="https://my.telegram.org/apps" target="_blank" rel="noopener noreferrer" className="text-primary-400 hover:underline">
                my.telegram.org/apps
              </a>
            </div>
            
            <input
              type="text"
              placeholder="API ID (e.g., 12345678)"
              value={formData.apiId}
              onChange={(e) => setFormData({ ...formData, apiId: e.target.value })}
              className="w-full px-4 py-2.5 bg-terminal-bg border border-terminal-border rounded-lg focus:border-primary-600 focus:outline-none text-sm"
            />
            <input
              type="text"
              placeholder="API Hash"
              value={formData.apiHash}
              onChange={(e) => setFormData({ ...formData, apiHash: e.target.value })}
              className="w-full px-4 py-2.5 bg-terminal-bg border border-terminal-border rounded-lg focus:border-primary-600 focus:outline-none text-sm"
            />
            <input
              type="tel"
              placeholder="Phone (+1234567890)"
              value={formData.phone}
              onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
              className="w-full px-4 py-2.5 bg-terminal-bg border border-terminal-border rounded-lg focus:border-primary-600 focus:outline-none text-sm"
            />
            
            <button
              onClick={handleStartAuth}
              disabled={isLoading || !formData.apiId || !formData.apiHash || !formData.phone}
              className="w-full py-2.5 bg-primary-600 hover:bg-primary-700 disabled:bg-terminal-border disabled:text-terminal-muted text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              Connect Telegram
            </button>
          </div>
        </>
      )}

      {step === "code" && (
        <>
          <p className="text-terminal-muted mb-4">Enter the code sent to your Telegram</p>
          
          <div className="text-left space-y-3 max-w-sm mx-auto">
            {error && (
              <div className="p-3 bg-bearish/20 border border-bearish/30 rounded-lg text-bearish text-sm">
                {error}
              </div>
            )}
            
            <input
              type="text"
              placeholder="Verification code"
              value={formData.code}
              onChange={(e) => setFormData({ ...formData, code: e.target.value })}
              className="w-full px-4 py-2.5 bg-terminal-bg border border-terminal-border rounded-lg focus:border-primary-600 focus:outline-none text-sm text-center text-2xl tracking-widest"
              maxLength={6}
            />
            
            <button
              onClick={handleVerifyCode}
              disabled={isLoading || !formData.code}
              className="w-full py-2.5 bg-primary-600 hover:bg-primary-700 disabled:bg-terminal-border disabled:text-terminal-muted text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
              Verify Code
            </button>
          </div>
        </>
      )}

      {step === "2fa" && (
        <>
          <p className="text-terminal-muted mb-4">Enter your 2FA password</p>
          
          <div className="text-left space-y-3 max-w-sm mx-auto">
            {error && (
              <div className="p-3 bg-bearish/20 border border-bearish/30 rounded-lg text-bearish text-sm">
                {error}
              </div>
            )}
            
            <input
              type="password"
              placeholder="2FA Password"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              className="w-full px-4 py-2.5 bg-terminal-bg border border-terminal-border rounded-lg focus:border-primary-600 focus:outline-none text-sm"
            />
            
            <button
              onClick={handleVerify2FA}
              disabled={isLoading || !formData.password}
              className="w-full py-2.5 bg-primary-600 hover:bg-primary-700 disabled:bg-terminal-border disabled:text-terminal-muted text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
              Verify Password
            </button>
          </div>
        </>
      )}
    </div>
  );
}
