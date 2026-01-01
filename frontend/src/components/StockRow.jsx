import { CheckCircle, XCircle, X, AlertTriangle, ShoppingCart } from 'lucide-react'
import PerfBadge from './PerfBadge'

export default function StockRow({ stock, onSelect, onRemove, onTrade, isSelected }) {
  const formatPrice = (price, currency) => {
    const symbols = {
      'USD': '$',
      'EUR': '€',
      'GBP': '£',
      'HKD': 'HK$',
      'JPY': '¥',
      'CNY': '¥'
    }
    const symbol = symbols[currency] || currency + ' '
    return `${symbol}${price?.toLocaleString() || 'N/A'}`
  }

  const highVolatility = stock.volatility > 30

  return (
    <tr
      onClick={() => onSelect(stock)}
      className={`
        border-b border-slate-700/50 cursor-pointer
        ${isSelected
          ? 'bg-emerald-500/10'
          : 'hover:bg-slate-700/30'
        }
      `}
    >
      {/* Status */}
      <td className="px-4 py-3">
        {stock.is_resilient ? (
          <CheckCircle className="w-5 h-5 text-emerald-500" />
        ) : (
          <XCircle className="w-5 h-5 text-red-500" />
        )}
      </td>

      {/* Ticker & Name */}
      <td className="px-4 py-3">
        <div className="font-semibold text-white">{stock.ticker}</div>
        <div className="text-sm text-slate-400 truncate max-w-[200px]" title={stock.name}>
          {stock.name}
        </div>
      </td>

      {/* Price */}
      <td className="px-4 py-3 text-right">
        <div className="font-medium">{formatPrice(stock.current_price, stock.currency)}</div>
      </td>

      {/* Performances */}
      <td className="px-2 py-3">
        <PerfBadge value={stock.perf_3m} label="3M" />
      </td>
      <td className="px-2 py-3">
        <PerfBadge value={stock.perf_6m} label="6M" />
      </td>
      <td className="px-2 py-3">
        <PerfBadge value={stock.perf_1y} label="1Y" />
      </td>
      <td className="px-2 py-3">
        <PerfBadge value={stock.perf_3y} label="3Y" />
      </td>
      <td className="px-2 py-3">
        <PerfBadge value={stock.perf_5y} label="5Y" />
      </td>

      {/* Volatility */}
      <td className="px-4 py-3 text-center">
        <span className={`
          inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium
          ${highVolatility
            ? 'bg-orange-500/20 text-orange-400'
            : 'bg-slate-700/50 text-slate-400'
          }
        `}>
          {highVolatility && <AlertTriangle className="w-3 h-3" />}
          {stock.volatility?.toFixed(1)}%
        </span>
      </td>

      {/* Dividend */}
      <td className="px-4 py-3 text-center">
        {stock.dividend_yield ? (
          <span className="text-emerald-400 font-medium">
            {stock.dividend_yield.toFixed(2)}%
          </span>
        ) : (
          <span className="text-slate-500">-</span>
        )}
      </td>

      {/* Trade Button */}
      <td className="px-2 py-3">
        {onTrade && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              onTrade(stock)
            }}
            className="bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1 transition-colors"
            title={`Trader ${stock.ticker}`}
          >
            <ShoppingCart className="w-3.5 h-3.5" />
            Trader
          </button>
        )}
      </td>

      {/* Remove */}
      <td className="px-4 py-3">
        <button
          onClick={(e) => {
            e.stopPropagation()
            onRemove(stock.ticker)
          }}
          className="text-slate-500 hover:text-red-400 p-1"
        >
          <X className="w-4 h-4" />
        </button>
      </td>
    </tr>
  )
}
