import { useState, useEffect } from 'react'
import {
  X, Shield, Bell, Lock, RefreshCw,
  TrendingDown, TrendingUp, AlertTriangle, Target
} from 'lucide-react'

const API_BASE = '/api'

/**
 * StopLossModal - Modal dual-mode pour configurer Stop-Loss et Take-Profit
 *
 * Modes:
 * - "alert": Envoie une notification Telegram quand le prix atteint le niveau
 * - "order": Cree un ordre stop/limit reel sur Saxo Bank
 *
 * Props:
 * - position: { symbol, current_price, uic, asset_type, quantity, average_price }
 * - onClose: () => void
 * - onSuccess: (message: string) => void
 * - onError: (message: string) => void
 * - accountKey: string (pour les ordres Saxo)
 */
export default function StopLossModal({ position, onClose, onSuccess, onError, accountKey }) {
  // Mode: 'alert' (Telegram) ou 'order' (Saxo reel)
  const [mode, setMode] = useState('alert')

  // Configuration SL/TP
  const [config, setConfig] = useState({
    stopLossPercent: 8,
    takeProfitPercent: 24,
    trailingStop: false,
    trailingDistance: 3,
  })

  const [loading, setLoading] = useState(false)

  // Calculs de prix
  const currentPrice = position?.current_price || 0
  const stopLossPrice = currentPrice * (1 - config.stopLossPercent / 100)
  const takeProfitPrice = currentPrice * (1 + config.takeProfitPercent / 100)

  // Calcul du Risk/Reward ratio
  const riskAmount = currentPrice - stopLossPrice
  const rewardAmount = takeProfitPrice - currentPrice
  const rrRatio = riskAmount > 0 ? (rewardAmount / riskAmount).toFixed(2) : 0

  // P&L potentiel
  const quantity = position?.quantity || 1
  const potentialLoss = riskAmount * quantity
  const potentialGain = rewardAmount * quantity

  const handleSubmit = async () => {
    if (!position) return

    setLoading(true)

    try {
      if (mode === 'alert') {
        // Mode Alerte Telegram
        const res = await fetch(`${API_BASE}/saxo/positions/alerts`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            symbol: position.symbol,
            current_price: currentPrice,
            stop_loss_percent: config.stopLossPercent,
            take_profit_percent: config.takeProfitPercent
          })
        })

        const data = await res.json()

        if (res.ok && data.success) {
          // Pass actual SL/TP prices and mode to parent callback
          onSuccess?.(
            `Alertes Telegram creees: SL ${stopLossPrice.toFixed(2)}€, TP ${takeProfitPrice.toFixed(2)}€`,
            stopLossPrice,
            takeProfitPrice,
            'alert'
          )
          onClose()
        } else {
          throw new Error(data.detail || 'Erreur creation alertes')
        }

      } else {
        // Mode Ordre Saxo reel
        const orders = []

        // Creer ordre Stop Loss (vente si prix descend)
        if (config.stopLossPercent > 0) {
          const slOrder = {
            symbol: String(position.uic),
            asset_type: position.asset_type || 'Stock',
            buy_sell: 'Sell',
            quantity: quantity,
            order_type: config.trailingStop ? 'TrailingStop' : 'StopIfTraded',
            price: stopLossPrice,
            account_key: accountKey
          }

          if (config.trailingStop) {
            slOrder.trailing_distance = config.trailingDistance
          }

          orders.push({ type: 'StopLoss', order: slOrder })
        }

        // Creer ordre Take Profit (vente si prix monte)
        if (config.takeProfitPercent > 0) {
          const tpOrder = {
            symbol: String(position.uic),
            asset_type: position.asset_type || 'Stock',
            buy_sell: 'Sell',
            quantity: quantity,
            order_type: 'Limit',
            price: takeProfitPrice,
            account_key: accountKey
          }

          orders.push({ type: 'TakeProfit', order: tpOrder })
        }

        // Envoyer les ordres
        const results = []
        for (const { type, order } of orders) {
          const res = await fetch(`${API_BASE}/saxo/orders`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(order)
          })

          if (!res.ok) {
            const err = await res.json()
            throw new Error(`Erreur ${type}: ${err.detail || 'Echec'}`)
          }

          results.push(type)
        }

        // Pass actual SL/TP prices and mode to parent callback
        onSuccess?.(
          `Ordres Saxo crees: ${results.join(', ')}`,
          stopLossPrice,
          takeProfitPrice,
          'order'
        )
        onClose()
      }

    } catch (err) {
      onError?.(err.message || 'Erreur inconnue')
    } finally {
      setLoading(false)
    }
  }

  if (!position) return null

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 max-w-lg w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex justify-between items-start mb-6">
          <div>
            <h3 className="text-xl font-semibold flex items-center gap-2">
              <Shield className="w-6 h-6 text-yellow-400" />
              Stop-Loss / Take-Profit
            </h3>
            <p className="text-slate-400 mt-1">
              <span className="font-medium text-white">{position.symbol}</span>
              {' '}&bull;{' '}Prix actuel: <span className="font-mono">{currentPrice.toFixed(2)}€</span>
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Mode Toggle */}
        <div className="bg-slate-900/50 rounded-lg p-1 flex gap-1 mb-6">
          <button
            onClick={() => setMode('alert')}
            className={`flex-1 py-2.5 px-4 rounded-md font-medium flex items-center justify-center gap-2 transition-colors ${
              mode === 'alert'
                ? 'bg-yellow-600 text-white'
                : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
            }`}
          >
            <Bell className="w-4 h-4" />
            Alerte Telegram
          </button>
          <button
            onClick={() => setMode('order')}
            className={`flex-1 py-2.5 px-4 rounded-md font-medium flex items-center justify-center gap-2 transition-colors ${
              mode === 'order'
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
            }`}
          >
            <Lock className="w-4 h-4" />
            Ordre Saxo
          </button>
        </div>

        {/* Warning for Order mode */}
        {mode === 'order' && (
          <div className="bg-orange-900/30 border border-orange-700/50 rounded-lg p-3 mb-6 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-orange-400 flex-shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="text-orange-300 font-medium">Ordres reels sur Saxo Bank</p>
              <p className="text-orange-200/70 mt-0.5">
                Les ordres seront executes automatiquement si le prix atteint les niveaux configures.
              </p>
            </div>
          </div>
        )}

        {/* Stop Loss Configuration */}
        <div className="bg-red-900/20 border border-red-800/50 rounded-lg p-4 mb-4">
          <div className="flex justify-between items-center mb-3">
            <div className="flex items-center gap-2">
              <TrendingDown className="w-5 h-5 text-red-400" />
              <label className="font-medium text-red-400">Stop Loss</label>
            </div>
            <div className="text-right">
              <span className="text-red-300 font-mono text-lg">{stopLossPrice.toFixed(2)}€</span>
              <p className="text-red-400/70 text-xs">-{potentialLoss.toFixed(2)}€</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <input
              type="range"
              min="1"
              max="25"
              step="0.5"
              value={config.stopLossPercent}
              onChange={(e) => setConfig({ ...config, stopLossPercent: Number(e.target.value) })}
              className="flex-1 accent-red-500 h-2"
            />
            <div className="flex items-center gap-1 bg-red-900/40 px-3 py-1.5 rounded-lg">
              <span className="text-red-400 font-mono font-semibold">-{config.stopLossPercent}%</span>
            </div>
          </div>
        </div>

        {/* Take Profit Configuration */}
        <div className="bg-emerald-900/20 border border-emerald-800/50 rounded-lg p-4 mb-4">
          <div className="flex justify-between items-center mb-3">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-emerald-400" />
              <label className="font-medium text-emerald-400">Take Profit</label>
            </div>
            <div className="text-right">
              <span className="text-emerald-300 font-mono text-lg">{takeProfitPrice.toFixed(2)}€</span>
              <p className="text-emerald-400/70 text-xs">+{potentialGain.toFixed(2)}€</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <input
              type="range"
              min="5"
              max="100"
              step="1"
              value={config.takeProfitPercent}
              onChange={(e) => setConfig({ ...config, takeProfitPercent: Number(e.target.value) })}
              className="flex-1 accent-emerald-500 h-2"
            />
            <div className="flex items-center gap-1 bg-emerald-900/40 px-3 py-1.5 rounded-lg">
              <span className="text-emerald-400 font-mono font-semibold">+{config.takeProfitPercent}%</span>
            </div>
          </div>
        </div>

        {/* Trailing Stop (Order mode only) */}
        {mode === 'order' && (
          <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4 mb-4">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={config.trailingStop}
                onChange={(e) => setConfig({ ...config, trailingStop: e.target.checked })}
                className="w-5 h-5 rounded bg-slate-700 border-slate-600 text-blue-600 focus:ring-blue-500"
              />
              <div>
                <span className="font-medium text-slate-200">Trailing Stop</span>
                <p className="text-xs text-slate-500">Le stop suit le prix a la hausse</p>
              </div>
            </label>

            {config.trailingStop && (
              <div className="mt-4 pl-8">
                <div className="flex items-center gap-4">
                  <label className="text-sm text-slate-400">Distance:</label>
                  <input
                    type="range"
                    min="1"
                    max="10"
                    step="0.5"
                    value={config.trailingDistance}
                    onChange={(e) => setConfig({ ...config, trailingDistance: Number(e.target.value) })}
                    className="flex-1 accent-blue-500"
                  />
                  <span className="font-mono text-blue-400">{config.trailingDistance}%</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Risk/Reward Summary */}
        <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4 mb-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Target className="w-5 h-5 text-blue-400" />
              <span className="text-slate-300">Risk/Reward Ratio</span>
            </div>
            <div className={`text-lg font-bold ${
              parseFloat(rrRatio) >= 2 ? 'text-emerald-400' :
              parseFloat(rrRatio) >= 1 ? 'text-yellow-400' : 'text-red-400'
            }`}>
              1:{rrRatio}
            </div>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-4 text-sm">
            <div className="text-center">
              <p className="text-red-400">Risque max</p>
              <p className="font-mono text-red-300">-{potentialLoss.toFixed(2)}€</p>
            </div>
            <div className="text-center">
              <p className="text-emerald-400">Gain potentiel</p>
              <p className="font-mono text-emerald-300">+{potentialGain.toFixed(2)}€</p>
            </div>
          </div>
        </div>

        {/* Info text */}
        <p className="text-xs text-slate-500 text-center mb-4">
          {mode === 'alert'
            ? 'Vous recevrez une notification Telegram quand le prix atteint ces niveaux'
            : 'Les ordres seront places sur votre compte Saxo et executes automatiquement'
          }
        </p>

        {/* Buttons */}
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 bg-slate-700 hover:bg-slate-600 text-slate-300 py-3 rounded-lg font-medium transition-colors"
          >
            Annuler
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className={`flex-1 py-3 rounded-lg font-medium flex items-center justify-center gap-2 transition-colors ${
              mode === 'alert'
                ? 'bg-yellow-600 hover:bg-yellow-500 text-white'
                : 'bg-blue-600 hover:bg-blue-500 text-white'
            }`}
          >
            {loading ? (
              <RefreshCw className="w-5 h-5 animate-spin" />
            ) : mode === 'alert' ? (
              <>
                <Bell className="w-5 h-5" />
                Creer Alertes
              </>
            ) : (
              <>
                <Lock className="w-5 h-5" />
                Placer Ordres
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
