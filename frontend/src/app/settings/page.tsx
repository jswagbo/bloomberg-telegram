"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { 
  Settings, 
  Bell,
  Moon,
  Volume2,
  Shield,
  Zap,
  Link,
  Save,
  Check
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useStore } from "@/lib/store";

export default function SettingsPage() {
  const { minScore, minSources, setMinScore, setMinSources } = useStore();
  const [saved, setSaved] = useState(false);
  
  // Local settings state
  const [notifications, setNotifications] = useState(true);
  const [soundAlerts, setSoundAlerts] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [darkMode, setDarkMode] = useState(true);

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

      {/* Signal Preferences */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
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
