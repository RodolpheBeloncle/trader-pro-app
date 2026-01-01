import { Filter } from 'lucide-react'

export default function Filters({ filters, onChange }) {
  return (
    <div className="flex flex-wrap items-center gap-6">
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <Filter className="w-4 h-4" />
        Filters:
      </div>

      {/* Resilient only checkbox */}
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={filters.resilientOnly}
          onChange={(e) => onChange({ ...filters, resilientOnly: e.target.checked })}
          className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-emerald-500 focus:ring-emerald-500 focus:ring-offset-0 cursor-pointer"
        />
        <span className="text-sm">Resilient only</span>
      </label>

      {/* Volatility slider */}
      <div className="flex items-center gap-3">
        <span className="text-sm text-slate-400">Max volatility:</span>
        <input
          type="range"
          min="10"
          max="100"
          value={filters.maxVolatility}
          onChange={(e) => onChange({ ...filters, maxVolatility: Number(e.target.value) })}
          className="w-24 h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-emerald-500"
        />
        <span className="text-sm font-medium w-12">
          {filters.maxVolatility}%
        </span>
      </div>
    </div>
  )
}
