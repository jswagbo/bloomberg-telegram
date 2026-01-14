"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import { Flame, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";

export default function LoginPage() {
  const router = useRouter();
  const { setAuth } = useStore();
  const [isLogin, setIsLogin] = useState(true);
  const [formData, setFormData] = useState({
    email: "",
    password: "",
    username: "",
  });
  const [error, setError] = useState("");

  const loginMutation = useMutation({
    mutationFn: () => api.login(formData.email, formData.password),
    onSuccess: (data) => {
      setAuth(data.access_token, null);
      router.push("/");
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || "Login failed");
    },
  });

  const registerMutation = useMutation({
    mutationFn: () => api.register(formData.email, formData.password, formData.username || undefined),
    onSuccess: () => {
      // Auto-login after register
      loginMutation.mutate();
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || "Registration failed");
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    
    if (isLogin) {
      loginMutation.mutate();
    } else {
      registerMutation.mutate();
    }
  };

  const isLoading = loginMutation.isPending || registerMutation.isPending;

  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-primary-600 flex items-center justify-center mx-auto mb-4">
            <Flame className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold">
            {isLogin ? "Welcome Back" : "Create Account"}
          </h1>
          <p className="text-terminal-muted mt-2">
            {isLogin 
              ? "Sign in to access your signal feed" 
              : "Start tracking crypto signals from Telegram"
            }
          </p>
        </div>

        <form onSubmit={handleSubmit} className="bg-terminal-card border border-terminal-border rounded-xl p-6 space-y-4">
          {error && (
            <div className="p-3 bg-bearish/20 border border-bearish/30 rounded-lg text-bearish text-sm">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium mb-1">Email</label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              className="w-full px-4 py-2.5 bg-terminal-bg border border-terminal-border rounded-lg focus:border-primary-600 focus:outline-none"
              placeholder="you@example.com"
              required
            />
          </div>

          {!isLogin && (
            <div>
              <label className="block text-sm font-medium mb-1">Username (optional)</label>
              <input
                type="text"
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                className="w-full px-4 py-2.5 bg-terminal-bg border border-terminal-border rounded-lg focus:border-primary-600 focus:outline-none"
                placeholder="satoshi"
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium mb-1">Password</label>
            <input
              type="password"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              className="w-full px-4 py-2.5 bg-terminal-bg border border-terminal-border rounded-lg focus:border-primary-600 focus:outline-none"
              placeholder="••••••••"
              required
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50 font-medium"
          >
            {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
            {isLogin ? "Sign In" : "Create Account"}
          </button>

          <div className="text-center text-sm">
            <span className="text-terminal-muted">
              {isLogin ? "Don't have an account? " : "Already have an account? "}
            </span>
            <button
              type="button"
              onClick={() => setIsLogin(!isLogin)}
              className="text-primary-400 hover:underline"
            >
              {isLogin ? "Sign up" : "Sign in"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
