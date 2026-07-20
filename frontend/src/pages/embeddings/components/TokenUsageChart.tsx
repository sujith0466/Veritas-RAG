import { motion } from 'framer-motion'
import { Activity, Database, CheckCircle, Clock, AlertTriangle, Zap } from 'lucide-react'
import type { EmbeddingMetricsDTO } from '@/types'

interface TokenUsageChartProps {
  metrics: EmbeddingMetricsDTO | null
  isLoading: boolean
}

export function TokenUsageChart({ metrics, isLoading }: TokenUsageChartProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 animate-pulse h-28" />
        ))}
      </div>
    )
  }

  const quota = metrics?.monthly_token_quota || 1_000_000
  const consumed = metrics?.total_tokens_consumed || 0
  const remaining = metrics?.remaining_tokens || quota
  const vectorsStored = metrics?.total_vectors_stored || 0
  const activeCount = metrics?.active_jobs_count || 0
  const completedCount = metrics?.completed_jobs_count || 0
  const failedCount = metrics?.failed_jobs_count || 0

  const usagePercent = Math.min(100, Math.round((consumed / quota) * 100))

  return (
    <div className="space-y-4 mb-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Token Quota Card */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-slate-900/60 backdrop-blur border border-slate-800/80 rounded-xl p-5 flex flex-col justify-between shadow-lg"
        >
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Token Quota</p>
            <div className="w-10 h-10 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <Zap className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-2">
            <p className="text-2xl font-bold text-slate-100">
              {consumed.toLocaleString()} <span className="text-xs font-normal text-slate-400">/ {quota.toLocaleString()}</span>
            </p>
            <div className="w-full bg-slate-800 rounded-full h-1.5 mt-2.5 overflow-hidden">
              <div
                className={`h-full transition-all duration-500 ${
                  usagePercent > 80 ? 'bg-amber-500' : 'bg-indigo-500'
                }`}
                style={{ width: `${usagePercent}%` }}
              />
            </div>
            <p className="text-xs text-slate-500 mt-1.5 flex justify-between">
              <span>{usagePercent}% utilized</span>
              <span>{remaining.toLocaleString()} left</span>
            </p>
          </div>
        </motion.div>

        {/* Total Vectors Stored */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-slate-900/60 backdrop-blur border border-slate-800/80 rounded-xl p-5 flex flex-col justify-between shadow-lg"
        >
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Vectors Generated</p>
            <div className="w-10 h-10 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
              <Database className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-2">
            <p className="text-2xl font-bold text-slate-100">{vectorsStored.toLocaleString()}</p>
            <p className="text-xs text-slate-500 mt-2 flex items-center gap-1.5">
              <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
              Idempotent hash tracking active
            </p>
          </div>
        </motion.div>

        {/* Active & Completed Jobs */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="bg-slate-900/60 backdrop-blur border border-slate-800/80 rounded-xl p-5 flex flex-col justify-between shadow-lg"
        >
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Pipeline Throughput</p>
            <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <Activity className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-2 flex items-center justify-between">
            <div>
              <p className="text-2xl font-bold text-slate-100">{completedCount.toLocaleString()}</p>
              <p className="text-xs text-slate-500 mt-1 flex items-center gap-1">
                <CheckCircle className="w-3.5 h-3.5 text-emerald-400" /> Completed
              </p>
            </div>
            <div className="text-right border-l border-slate-800 pl-4">
              <p className="text-2xl font-bold text-indigo-400">{activeCount.toLocaleString()}</p>
              <p className="text-xs text-slate-500 mt-1 flex items-center justify-end gap-1">
                <Clock className="w-3.5 h-3.5 text-indigo-400 animate-spin" /> In Progress
              </p>
            </div>
          </div>
        </motion.div>

        {/* Failed Jobs Status */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="bg-slate-900/60 backdrop-blur border border-slate-800/80 rounded-xl p-5 flex flex-col justify-between shadow-lg"
        >
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Failed Jobs</p>
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
              failedCount > 0
                ? 'bg-rose-500/10 border border-rose-500/20 text-rose-400'
                : 'bg-slate-800/60 border border-slate-700/60 text-slate-400'
            }`}>
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-2">
            <p className={`text-2xl font-bold ${failedCount > 0 ? 'text-rose-400' : 'text-slate-100'}`}>
              {failedCount.toLocaleString()}
            </p>
            <p className="text-xs text-slate-500 mt-2">
              {failedCount === 0 ? 'Zero unrecoverable failures' : 'Check job logs for details'}
            </p>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
