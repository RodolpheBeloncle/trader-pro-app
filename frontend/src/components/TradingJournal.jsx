import { useState, useEffect, useCallback } from 'react'
import {
  BookOpen, RefreshCw, TrendingUp, TrendingDown,
  Target, Clock, CheckCircle, XCircle, AlertCircle,
  DollarSign, Percent, BarChart3, Play, Square, Trash2
} from 'lucide-react'

const API_BASE = '/api'

// Status badge colors
const STATUS_CONFIG = {
  planned: { label: 'Planifie', color: 'bg-yellow-600/20 text-yellow-400 border-yellow-600/30', icon: Clock },
  active: { label: 'Actif', color: 'bg-blue-600/20 text-blue-400 border-blue-600/30', icon: Play },
  closed: { label: 'Cloture', color: 'bg-slate-600/20 text-slate-400 border-slate-600/30', icon: CheckCircle },
  cancelled: { label: 'Annule', color: 'bg-red-600/20 text-red-400 border-red-600/30', icon: XCircle }
}

export default function TradingJournal() {
  const [trades, setTrades] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [statusFilter, setStatusFilter] = useState('all')
  const [selectedTrade, setSelectedTrade] = useState(null)
  const [actionModal, setActionModal] = useState({ show: false, trade: null, action: null })
  const [actionForm, setActionForm] = useState({ exit_price: '', exit_reason: '' })

  // Load trades and stats
  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const [tradesRes, statsRes] = await Promise.all([
        fetch(`${API_BASE}/journal/trades?limit=100`),
        fetch(`${API_BASE}/journal/stats`)
      ])

      if (tradesRes.ok) {
        const tradesData = await tradesRes.json()
        setTrades(tradesData)
      }

      if (statsRes.ok) {
        const statsData = await statsRes.json()
        setStats(statsData)
      }
    } catch (err) {
      setError('Erreur de chargement du journal')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  // Activate a planned trade
  const activateTrade = async (tradeId, actualEntryPrice) => {
    try {
      setError(null)
      const res = await fetch(`${API_BASE}/journal/trades/${tradeId}/activate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          actual_entry_price: actualEntryPrice || undefined
        })
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        const errMsg = errData.detail || errData.message || `Erreur HTTP ${res.status}`
        throw new Error(typeof errMsg === 'string' ? errMsg : JSON.stringify(errMsg))
      }

      setSuccess('Trade active!')
      setTimeout(() => setSuccess(null), 3000)
      loadData()
    } catch (err) {
      const errorMessage = err.message || String(err)
      setError(errorMessage)
      console.error('Activate trade error:', err)
    }
  }

  // Close an active trade
  const closeTrade = async (tradeId, exitPrice, exitReason) => {
    try {
      setError(null)
      const res = await fetch(`${API_BASE}/journal/trades/${tradeId}/close`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          exit_price: parseFloat(exitPrice),
          exit_reason: exitReason || 'manual'
        })
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        const errMsg = errData.detail || errData.message || `Erreur HTTP ${res.status}`
        throw new Error(typeof errMsg === 'string' ? errMsg : JSON.stringify(errMsg))
      }

      setSuccess('Trade cloture!')
      setTimeout(() => setSuccess(null), 3000)
      setActionModal({ show: false, trade: null, action: null })
      loadData()
    } catch (err) {
      const errorMessage = err.message || String(err)
      setError(errorMessage)
      console.error('Close trade error:', err)
    }
  }

  // Cancel a planned trade
  const cancelTrade = async (tradeId) => {
    try {
      setError(null)
      const res = await fetch(`${API_BASE}/journal/trades/${tradeId}/cancel`, {
        method: 'POST'
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        const errMsg = errData.detail || errData.message || `Erreur HTTP ${res.status}`
        throw new Error(typeof errMsg === 'string' ? errMsg : JSON.stringify(errMsg))
      }

      setSuccess('Trade annule!')
      setTimeout(() => setSuccess(null), 3000)
      loadData()
    } catch (err) {
      const errorMessage = err.message || String(err)
      setError(errorMessage)
      console.error('Cancel trade error:', err)
    }
  }

  // Delete a trade permanently
  const deleteTrade = async (tradeId, ticker) => {
    if (!confirm(`Supprimer definitivement le trade ${ticker} ?`)) {
      return
    }

    try {
      setError(null)
      const res = await fetch(`${API_BASE}/journal/trades/${tradeId}`, {
        method: 'DELETE'
      })

      if (!res.ok && res.status !== 204) {
        const errData = await res.json().catch(() => ({}))
        const errMsg = errData.detail || errData.message || `Erreur HTTP ${res.status}`
        throw new Error(typeof errMsg === 'string' ? errMsg : JSON.stringify(errMsg))
      }

      setSuccess('Trade supprime!')
      setTimeout(() => setSuccess(null), 3000)
      loadData()
    } catch (err) {
      const errorMessage = err.message || String(err)
      setError(errorMessage)
      console.error('Delete trade error:', err)
    }
  }

  // Filter trades
  const filteredTrades = trades.filter(t =>
    statusFilter === 'all' || t.status === statusFilter
  )

  // Count by status
  const countByStatus = {
    all: trades.length,
    planned: trades.filter(t => t.status === 'planned').length,
    active: trades.filter(t => t.status === 'active').length,
    closed: trades.filter(t => t.status === 'closed').length,
  }

  if (loading && trades.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-purple-600 rounded-lg flex items-center justify-center">
            <BookOpen className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-semibold">Journal de Trading</h2>
            <p className="text-sm text-slate-400">
              {trades.length} trades enregistres
            </p>
          </div>
        </div>
        <button
          onClick={loadData}
          disabled={loading}
          className="bg-slate-700/50 hover:bg-slate-600/50 p-2 rounded-lg"
        >
          <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Messages */}
      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4">
          <p className="text-red-400">{error}</p>
        </div>
      )}
      {success && (
        <div className="bg-emerald-900/30 border border-emerald-700 rounded-lg p-4">
          <p className="text-emerald-400">{success}</p>
        </div>
      )}

      {/* Stats Summary */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
            <div className="flex items-center gap-2 text-sm text-slate-400 mb-1">
              <BarChart3 className="w-4 h-4" />
              Total Trades
            </div>
            <p className="text-2xl font-bold">{stats.total_trades || 0}</p>
          </div>

          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
            <div className="flex items-center gap-2 text-sm text-slate-400 mb-1">
              <Percent className="w-4 h-4" />
              Win Rate
            </div>
            <p className={`text-2xl font-bold ${
              (stats.win_rate || 0) >= 50 ? 'text-emerald-400' : 'text-red-400'
            }`}>
              {(stats.win_rate || 0).toFixed(1)}%
            </p>
          </div>

          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
            <div className="flex items-center gap-2 text-sm text-slate-400 mb-1">
              <DollarSign className="w-4 h-4" />
              P&L Total
            </div>
            <p className={`text-2xl font-bold ${
              (stats.total_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
            }`}>
              {(stats.total_pnl || 0) >= 0 ? '+' : ''}{(stats.total_pnl || 0).toFixed(2)}
            </p>
          </div>

          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
            <div className="flex items-center gap-2 text-sm text-slate-400 mb-1">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
              Gagnants
            </div>
            <p className="text-2xl font-bold text-emerald-400">{stats.winners || 0}</p>
          </div>

          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
            <div className="flex items-center gap-2 text-sm text-slate-400 mb-1">
              <TrendingDown className="w-4 h-4 text-red-400" />
              Perdants
            </div>
            <p className="text-2xl font-bold text-red-400">{stats.losers || 0}</p>
          </div>
        </div>
      )}

      {/* Status Filter */}
      <div className="flex gap-2">
        {[
          { id: 'all', label: 'Tous' },
          { id: 'planned', label: 'Planifies' },
          { id: 'active', label: 'Actifs' },
          { id: 'closed', label: 'Clotures' }
        ].map(filter => (
          <button
            key={filter.id}
            onClick={() => setStatusFilter(filter.id)}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              statusFilter === filter.id
                ? 'bg-purple-600 text-white'
                : 'bg-slate-700/50 text-slate-300 hover:bg-slate-600/50'
            }`}
          >
            {filter.label}
            <span className="ml-2 text-xs bg-white/20 px-2 py-0.5 rounded-full">
              {countByStatus[filter.id]}
            </span>
          </button>
        ))}
      </div>

      {/* Trades List */}
      {filteredTrades.length === 0 ? (
        <div className="bg-slate-800/30 border border-slate-700 rounded-xl p-8 text-center">
          <BookOpen className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400">Aucun trade {statusFilter !== 'all' ? statusFilter : ''}</p>
          <p className="text-slate-500 text-sm mt-2">
            Utilisez Claude Desktop pour planifier des trades via MCP
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredTrades.map(trade => {
            const statusConfig = STATUS_CONFIG[trade.status] || STATUS_CONFIG.planned
            const StatusIcon = statusConfig.icon
            const isWinner = trade.pnl && trade.pnl > 0
            const isLoser = trade.pnl && trade.pnl < 0

            return (
              <div
                key={trade.id}
                className="bg-slate-800/50 border border-slate-700 rounded-xl p-4 hover:border-slate-600 transition-colors"
              >
                <div className="flex items-start justify-between">
                  {/* Left: Trade info */}
                  <div className="flex items-start gap-4">
                    {/* Direction indicator */}
                    <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                      trade.direction === 'long'
                        ? 'bg-emerald-600/20 text-emerald-400'
                        : 'bg-red-600/20 text-red-400'
                    }`}>
                      {trade.direction === 'long'
                        ? <TrendingUp className="w-6 h-6" />
                        : <TrendingDown className="w-6 h-6" />
                      }
                    </div>

                    {/* Trade details */}
                    <div>
                      <div className="flex items-center gap-3">
                        <span className="text-lg font-semibold">{trade.ticker}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${statusConfig.color}`}>
                          <StatusIcon className="w-3 h-3 inline mr-1" />
                          {statusConfig.label}
                        </span>
                        <span className={`text-xs px-2 py-0.5 rounded ${
                          trade.direction === 'long' ? 'bg-emerald-600/20 text-emerald-400' : 'bg-red-600/20 text-red-400'
                        }`}>
                          {trade.direction?.toUpperCase()}
                        </span>
                      </div>

                      <div className="flex items-center gap-4 mt-2 text-sm">
                        <span className="text-slate-400">
                          Entree: <span className="text-white font-mono">${trade.entry_price?.toFixed(2)}</span>
                        </span>
                        <span className="text-red-400">
                          SL: <span className="font-mono">${trade.stop_loss?.toFixed(2)}</span>
                        </span>
                        <span className="text-emerald-400">
                          TP: <span className="font-mono">${trade.take_profit?.toFixed(2)}</span>
                        </span>
                        <span className="text-slate-400">
                          Taille: <span className="text-white">{trade.position_size}</span>
                        </span>
                      </div>

                      {/* R/R and P&L */}
                      <div className="flex items-center gap-4 mt-2 text-sm">
                        <span className="text-blue-400">
                          <Target className="w-3 h-3 inline mr-1" />
                          R/R: 1:{trade.risk_reward_ratio?.toFixed(2) || 'N/A'}
                        </span>
                        {trade.pnl !== null && trade.pnl !== undefined && (
                          <span className={isWinner ? 'text-emerald-400' : isLoser ? 'text-red-400' : 'text-slate-400'}>
                            <DollarSign className="w-3 h-3 inline" />
                            P&L: {trade.pnl >= 0 ? '+' : ''}{trade.pnl?.toFixed(2)}
                          </span>
                        )}
                      </div>

                      {/* Created date */}
                      <p className="text-xs text-slate-500 mt-2">
                        Cree le {new Date(trade.created_at).toLocaleDateString('fr-FR', {
                          day: 'numeric',
                          month: 'short',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </p>
                    </div>
                  </div>

                  {/* Right: Actions */}
                  <div className="flex items-center gap-2">
                    {trade.status === 'planned' && (
                      <>
                        <button
                          onClick={() => activateTrade(trade.id)}
                          className="bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 px-3 py-1.5 rounded-lg text-sm flex items-center gap-1"
                          title="Activer le trade"
                        >
                          <Play className="w-4 h-4" />
                          Activer
                        </button>
                        <button
                          onClick={() => cancelTrade(trade.id)}
                          className="bg-red-600/20 hover:bg-red-600/40 text-red-400 p-1.5 rounded-lg"
                          title="Annuler"
                        >
                          <XCircle className="w-4 h-4" />
                        </button>
                      </>
                    )}
                    {trade.status === 'active' && (
                      <button
                        onClick={() => {
                          setActionModal({ show: true, trade, action: 'close' })
                          setActionForm({ exit_price: '', exit_reason: 'manual' })
                        }}
                        className="bg-orange-600/20 hover:bg-orange-600/40 text-orange-400 px-3 py-1.5 rounded-lg text-sm flex items-center gap-1"
                        title="Cloturer le trade"
                      >
                        <Square className="w-4 h-4" />
                        Cloturer
                      </button>
                    )}
                    {/* Delete button for non-active trades */}
                    {trade.status !== 'active' && (
                      <button
                        onClick={() => deleteTrade(trade.id, trade.ticker)}
                        className="bg-slate-600/20 hover:bg-red-600/40 text-slate-400 hover:text-red-400 p-1.5 rounded-lg transition-colors"
                        title="Supprimer definitivement"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Close Trade Modal */}
      {actionModal.show && actionModal.action === 'close' && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 max-w-md w-full">
            <h3 className="text-lg font-semibold mb-4">Cloturer le trade {actionModal.trade?.ticker}</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-2">Prix de sortie</label>
                <input
                  type="number"
                  step="0.01"
                  value={actionForm.exit_price}
                  onChange={(e) => setActionForm({ ...actionForm, exit_price: e.target.value })}
                  placeholder={`Entree: ${actionModal.trade?.entry_price?.toFixed(2)}`}
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2"
                />
              </div>

              <div>
                <label className="block text-sm text-slate-400 mb-2">Raison de sortie</label>
                <select
                  value={actionForm.exit_reason}
                  onChange={(e) => setActionForm({ ...actionForm, exit_reason: e.target.value })}
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2"
                >
                  <option value="manual">Sortie manuelle</option>
                  <option value="stop_loss">Stop Loss atteint</option>
                  <option value="take_profit">Take Profit atteint</option>
                  <option value="trailing_stop">Trailing Stop</option>
                  <option value="time_exit">Sortie temps</option>
                </select>
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setActionModal({ show: false, trade: null, action: null })}
                className="flex-1 bg-slate-700 hover:bg-slate-600 py-2 rounded-lg"
              >
                Annuler
              </button>
              <button
                onClick={() => closeTrade(
                  actionModal.trade.id,
                  actionForm.exit_price,
                  actionForm.exit_reason
                )}
                disabled={!actionForm.exit_price}
                className="flex-1 bg-orange-600 hover:bg-orange-500 disabled:opacity-50 py-2 rounded-lg"
              >
                Cloturer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
