import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

export default function PerfBadge({ value, label }) {
  if (value === null || value === undefined) {
    return (
      <div className="flex flex-col items-center">
        <span className="text-xs text-slate-500 mb-1">{label}</span>
        <span className="bg-slate-700/50 text-slate-400 px-2.5 py-1 rounded-full text-xs font-medium flex items-center gap-1">
          <Minus className="w-3 h-3" />
          N/A
        </span>
      </div>
    )
  }

  const isPositive = value > 0
  const isZero = value === 0

  return (
    <div className="flex flex-col items-center">
      <span className="text-xs text-slate-500 mb-1">{label}</span>
      <span
        className={`
          px-2.5 py-1 rounded-full text-xs font-medium flex items-center gap-1
          ${isZero
            ? 'bg-slate-700/50 text-slate-400'
            : isPositive
              ? 'bg-emerald-500/20 text-emerald-400'
              : 'bg-red-500/20 text-red-400'
          }
        `}
      >
        {isZero ? (
          <Minus className="w-3 h-3" />
        ) : isPositive ? (
          <TrendingUp className="w-3 h-3" />
        ) : (
          <TrendingDown className="w-3 h-3" />
        )}
        {isPositive && '+'}{value.toFixed(1)}%
      </span>
    </div>
  )
}
