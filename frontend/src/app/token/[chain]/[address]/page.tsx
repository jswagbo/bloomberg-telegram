"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { 
  ArrowLeft, 
  ExternalLink, 
  TrendingUp, 
  TrendingDown,
  Clock,
  Users,
  Wallet,
  Copy,
  Star,
  AlertCircle,
  AlertTriangle,
  CheckCircle,
  MessageSquare,
  BarChart3,
  Shield,
  Zap,
  Check
} from "lucide-react";
import { api } from "@/lib/api";
import { cn, formatPrice, formatNumber, truncateAddress, getDexScreenerUrl } from "@/lib/utils";
import { formatDistanceToNow } from "date-fns";
import { useState } from "react";

export default function TokenDetailPage() {
  const params = useParams();
  const chain = params.chain as string;
  const address = params.address as string;
  const [copied, setCopied] = useState(false);

  // Fetch comprehensive insights - stable, no auto-refresh
  const { data: insights, isLoading: insightsLoading } = useQuery({
    queryKey: ["token-insights", chain, address],
    queryFn: () => api.getTokenInsights(chain, address),
    staleTime: 1000 * 60 * 5, // 5 minutes
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    refetchOnReconnect: false,
  });

  const { data: tokenInfo, isLoading: infoLoading } = useQuery({
    queryKey: ["token-info", chain, address],
    queryFn: () => api.getTokenInfo(chain, address),
    staleTime: 1000 * 60 * 5, // 5 minutes  
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    refetchOnReconnect: false,
  });

  const copyAddress = () => {
    navigator.clipboard.writeText(address);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (insightsLoading || infoLoading) {
    return <TokenDetailSkeleton />;
  }

  const priceData = insights?.price_data || tokenInfo || {};
  const quantitative = insights?.quantitative || {};
  const qualitative = insights?.qualitative || {};
  const chatter = insights?.chatter || {};
  const riskAssessment = insights?.risk_assessment || {};

  return (
    <div className="space-y-6">
      {/* Back button */}
      <Link href="/" className="inline-flex items-center gap-2 text-terminal-muted hover:text-terminal-text transition-colors">
        <ArrowLeft className="w-4 h-4" />
        Back to Feed
      </Link>

      {/* Header */}
      <div className="bg-terminal-card border border-terminal-border rounded-xl p-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-full bg-primary-600/20 flex items-center justify-center text-2xl font-bold">
              {insights?.token?.symbol?.[0] || priceData?.symbol?.[0] || "?"}
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold">
                  ${insights?.token?.symbol || priceData?.symbol || truncateAddress(address)}
                </h1>
                <span className="px-2 py-1 rounded bg-purple-500/20 text-purple-400 text-sm">
                  {chain}
                </span>
                {riskAssessment.level && (
                  <span className={cn(
                    "px-2 py-1 rounded text-sm font-medium",
                    riskAssessment.level === "high" ? "bg-bearish/20 text-bearish" :
                    riskAssessment.level === "low" ? "bg-bullish/20 text-bullish" :
                    "bg-yellow-500/20 text-yellow-400"
                  )}>
                    {riskAssessment.level === "high" ? "High Risk" :
                     riskAssessment.level === "low" ? "Low Risk" : "Med Risk"}
                  </span>
                )}
              </div>
              {insights?.token?.name && (
                <div className="text-terminal-muted mt-1">{insights.token.name}</div>
              )}
              <div className="flex items-center gap-2 mt-1 text-terminal-muted">
                <span className="font-mono text-sm">{truncateAddress(address, 8)}</span>
                <button onClick={copyAddress} className="hover:text-terminal-text transition-colors">
                  {copied ? <Check className="w-4 h-4 text-bullish" /> : <Copy className="w-4 h-4" />}
                </button>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button className="p-2 rounded-lg hover:bg-terminal-border transition-colors">
              <Star className="w-5 h-5 text-terminal-muted" />
            </button>
            <a
              href={priceData?.url || getDexScreenerUrl(chain, address)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-4 py-2 bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors"
            >
              <span>DEX Screener</span>
              <ExternalLink className="w-4 h-4" />
            </a>
          </div>
        </div>

        {/* Price Stats */}
        <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-terminal-bg rounded-lg p-4">
            <div className="text-terminal-muted text-sm mb-1">Price</div>
            <div className="text-xl font-bold">${formatPrice(priceData.price_usd || 0)}</div>
          </div>
          <div className="bg-terminal-bg rounded-lg p-4">
            <div className="text-terminal-muted text-sm mb-1">24h Change</div>
            <div className={cn(
              "text-xl font-bold flex items-center gap-1",
              (priceData.price_change_24h || 0) >= 0 ? "text-bullish" : "text-bearish"
            )}>
              {(priceData.price_change_24h || 0) >= 0 ? (
                <TrendingUp className="w-5 h-5" />
              ) : (
                <TrendingDown className="w-5 h-5" />
              )}
              {(priceData.price_change_24h || 0).toFixed(2)}%
            </div>
          </div>
          <div className="bg-terminal-bg rounded-lg p-4">
            <div className="text-terminal-muted text-sm mb-1">Market Cap</div>
            <div className="text-xl font-bold">
              {priceData.market_cap ? `$${formatNumber(priceData.market_cap)}` : "N/A"}
            </div>
          </div>
          <div className="bg-terminal-bg rounded-lg p-4">
            <div className="text-terminal-muted text-sm mb-1">Liquidity</div>
            <div className="text-xl font-bold">${formatNumber(priceData.liquidity_usd || 0)}</div>
          </div>
        </div>
      </div>

      {/* AI Analysis Card */}
      {(insights?.ai_analysis || insights?.summary) && (
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-gradient-to-r from-primary-600/10 to-purple-600/10 border border-primary-600/30 rounded-xl p-6"
        >
          <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
            <Zap className="w-5 h-5 text-primary-400" />
            AI Analysis
            {insights?.ai_analysis?.generated_by === "llm" && (
              <span className="text-xs px-2 py-0.5 bg-primary-600/30 rounded text-primary-300">
                Powered by {insights.ai_analysis.model || "LLM"}
              </span>
            )}
          </h2>
          
          {/* Main Summary */}
          <p className="text-terminal-text leading-relaxed mb-4">
            {insights?.ai_analysis?.summary || insights?.summary}
          </p>
          
          {insights?.ai_analysis && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
              {/* Bullish Points */}
              {insights.ai_analysis.key_bullish_points?.length > 0 && (
                <div className="bg-bullish/10 rounded-lg p-4">
                  <h3 className="text-sm font-medium text-bullish mb-2 flex items-center gap-1">
                    <TrendingUp className="w-4 h-4" />
                    Bullish Arguments
                  </h3>
                  <ul className="space-y-1">
                    {insights.ai_analysis.key_bullish_points.map((point: string, i: number) => (
                      <li key={i} className="text-sm text-terminal-text flex items-start gap-2">
                        <CheckCircle className="w-3 h-3 text-bullish mt-1 flex-shrink-0" />
                        {point}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              
              {/* Bearish Points */}
              {insights.ai_analysis.key_bearish_points?.length > 0 && (
                <div className="bg-bearish/10 rounded-lg p-4">
                  <h3 className="text-sm font-medium text-bearish mb-2 flex items-center gap-1">
                    <TrendingDown className="w-4 h-4" />
                    Risk Factors
                  </h3>
                  <ul className="space-y-1">
                    {insights.ai_analysis.key_bearish_points.map((point: string, i: number) => (
                      <li key={i} className="text-sm text-terminal-text flex items-start gap-2">
                        <AlertTriangle className="w-3 h-3 text-bearish mt-1 flex-shrink-0" />
                        {point}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
          
          {/* AI Insights Row */}
          {insights?.ai_analysis && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4 pt-4 border-t border-primary-600/20">
              <div className="text-center">
                <div className="text-xs text-terminal-muted mb-1">Consensus</div>
                <div className={cn(
                  "text-sm font-medium capitalize",
                  insights.ai_analysis.community_consensus === "bullish" ? "text-bullish" :
                  insights.ai_analysis.community_consensus === "bearish" ? "text-bearish" :
                  "text-yellow-400"
                )}>
                  {insights.ai_analysis.community_consensus || "Mixed"}
                </div>
              </div>
              <div className="text-center">
                <div className="text-xs text-terminal-muted mb-1">Risk Level</div>
                <div className={cn(
                  "text-sm font-medium capitalize",
                  insights.ai_analysis.risk_assessment === "high" ? "text-bearish" :
                  insights.ai_analysis.risk_assessment === "low" ? "text-bullish" :
                  "text-yellow-400"
                )}>
                  {insights.ai_analysis.risk_assessment || "Medium"}
                </div>
              </div>
              <div className="text-center">
                <div className="text-xs text-terminal-muted mb-1">Alpha Quality</div>
                <div className={cn(
                  "text-sm font-medium capitalize",
                  insights.ai_analysis.alpha_quality === "high" ? "text-bullish" :
                  insights.ai_analysis.alpha_quality === "low" ? "text-bearish" :
                  "text-yellow-400"
                )}>
                  {insights.ai_analysis.alpha_quality || "Medium"}
                </div>
              </div>
              <div className="text-center">
                <div className="text-xs text-terminal-muted mb-1">Recommendation</div>
                <div className="text-sm font-medium text-primary-400 truncate">
                  {insights.ai_analysis.recommendation?.split(" - ")[0] || "DYOR"}
                </div>
              </div>
            </div>
          )}
          
          {/* Notable Mentions */}
          {insights?.ai_analysis?.notable_mentions && (
            <div className="mt-4 pt-4 border-t border-primary-600/20">
              <div className="text-xs text-terminal-muted mb-1">Notable Activity</div>
              <p className="text-sm text-terminal-text">{insights.ai_analysis.notable_mentions}</p>
            </div>
          )}
        </motion.div>
      )}

      {/* Rich Context - Narratives & Intel */}
      {insights?.rich_context && (
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-terminal-card border border-terminal-border rounded-xl p-6"
        >
          <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-primary-400" />
            Community Intel
            <span className="text-xs px-2 py-0.5 bg-terminal-border rounded text-terminal-muted ml-2">
              {insights.rich_context.messages_analyzed} messages analyzed
            </span>
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Top Narratives */}
            {insights.rich_context.top_narratives?.length > 0 && (
              <div className="bg-terminal-bg rounded-lg p-4">
                <h3 className="text-sm font-medium text-terminal-muted mb-3">Dominant Narratives</h3>
                <div className="space-y-2">
                  {insights.rich_context.top_narratives.map((narrative: any, i: number) => (
                    <div key={i} className="flex items-center justify-between">
                      <span className="text-sm capitalize">
                        {narrative.type.replace(/_/g, ' ')}
                      </span>
                      <span className="text-xs px-2 py-0.5 bg-primary-600/20 rounded text-primary-400">
                        {narrative.count}x
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Price Targets */}
            {insights.rich_context.price_targets?.count > 0 && (
              <div className="bg-terminal-bg rounded-lg p-4">
                <h3 className="text-sm font-medium text-terminal-muted mb-3">Price Targets Mentioned</h3>
                <div className="space-y-2">
                  {insights.rich_context.price_targets.average && (
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-terminal-muted">Average Target</span>
                      <span className="text-sm font-medium text-bullish">
                        ${insights.rich_context.price_targets.average.toLocaleString(undefined, {maximumFractionDigits: 2})}
                      </span>
                    </div>
                  )}
                  {insights.rich_context.price_targets.max && (
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-terminal-muted">Highest Target</span>
                      <span className="text-sm font-medium">
                        ${insights.rich_context.price_targets.max.toLocaleString(undefined, {maximumFractionDigits: 2})}
                      </span>
                    </div>
                  )}
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-terminal-muted">Total Mentions</span>
                    <span className="text-sm">{insights.rich_context.price_targets.count}</span>
                  </div>
                </div>
              </div>
            )}
            
            {/* Catalysts */}
            {insights.rich_context.catalyst_mentions?.length > 0 && (
              <div className="bg-terminal-bg rounded-lg p-4">
                <h3 className="text-sm font-medium text-terminal-muted mb-3">Upcoming Catalysts</h3>
                <ul className="space-y-1">
                  {insights.rich_context.catalyst_mentions.slice(0, 3).map((catalyst: string, i: number) => (
                    <li key={i} className="text-sm text-terminal-text flex items-start gap-2">
                      <Zap className="w-3 h-3 text-fire mt-1 flex-shrink-0" />
                      {catalyst}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            
            {/* Risk Mentions */}
            {insights.rich_context.risk_mentions?.length > 0 && (
              <div className="bg-bearish/10 rounded-lg p-4">
                <h3 className="text-sm font-medium text-bearish mb-3">Risk Signals</h3>
                <ul className="space-y-1">
                  {insights.rich_context.risk_mentions.slice(0, 3).map((risk: string, i: number) => (
                    <li key={i} className="text-sm text-terminal-text flex items-start gap-2">
                      <AlertTriangle className="w-3 h-3 text-bearish mt-1 flex-shrink-0" />
                      {risk}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
          
          {/* Highlights */}
          {insights.rich_context.highlights?.length > 0 && (
            <div className="mt-4 pt-4 border-t border-terminal-border">
              <h3 className="text-sm font-medium text-terminal-muted mb-3">Key Quotes</h3>
              <div className="space-y-2">
                {insights.rich_context.highlights.slice(0, 5).map((quote: string, i: number) => (
                  <div key={i} className="text-sm text-terminal-text bg-terminal-bg rounded p-3 italic">
                    "{quote}"
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* Conviction & Urgency */}
          <div className="mt-4 pt-4 border-t border-terminal-border flex gap-4">
            <div className="flex items-center gap-2">
              <span className="text-xs text-terminal-muted">Community Conviction:</span>
              <span className={cn(
                "text-sm font-medium capitalize",
                insights.rich_context.conviction_level === "high" ? "text-bullish" :
                insights.rich_context.conviction_level === "low" ? "text-bearish" :
                "text-yellow-400"
              )}>
                {insights.rich_context.conviction_level || "Medium"}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-terminal-muted">Urgency:</span>
              <span className={cn(
                "text-sm font-medium capitalize",
                insights.rich_context.urgency_level === "urgent" ? "text-fire" :
                insights.rich_context.urgency_level === "high" ? "text-yellow-400" :
                "text-terminal-text"
              )}>
                {insights.rich_context.urgency_level || "Normal"}
              </span>
            </div>
          </div>
        </motion.div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Quantitative Metrics */}
        <div className="bg-terminal-card border border-terminal-border rounded-xl p-6">
          <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-primary-400" />
            Quantitative Metrics
          </h2>
          
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-terminal-bg rounded-lg p-4">
                <div className="flex items-center gap-2 text-terminal-muted text-sm mb-1">
                  <MessageSquare className="w-4 h-4" />
                  Total Mentions
                </div>
                <div className="text-2xl font-bold">{quantitative.total_mentions || 0}</div>
              </div>
              <div className="bg-terminal-bg rounded-lg p-4">
                <div className="flex items-center gap-2 text-terminal-muted text-sm mb-1">
                  <Users className="w-4 h-4" />
                  Unique Sources
                </div>
                <div className="text-2xl font-bold">{quantitative.unique_sources || 0}</div>
              </div>
              <div className="bg-terminal-bg rounded-lg p-4">
                <div className="flex items-center gap-2 text-terminal-muted text-sm mb-1">
                  <Wallet className="w-4 h-4 text-whale" />
                  Wallets Mentioned
                </div>
                <div className="text-2xl font-bold">{quantitative.unique_wallets || 0}</div>
              </div>
              <div className="bg-terminal-bg rounded-lg p-4">
                <div className="flex items-center gap-2 text-terminal-muted text-sm mb-1">
                  <Zap className="w-4 h-4 text-fire" />
                  Velocity
                </div>
                <div className="text-2xl font-bold">{(quantitative.velocity || 0).toFixed(1)}/min</div>
              </div>
            </div>

            {quantitative.first_seen && (
              <div className="flex items-center justify-between text-sm text-terminal-muted pt-2 border-t border-terminal-border">
                <span>First seen: {formatDistanceToNow(new Date(quantitative.first_seen))} ago</span>
                {quantitative.age_minutes && (
                  <span>Active for {Math.round(quantitative.age_minutes)} min</span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Qualitative Analysis */}
        <div className="bg-terminal-card border border-terminal-border rounded-xl p-6">
          <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
            <Shield className="w-5 h-5 text-primary-400" />
            Qualitative Analysis
          </h2>
          
          <div className="space-y-4">
            {/* Sentiment Bar */}
            <div>
              <div className="flex items-center justify-between text-sm mb-2">
                <span className={cn(
                  "font-medium",
                  qualitative.overall_sentiment === "bullish" ? "text-bullish" :
                  qualitative.overall_sentiment === "bearish" ? "text-bearish" : "text-terminal-muted"
                )}>
                  {(qualitative.bullish_percent || 50).toFixed(0)}% Bullish
                </span>
                <span className="text-terminal-muted">
                  {qualitative.bullish_count || 0} bullish · {qualitative.bearish_count || 0} bearish · {qualitative.neutral_count || 0} neutral
                </span>
              </div>
              <div className="h-3 bg-terminal-border rounded-full overflow-hidden flex">
                <div 
                  className="bg-bullish h-full transition-all"
                  style={{ width: `${qualitative.bullish_percent || 50}%` }}
                />
                <div 
                  className="bg-bearish h-full transition-all"
                  style={{ width: `${100 - (qualitative.bullish_percent || 50)}%` }}
                />
              </div>
            </div>

            {/* Risk & Quality Scores */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-terminal-bg rounded-lg p-4">
                <div className="text-terminal-muted text-sm mb-2">Risk Score</div>
                <div className="flex items-center gap-3">
                  <div className={cn(
                    "text-2xl font-bold",
                    (qualitative.risk_score || 0) > 60 ? "text-bearish" :
                    (qualitative.risk_score || 0) > 30 ? "text-yellow-400" : "text-bullish"
                  )}>
                    {(qualitative.risk_score || 0).toFixed(0)}
                  </div>
                  <span className={cn(
                    "px-2 py-1 rounded text-xs font-medium",
                    qualitative.risk_level === "high" ? "bg-bearish/20 text-bearish" :
                    qualitative.risk_level === "low" ? "bg-bullish/20 text-bullish" :
                    "bg-yellow-500/20 text-yellow-400"
                  )}>
                    {qualitative.risk_level || "medium"}
                  </span>
                </div>
              </div>
              <div className="bg-terminal-bg rounded-lg p-4">
                <div className="text-terminal-muted text-sm mb-2">Quality Score</div>
                <div className="flex items-center gap-3">
                  <div className={cn(
                    "text-2xl font-bold",
                    (qualitative.quality_score || 0) > 70 ? "text-bullish" :
                    (qualitative.quality_score || 0) > 40 ? "text-yellow-400" : "text-bearish"
                  )}>
                    {(qualitative.quality_score || 50).toFixed(0)}
                  </div>
                  <span className={cn(
                    "px-2 py-1 rounded text-xs font-medium",
                    qualitative.quality_level === "high" ? "bg-bullish/20 text-bullish" :
                    qualitative.quality_level === "low" ? "bg-bearish/20 text-bearish" :
                    "bg-yellow-500/20 text-yellow-400"
                  )}>
                    {qualitative.quality_level || "medium"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Risk Assessment */}
      {riskAssessment.warnings?.length > 0 && (
        <div className={cn(
          "border rounded-xl p-6",
          riskAssessment.level === "high" 
            ? "bg-bearish/10 border-bearish/30" 
            : "bg-yellow-500/10 border-yellow-500/30"
        )}>
          <h2 className="text-lg font-bold mb-3 flex items-center gap-2">
            <AlertTriangle className={cn(
              "w-5 h-5",
              riskAssessment.level === "high" ? "text-bearish" : "text-yellow-400"
            )} />
            Risk Warnings
          </h2>
          <ul className="space-y-2">
            {riskAssessment.warnings.map((warning: string, i: number) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                <AlertCircle className={cn(
                  "w-4 h-4 mt-0.5 flex-shrink-0",
                  riskAssessment.level === "high" ? "text-bearish" : "text-yellow-400"
                )} />
                {warning}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Chatter Summary */}
      <div className="bg-terminal-card border border-terminal-border rounded-xl p-6">
        <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-primary-400" />
          Chatter Summary
        </h2>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Key Quotes */}
          <div>
            <h3 className="text-sm font-medium text-terminal-muted mb-3">Key Quotes</h3>
            {chatter.key_quotes?.length > 0 ? (
              <div className="space-y-3">
                {chatter.key_quotes.map((quote: any, i: number) => (
                  <div 
                    key={i}
                    className={cn(
                      "rounded-lg p-3 border-l-4",
                      quote.type === "bullish" 
                        ? "bg-bullish/10 border-bullish" 
                        : "bg-bearish/10 border-bearish"
                    )}
                  >
                    <p className="text-sm mb-2">"{quote.text}"</p>
                    <div className="flex items-center justify-between text-xs text-terminal-muted">
                      <span>{quote.source}</span>
                      <span className={cn(
                        quote.type === "bullish" ? "text-bullish" : "text-bearish"
                      )}>
                        {quote.highlight}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-terminal-muted text-sm">No significant quotes yet.</p>
            )}
          </div>

          {/* Themes & Factors */}
          <div className="space-y-4">
            {/* Themes */}
            {chatter.themes?.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-terminal-muted mb-2">Top Themes</h3>
                <div className="flex flex-wrap gap-2">
                  {chatter.themes.slice(0, 8).map((theme: any, i: number) => (
                    <span 
                      key={i}
                      className="px-3 py-1 bg-terminal-bg rounded-full text-sm"
                    >
                      {theme.theme} <span className="text-terminal-muted">({theme.count})</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Quality Factors */}
            {chatter.quality_factors?.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-bullish mb-2 flex items-center gap-1">
                  <CheckCircle className="w-4 h-4" />
                  Positive Signals
                </h3>
                <div className="flex flex-wrap gap-2">
                  {chatter.quality_factors.map((factor: any, i: number) => (
                    <span 
                      key={i}
                      className="px-2 py-1 bg-bullish/20 text-bullish rounded text-xs"
                    >
                      {factor.factor} ({factor.count})
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Risk Factors */}
            {chatter.risk_factors?.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-bearish mb-2 flex items-center gap-1">
                  <AlertTriangle className="w-4 h-4" />
                  Risk Signals
                </h3>
                <div className="flex flex-wrap gap-2">
                  {chatter.risk_factors.map((factor: any, i: number) => (
                    <span 
                      key={i}
                      className="px-2 py-1 bg-bearish/20 text-bearish rounded text-xs"
                    >
                      {factor.factor} ({factor.count})
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Sources */}
        {chatter.sources?.length > 0 && (
          <div className="mt-4 pt-4 border-t border-terminal-border">
            <h3 className="text-sm font-medium text-terminal-muted mb-2">Mentioned In</h3>
            <div className="flex flex-wrap gap-2">
              {chatter.sources.map((source: string, i: number) => (
                <span key={i} className="px-3 py-1 bg-terminal-bg rounded-lg text-sm">
                  {source}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Bullish vs Bearish Messages */}
      {(chatter.bullish_messages?.length > 0 || chatter.bearish_messages?.length > 0) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Bullish Messages */}
          <div className="bg-terminal-card border border-terminal-border rounded-xl p-6">
            <h3 className="text-lg font-bold mb-4 flex items-center gap-2 text-bullish">
              <TrendingUp className="w-5 h-5" />
              Bullish Chatter ({chatter.bullish_messages?.length || 0})
            </h3>
            {chatter.bullish_messages?.length > 0 ? (
              <div className="space-y-3">
                {chatter.bullish_messages.slice(0, 5).map((msg: any, i: number) => (
                  <div key={i} className="bg-bullish/5 border border-bullish/20 rounded-lg p-3">
                    <p className="text-sm mb-2">"{msg.text}"</p>
                    <div className="flex items-center justify-between text-xs text-terminal-muted">
                      <span>{msg.source}</span>
                      <span className="text-bullish">Quality: {(msg.quality_score || 0).toFixed(0)}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-terminal-muted text-sm">No bullish messages found.</p>
            )}
          </div>

          {/* Bearish Messages */}
          <div className="bg-terminal-card border border-terminal-border rounded-xl p-6">
            <h3 className="text-lg font-bold mb-4 flex items-center gap-2 text-bearish">
              <TrendingDown className="w-5 h-5" />
              Bearish Chatter ({chatter.bearish_messages?.length || 0})
            </h3>
            {chatter.bearish_messages?.length > 0 ? (
              <div className="space-y-3">
                {chatter.bearish_messages.slice(0, 5).map((msg: any, i: number) => (
                  <div key={i} className="bg-bearish/5 border border-bearish/20 rounded-lg p-3">
                    <p className="text-sm mb-2">"{msg.text}"</p>
                    <div className="flex items-center justify-between text-xs text-terminal-muted">
                      <span>{msg.source}</span>
                      <span className="text-bearish">Risk: {(msg.risk_score || 0).toFixed(0)}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-terminal-muted text-sm">No bearish messages found.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function TokenDetailSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-4 w-24 bg-terminal-border rounded" />
      <div className="bg-terminal-card border border-terminal-border rounded-xl p-6">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-full bg-terminal-border" />
          <div className="space-y-2">
            <div className="h-8 w-32 bg-terminal-border rounded" />
            <div className="h-4 w-48 bg-terminal-border rounded" />
          </div>
        </div>
        <div className="mt-6 grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-terminal-bg rounded-lg p-4">
              <div className="h-4 w-16 bg-terminal-border rounded mb-2" />
              <div className="h-6 w-24 bg-terminal-border rounded" />
            </div>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-terminal-card border border-terminal-border rounded-xl p-6 h-64" />
        <div className="bg-terminal-card border border-terminal-border rounded-xl p-6 h-64" />
      </div>
    </div>
  );
}
