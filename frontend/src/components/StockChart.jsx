import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { TrendingUp, Calendar, DollarSign } from 'lucide-react'

export default function StockChart({ stock }) {
  if (!stock) {
    return (
      <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-xl p-6 h-[400px] flex items-center justify-center">
        <div className="text-center text-slate-400">
          <TrendingUp className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>Select a stock to view its chart</p>
        </div>
      </div>
    )
  }

  const chartData = stock.chart_data || []
  const minPrice = Math.min(...chartData.map(d => d.price)) * 0.95
  const maxPrice = Math.max(...chartData.map(d => d.price)) * 1.05

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 shadow-xl">
          <p className="text-slate-400 text-xs mb-1">{label}</p>
          <p className="text-white font-semibold">
            {stock.currency} {payload[0].value.toLocaleString()}
          </p>
        </div>
      )
    }
    return null
  }

  return (
    <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-xl p-6">
      {/* Header */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-xl font-bold">{stock.ticker}</h3>
          <span className={`
            px-3 py-1 rounded-full text-sm font-medium
            ${stock.is_resilient
              ? 'bg-emerald-500/20 text-emerald-400'
              : 'bg-red-500/20 text-red-400'
            }
          `}>
            {stock.is_resilient ? 'Resilient' : 'Not Resilient'}
          </span>
        </div>
        <p className="text-slate-400 text-sm truncate">{stock.name}</p>
      </div>

      {/* Current price */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-slate-700/30 rounded-lg p-3">
          <div className="flex items-center gap-2 text-slate-400 text-sm mb-1">
            <DollarSign className="w-4 h-4" />
            Current Price
          </div>
          <p className="text-2xl font-bold">
            {stock.currency} {stock.current_price?.toLocaleString()}
          </p>
        </div>
        <div className="bg-slate-700/30 rounded-lg p-3">
          <div className="flex items-center gap-2 text-slate-400 text-sm mb-1">
            <Calendar className="w-4 h-4" />
            5Y Performance
          </div>
          <p className={`text-2xl font-bold ${stock.perf_5y >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {stock.perf_5y !== null ? `${stock.perf_5y >= 0 ? '+' : ''}${stock.perf_5y.toFixed(1)}%` : 'N/A'}
          </p>
        </div>
      </div>

      {/* Chart */}
      <div className="h-[200px]">
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <XAxis
                dataKey="date"
                tickFormatter={(d) => d.substring(0, 7)}
                tick={{ fill: '#64748b', fontSize: 10 }}
                axisLine={{ stroke: '#334155' }}
                tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                domain={[minPrice, maxPrice]}
                tick={{ fill: '#64748b', fontSize: 10 }}
                axisLine={{ stroke: '#334155' }}
                tickLine={false}
                tickFormatter={(v) => v.toFixed(0)}
                width={50}
              />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="price"
                stroke="#10b981"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#colorPrice)"
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-full text-slate-400">
            No chart data available
          </div>
        )}
      </div>

      {/* Additional info */}
      {(stock.sector || stock.dividend_yield) && (
        <div className="mt-4 pt-4 border-t border-slate-700">
          <div className="flex flex-wrap gap-4 text-sm">
            {stock.sector && (
              <div>
                <span className="text-slate-400">Sector: </span>
                <span className="text-white">{stock.sector}</span>
              </div>
            )}
            {stock.dividend_yield && (
              <div>
                <span className="text-slate-400">Dividend: </span>
                <span className="text-emerald-400">{stock.dividend_yield.toFixed(2)}%</span>
              </div>
            )}
            <div>
              <span className="text-slate-400">Volatility: </span>
              <span className={stock.volatility > 30 ? 'text-orange-400' : 'text-white'}>
                {stock.volatility?.toFixed(1)}%
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
