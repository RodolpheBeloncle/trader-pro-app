import { useState, useEffect, useCallback } from 'react'
import {
  Wallet, RefreshCw, TrendingUp, TrendingDown,
  AlertCircle, ExternalLink, LogOut,
  History, ShoppingCart, Search, X, Bell, Shield
} from 'lucide-react'

const API_BASE = '/api'

// Sub-tabs
const TABS = [
  { id: 'portfolio', label: 'Portefeuille', icon: Wallet },
  { id: 'trade', label: 'Trading', icon: TrendingUp },
  { id: 'orders', label: 'Ordres', icon: ShoppingCart },
  { id: 'history', label: 'Historique', icon: History }
]

export default function SaxoPortfolio({ initialTicker, oauthResult, onOauthResultHandled }) {
  // Connection state
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)

  // Data state
  const [portfolio, setPortfolio] = useState(null)
  const [orders, setOrders] = useState([])
  const [history, setHistory] = useState([])
  const [activeTab, setActiveTab] = useState(initialTicker ? 'trade' : 'portfolio')

  // Trading state
  const [searchQuery, setSearchQuery] = useState(initialTicker || '')
  const [searchResults, setSearchResults] = useState([])
  const [selectedInstrument, setSelectedInstrument] = useState(null)
  const [orderForm, setOrderForm] = useState({
    quantity: 1,
    orderType: 'Market',
    buySell: 'Buy',
    price: ''
  })
  const [initialTickerProcessed, setInitialTickerProcessed] = useState(false)

  // Alert modal state
  const [alertModal, setAlertModal] = useState({ show: false, position: null })
  const [alertForm, setAlertForm] = useState({ stopLoss: 8, takeProfit: 24 })

  // Check status on mount
  // Note: OAuth callback is handled by App.jsx and passed via oauthResult prop
  useEffect(() => {
    // Ne pas traiter le callback ici - c'est fait par App.jsx
    // Juste vérifier le statut
    checkStatus()
  }, [])

  // Handle OAuth result from parent
  useEffect(() => {
    if (oauthResult) {
      if (oauthResult.success) {
        setSuccess('Connexion reussie!')
        setTimeout(() => setSuccess(null), 3000)
        checkStatus()
      } else if (oauthResult.error) {
        setError(oauthResult.error)
      }
      onOauthResultHandled?.()
    }
  }, [oauthResult])

  // Auto-search when initialTicker is provided and connected
  useEffect(() => {
    if (initialTicker && status?.connected && !initialTickerProcessed) {
      setInitialTickerProcessed(true)
      setActiveTab('trade')
      setSearchQuery(initialTicker)
      // Auto-trigger search
      searchInstrumentsWithQuery(initialTicker)
    }
  }, [initialTicker, status?.connected, initialTickerProcessed])

  // Load portfolio when connected
  useEffect(() => {
    if (status?.connected) {
      loadPortfolio()
    }
  }, [status?.connected])

  // ==========================================================================
  // API CALLS
  // ==========================================================================

  const checkStatus = async () => {
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/saxo/status`)
      const data = await res.json()
      setStatus(data)
      setError(null)
    } catch (err) {
      setError('Erreur de connexion au serveur')
    } finally {
      setLoading(false)
    }
  }

  const connect = async () => {
    try {
      setLoading(true)
      setError(null)

      // Recuperer l'URL OAuth
      const res = await fetch(`${API_BASE}/saxo/auth/url`)
      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || 'Erreur connexion OAuth')
      }

      // Rediriger vers Saxo OAuth
      window.location.href = data.auth_url

    } catch (err) {
      setError(err.message || 'Impossible de se connecter')
      setLoading(false)
    }
  }

  const disconnect = async () => {
    try {
      await fetch(`${API_BASE}/saxo/disconnect`, { method: 'POST' })
      setStatus({ ...status, connected: false })
      setPortfolio(null)
      setOrders([])
      setHistory([])
    } catch (err) {
      setError('Erreur de deconnexion')
    }
  }

  const loadPortfolio = async () => {
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/saxo/portfolio`)

      if (res.status === 401) {
        setStatus({ ...status, connected: false })
        setError('Session expiree. Reconnectez-vous.')
        return
      }

      if (!res.ok) throw new Error('Erreur chargement')

      const data = await res.json()
      console.log('Portfolio data received:', data)

      // Debug: verifier si les positions ont des prix
      if (data.positions && data.positions.length > 0) {
        const sample = data.positions[0]
        console.log('Sample position:', sample)
        if (!sample.current_price && !sample.market_value) {
          console.warn('Position sans prix - verifier API Saxo')
        }
      }

      setPortfolio(data)
      setError(null)
    } catch (err) {
      console.error('Portfolio load error:', err)
      setError('Echec du chargement du portefeuille')
    } finally {
      setLoading(false)
    }
  }

  const loadOrders = async () => {
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/saxo/orders`)
      if (res.status === 401) {
        setStatus({ ...status, connected: false })
        return
      }
      const data = await res.json()
      setOrders(data.orders || [])
    } catch (err) {
      setError('Erreur chargement ordres')
    } finally {
      setLoading(false)
    }
  }

  const loadHistory = async () => {
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/saxo/history?days=30`)
      if (res.status === 401) {
        setStatus({ ...status, connected: false })
        return
      }
      const data = await res.json()
      setHistory(data.transactions || [])
    } catch (err) {
      setError('Erreur chargement historique')
    } finally {
      setLoading(false)
    }
  }

  const searchInstruments = async () => {
    if (!searchQuery.trim()) return
    await searchInstrumentsWithQuery(searchQuery)
  }

  const searchInstrumentsWithQuery = async (query) => {
    if (!query?.trim()) return

    try {
      setLoading(true)
      const res = await fetch(
        `${API_BASE}/saxo/search?query=${encodeURIComponent(query)}&asset_types=Stock,Etf`
      )
      if (res.status === 401) {
        setStatus({ ...status, connected: false })
        return
      }
      const data = await res.json()
      const results = data.results || []
      setSearchResults(results)

      // Si c'est une recherche automatique avec initialTicker et qu'on a un résultat exact, le sélectionner
      if (initialTicker && results.length > 0) {
        // Chercher un match exact sur le symbole
        const exactMatch = results.find(
          r => r.symbol?.toUpperCase() === query.toUpperCase()
        )
        if (exactMatch) {
          setSelectedInstrument(exactMatch)
          setSearchResults([])
          setSearchQuery('')
        }
      }
    } catch (err) {
      setError('Erreur recherche')
    } finally {
      setLoading(false)
    }
  }

  const placeOrder = async () => {
    if (!selectedInstrument || !portfolio?.account_key) return

    try {
      setLoading(true)
      setError(null)

      const orderData = {
        symbol: String(selectedInstrument.uic),
        asset_type: selectedInstrument.asset_type || 'Stock',
        buy_sell: orderForm.buySell,
        quantity: parseInt(orderForm.quantity, 10),
        order_type: orderForm.orderType,
        account_key: portfolio.account_key
      }

      if (orderForm.orderType === 'Limit' && orderForm.price) {
        orderData.price = parseFloat(orderForm.price)
      }

      const res = await fetch(`${API_BASE}/saxo/orders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(orderData)
      })

      if (res.status === 401) {
        setStatus({ ...status, connected: false })
        return
      }

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Erreur')
      }

      setSuccess(`Ordre ${orderForm.buySell} place!`)
      setTimeout(() => setSuccess(null), 3000)
      setSelectedInstrument(null)
      setOrderForm({ quantity: 1, orderType: 'Market', buySell: 'Buy', price: '' })
      loadOrders()
      loadPortfolio()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const cancelOrder = async (orderId, accountKey) => {
    try {
      const res = await fetch(
        `${API_BASE}/saxo/orders/${orderId}?account_key=${accountKey}`,
        { method: 'DELETE' }
      )
      if (res.ok) {
        setSuccess('Ordre annule')
        setTimeout(() => setSuccess(null), 3000)
        loadOrders()
      }
    } catch (err) {
      setError('Erreur annulation')
    }
  }

  const handleTabChange = (tabId) => {
    setActiveTab(tabId)
    if (tabId === 'orders') loadOrders()
    if (tabId === 'history') loadHistory()
  }

  const createPositionAlerts = async () => {
    if (!alertModal.position) return

    try {
      setLoading(true)
      setError(null)

      const res = await fetch(`${API_BASE}/saxo/positions/alerts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: alertModal.position.symbol,
          current_price: alertModal.position.current_price,
          stop_loss_percent: alertForm.stopLoss,
          take_profit_percent: alertForm.takeProfit
        })
      })

      const data = await res.json()

      if (res.ok && data.success) {
        setSuccess(`Alertes creees: SL a ${data.stop_loss_price}€, TP a ${data.take_profit_price}€`)
        setTimeout(() => setSuccess(null), 5000)
        setAlertModal({ show: false, position: null })
      } else {
        throw new Error(data.detail || 'Erreur creation alertes')
      }
    } catch (err) {
      setError(err.message || 'Erreur creation alertes')
    } finally {
      setLoading(false)
    }
  }

  // ==========================================================================
  // RENDER - Loading
  // ==========================================================================
  if (loading && !status) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    )
  }

  // ==========================================================================
  // RENDER - Not configured
  // ==========================================================================
  if (status && !status.configured) {
    return (
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-8 text-center">
        <AlertCircle className="w-16 h-16 text-yellow-500 mx-auto mb-4" />
        <h3 className="text-xl font-semibold mb-2">Configuration Saxo requise</h3>
        <p className="text-slate-400 mb-4">
          Configurez les variables d'environnement:
        </p>
        <pre className="bg-slate-900 rounded-lg p-4 text-left text-sm mb-4 inline-block">
          <code className="text-emerald-400">
            SAXO_APP_KEY=votre_app_key{'\n'}
            SAXO_APP_SECRET=votre_app_secret
          </code>
        </pre>
        <div>
          <a
            href="https://www.developer.saxo/openapi/appmanagement"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 text-blue-400 hover:text-blue-300"
          >
            Creer une app Saxo <ExternalLink className="w-4 h-4" />
          </a>
        </div>
      </div>
    )
  }

  // ==========================================================================
  // RENDER - Not connected
  // ==========================================================================
  if (status && !status.connected) {
    return (
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-8 text-center">
        <Wallet className="w-16 h-16 text-blue-500 mx-auto mb-4" />
        <h3 className="text-xl font-semibold mb-2">Connecter Saxo Trader</h3>

        {status.environment && (
          <div className="mb-4">
            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${
              status.environment === 'LIVE'
                ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-600/30'
                : 'bg-yellow-600/20 text-yellow-400 border border-yellow-600/30'
            }`}>
              {status.environment === 'LIVE' ? 'Production' : 'Simulation'}
            </span>
          </div>
        )}

        <p className="text-slate-400 mb-4">
          Connectez-vous via OAuth pour acceder a votre portefeuille
        </p>

        {error && (
          <div className="bg-red-900/30 border border-red-700 rounded-lg p-3 mb-4 max-w-md mx-auto">
            <p className="text-red-400 text-sm">{error}</p>
          </div>
        )}

        {success && (
          <div className="bg-emerald-900/30 border border-emerald-700 rounded-lg p-3 mb-4 max-w-md mx-auto">
            <p className="text-emerald-400 text-sm">{success}</p>
          </div>
        )}

        <button
          onClick={connect}
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-6 py-3 rounded-lg font-medium inline-flex items-center gap-2"
        >
          {loading ? (
            <RefreshCw className="w-5 h-5 animate-spin" />
          ) : (
            <Wallet className="w-5 h-5" />
          )}
          Connexion OAuth
        </button>
      </div>
    )
  }

  // ==========================================================================
  // RENDER - Connected
  // ==========================================================================
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
            <Wallet className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-semibold">Saxo Portfolio</h2>
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                status?.environment === 'LIVE'
                  ? 'bg-emerald-600/20 text-emerald-400'
                  : 'bg-yellow-600/20 text-yellow-400'
              }`}>
                {status?.environment === 'LIVE' ? 'PROD' : 'DEMO'}
              </span>
            </div>
            <p className="text-sm text-slate-400">Connecte</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={async () => {
              try {
                const res = await fetch(`${API_BASE}/saxo/debug/portfolio-raw`)
                const data = await res.json()
                console.log('=== DEBUG PORTFOLIO RAW ===', data)
                alert(`Debug: ${data.positions_count || 0} positions. Voir console (F12)`)
              } catch (e) {
                console.error('Debug error:', e)
                alert('Erreur debug - Voir console')
              }
            }}
            className="bg-purple-600/20 hover:bg-purple-600/40 text-purple-400 p-2 rounded-lg"
            title="Debug donnees brutes"
          >
            <Search className="w-5 h-5" />
          </button>
          <button
            onClick={async () => {
              try {
                const res = await fetch(`${API_BASE}/saxo/test/telegram`, { method: 'POST' })
                const data = await res.json()
                if (data.success) {
                  setSuccess('Notification Telegram envoyee!')
                  setTimeout(() => setSuccess(null), 3000)
                } else {
                  setError(data.error || 'Echec envoi Telegram')
                }
              } catch (e) {
                setError('Erreur test Telegram')
              }
            }}
            className="bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 p-2 rounded-lg"
            title="Tester Telegram"
          >
            <Bell className="w-5 h-5" />
          </button>
          <button
            onClick={loadPortfolio}
            disabled={loading}
            className="bg-slate-700/50 hover:bg-slate-600/50 p-2 rounded-lg"
            title="Rafraichir"
          >
            <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={disconnect}
            className="bg-red-600/20 hover:bg-red-600/30 text-red-400 p-2 rounded-lg"
            title="Deconnecter"
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>
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

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-700 pb-2">
        {TABS.map(tab => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => handleTabChange(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-700/50 text-slate-300 hover:bg-slate-600/50'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Portfolio Tab */}
      {activeTab === 'portfolio' && portfolio && (
        <div className="space-y-6">
          {/* Account Balance Banner */}
          {(portfolio.summary.cash_available != null || portfolio.summary.total_account_value != null) && (
            <div className="bg-gradient-to-r from-blue-900/40 to-purple-900/40 border border-blue-700/50 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-6">
                  {portfolio.summary.cash_available != null && (
                    <div>
                      <p className="text-xs text-blue-300 uppercase tracking-wide">Cash disponible</p>
                      <p className="text-xl font-bold text-white">
                        {portfolio.summary.cash_available.toLocaleString('fr-FR', {
                          style: 'currency',
                          currency: portfolio.summary.currency || 'EUR'
                        })}
                      </p>
                    </div>
                  )}
                  {portfolio.summary.total_account_value != null && (
                    <div className="border-l border-blue-700/50 pl-6">
                      <p className="text-xs text-purple-300 uppercase tracking-wide">Valeur compte total</p>
                      <p className="text-xl font-bold text-white">
                        {portfolio.summary.total_account_value.toLocaleString('fr-FR', {
                          style: 'currency',
                          currency: portfolio.summary.currency || 'EUR'
                        })}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
              <p className="text-sm text-slate-400">Positions</p>
              <p className="text-2xl font-bold">{portfolio.summary.total_positions}</p>
            </div>
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
              <p className="text-sm text-slate-400">Valeur positions</p>
              <p className="text-2xl font-bold">
                {portfolio.summary.total_value.toLocaleString('fr-FR', {
                  style: 'currency',
                  currency: portfolio.summary.currency || 'EUR'
                })}
              </p>
            </div>
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
              <p className="text-sm text-slate-400">P&L Total</p>
              <p className={`text-2xl font-bold ${
                portfolio.summary.total_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'
              }`}>
                {portfolio.summary.total_pnl >= 0 ? '+' : ''}
                {portfolio.summary.total_pnl.toLocaleString('fr-FR', {
                  style: 'currency',
                  currency: portfolio.summary.currency || 'EUR'
                })}
              </p>
            </div>
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
              <p className="text-sm text-slate-400">P&L %</p>
              <p className={`text-2xl font-bold ${
                portfolio.summary.total_pnl_percent >= 0 ? 'text-emerald-400' : 'text-red-400'
              }`}>
                {portfolio.summary.total_pnl_percent >= 0 ? '+' : ''}
                {portfolio.summary.total_pnl_percent.toFixed(2)}%
              </p>
            </div>
          </div>

          {/* Positions */}
          {portfolio.positions.length > 0 ? (
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden overflow-x-auto">
              <table className="w-full min-w-[900px]">
                <thead className="bg-slate-900/50">
                  <tr>
                    <th className="text-left p-3 text-sm font-medium text-slate-400">Position</th>
                    <th className="text-right p-3 text-sm font-medium text-slate-400">Qte</th>
                    <th className="text-right p-3 text-sm font-medium text-slate-400">PRU</th>
                    <th className="text-right p-3 text-sm font-medium text-slate-400">Prix</th>
                    <th className="text-right p-3 text-sm font-medium text-slate-400">Valeur</th>
                    <th className="text-right p-3 text-sm font-medium text-slate-400">P&L</th>
                    <th className="text-center p-3 text-sm font-medium text-slate-400">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {portfolio.positions.map((pos, idx) => (
                    <tr key={idx} className="border-t border-slate-700/50 hover:bg-slate-700/20">
                      <td className="p-3">
                        <span className="font-semibold text-white">{pos.symbol}</span>
                        <p className="text-xs text-slate-500 truncate max-w-[180px]">{pos.description}</p>
                      </td>
                      <td className="text-right p-3 font-mono">{pos.quantity}</td>
                      <td className="text-right p-3 font-mono text-slate-400">
                        {pos.average_price?.toLocaleString('fr-FR', {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2
                        })}
                      </td>
                      <td className="text-right p-3 font-mono font-semibold">
                        {pos.current_price?.toLocaleString('fr-FR', {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2
                        })}
                      </td>
                      <td className="text-right p-3 font-mono">
                        {pos.market_value?.toLocaleString('fr-FR', {
                          style: 'currency',
                          currency: pos.currency || 'EUR'
                        })}
                      </td>
                      <td className="text-right p-3">
                        <div className={`font-semibold ${pos.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {pos.pnl >= 0 ? '+' : ''}{pos.pnl?.toLocaleString('fr-FR', {
                            style: 'currency',
                            currency: pos.currency || 'EUR'
                          })}
                        </div>
                        <div className={`text-xs ${pos.pnl_percent >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                          {pos.pnl_percent >= 0 ? '+' : ''}{pos.pnl_percent?.toFixed(2)}%
                        </div>
                      </td>
                      <td className="text-center p-3">
                        <div className="flex items-center justify-center gap-1">
                          <button
                            onClick={() => setAlertModal({ show: true, position: pos })}
                            className="bg-yellow-600/20 hover:bg-yellow-600/40 text-yellow-400 p-1.5 rounded"
                            title="Configurer alertes SL/TP"
                          >
                            <Bell className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => {
                              setSelectedInstrument({
                                uic: pos.uic,
                                symbol: pos.symbol,
                                description: pos.description,
                                asset_type: pos.asset_type
                              })
                              setOrderForm({ ...orderForm, buySell: 'Buy' })
                              setActiveTab('trade')
                            }}
                            className="bg-emerald-600/20 hover:bg-emerald-600/40 text-emerald-400 px-2 py-1 rounded text-xs"
                          >
                            +
                          </button>
                          <button
                            onClick={() => {
                              setSelectedInstrument({
                                uic: pos.uic,
                                symbol: pos.symbol,
                                description: pos.description,
                                asset_type: pos.asset_type
                              })
                              setOrderForm({ ...orderForm, buySell: 'Sell' })
                              setActiveTab('trade')
                            }}
                            className="bg-red-600/20 hover:bg-red-600/40 text-red-400 px-2 py-1 rounded text-xs"
                          >
                            -
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="bg-slate-800/30 border border-slate-700 rounded-xl p-8 text-center">
              <Wallet className="w-12 h-12 text-slate-600 mx-auto mb-3" />
              <p className="text-slate-400">Aucune position</p>
            </div>
          )}
        </div>
      )}

      {/* Trading Tab */}
      {activeTab === 'trade' && (
        <div className="space-y-6">
          {/* Search */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Search className="w-5 h-5" />
              Rechercher un instrument
            </h3>
            <div className="flex gap-3">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && searchInstruments()}
                placeholder="Symbole ou nom (ex: AAPL, Microsoft)..."
                className="flex-1 bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={searchInstruments}
                disabled={loading || !searchQuery.trim()}
                className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-6 py-2 rounded-lg font-medium flex items-center gap-2"
              >
                {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                Rechercher
              </button>
            </div>

            {/* Results */}
            {searchResults.length > 0 && (
              <div className="mt-4 space-y-2 max-h-60 overflow-y-auto">
                {searchResults.map((inst, idx) => (
                  <div
                    key={idx}
                    onClick={() => {
                      setSelectedInstrument(inst)
                      setSearchResults([])
                      setSearchQuery('')
                    }}
                    className="bg-slate-900/50 hover:bg-slate-700/50 border border-slate-600 rounded-lg p-3 cursor-pointer"
                  >
                    <div className="flex justify-between">
                      <div>
                        <span className="font-medium">{inst.symbol}</span>
                        <span className="text-slate-400 ml-2">{inst.description}</span>
                      </div>
                      <span className="text-slate-500 text-sm">{inst.asset_type}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Order Form */}
          {selectedInstrument && (
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="text-lg font-semibold flex items-center gap-2">
                    <TrendingUp className="w-5 h-5" />
                    Passer un ordre
                  </h3>
                  <p className="text-slate-400 mt-1">
                    {selectedInstrument.symbol} - {selectedInstrument.description}
                  </p>
                </div>
                <button
                  onClick={() => setSelectedInstrument(null)}
                  className="text-slate-400 hover:text-white"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Buy/Sell */}
                <div>
                  <label className="block text-sm text-slate-400 mb-2">Direction</label>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setOrderForm({ ...orderForm, buySell: 'Buy' })}
                      className={`flex-1 py-3 rounded-lg font-semibold ${
                        orderForm.buySell === 'Buy'
                          ? 'bg-emerald-600 text-white'
                          : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                      }`}
                    >
                      Acheter
                    </button>
                    <button
                      onClick={() => setOrderForm({ ...orderForm, buySell: 'Sell' })}
                      className={`flex-1 py-3 rounded-lg font-semibold ${
                        orderForm.buySell === 'Sell'
                          ? 'bg-red-600 text-white'
                          : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                      }`}
                    >
                      Vendre
                    </button>
                  </div>
                </div>

                {/* Order Type */}
                <div>
                  <label className="block text-sm text-slate-400 mb-2">Type</label>
                  <select
                    value={orderForm.orderType}
                    onChange={(e) => setOrderForm({ ...orderForm, orderType: e.target.value })}
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-3"
                  >
                    <option value="Market">Market</option>
                    <option value="Limit">Limit</option>
                  </select>
                </div>

                {/* Quantity */}
                <div>
                  <label className="block text-sm text-slate-400 mb-2">Quantite</label>
                  <input
                    type="number"
                    min="1"
                    value={orderForm.quantity}
                    onChange={(e) => setOrderForm({ ...orderForm, quantity: parseInt(e.target.value) || 1 })}
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-3"
                  />
                </div>

                {/* Price (Limit) */}
                {orderForm.orderType === 'Limit' && (
                  <div>
                    <label className="block text-sm text-slate-400 mb-2">Prix limite</label>
                    <input
                      type="number"
                      step="0.01"
                      value={orderForm.price}
                      onChange={(e) => setOrderForm({ ...orderForm, price: e.target.value })}
                      placeholder="0.00"
                      className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-3"
                    />
                  </div>
                )}
              </div>

              <div className="mt-6">
                <button
                  onClick={placeOrder}
                  disabled={loading || (orderForm.orderType === 'Limit' && !orderForm.price)}
                  className={`w-full py-4 rounded-lg font-semibold text-lg disabled:opacity-50 ${
                    orderForm.buySell === 'Buy'
                      ? 'bg-emerald-600 hover:bg-emerald-500'
                      : 'bg-red-600 hover:bg-red-500'
                  }`}
                >
                  {loading ? (
                    <RefreshCw className="w-5 h-5 animate-spin mx-auto" />
                  ) : (
                    `${orderForm.buySell === 'Buy' ? 'Acheter' : 'Vendre'} ${orderForm.quantity} ${selectedInstrument.symbol}`
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Empty state */}
          {!selectedInstrument && searchResults.length === 0 && (
            <div className="bg-slate-800/30 border border-slate-700 rounded-xl p-6 text-center">
              <TrendingUp className="w-12 h-12 text-slate-600 mx-auto mb-3" />
              <p className="text-slate-400">Recherchez un instrument pour trader</p>
            </div>
          )}
        </div>
      )}

      {/* Orders Tab */}
      {activeTab === 'orders' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold">Ordres ({orders.length})</h3>
            <button
              onClick={loadOrders}
              disabled={loading}
              className="bg-slate-700/50 hover:bg-slate-600/50 px-3 py-1.5 rounded-lg text-sm flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Actualiser
            </button>
          </div>

          {orders.length === 0 ? (
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-8 text-center">
              <ShoppingCart className="w-12 h-12 text-slate-600 mx-auto mb-3" />
              <p className="text-slate-400">Aucun ordre en cours</p>
            </div>
          ) : (
            <div className="space-y-3">
              {orders.map((order, idx) => (
                <div key={order.OrderId || idx} className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
                  <div className="flex justify-between items-start">
                    <div className="flex items-center gap-3">
                      <span className={`px-3 py-1 rounded-lg font-semibold text-sm ${
                        order.BuySell === 'Buy'
                          ? 'bg-emerald-600/20 text-emerald-400'
                          : 'bg-red-600/20 text-red-400'
                      }`}>
                        {order.BuySell === 'Buy' ? 'ACHAT' : 'VENTE'}
                      </span>
                      <span className="font-semibold">{order.AssetType}</span>
                      <span className="text-slate-400">UIC: {order.Uic}</span>
                    </div>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      order.Status === 'Working' ? 'bg-yellow-600/20 text-yellow-400' :
                      order.Status === 'Filled' ? 'bg-emerald-600/20 text-emerald-400' :
                      'bg-slate-600/20 text-slate-400'
                    }`}>
                      {order.Status}
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-4 mt-4 text-sm">
                    <div>
                      <p className="text-slate-500">Quantite</p>
                      <p className="font-medium">{order.Amount}</p>
                    </div>
                    <div>
                      <p className="text-slate-500">Type</p>
                      <p className="font-medium">{order.OpenOrderType}</p>
                    </div>
                    <div>
                      <p className="text-slate-500">Prix</p>
                      <p className="font-medium">{order.Price?.toFixed(2) || '-'}</p>
                    </div>
                  </div>

                  {order.Status === 'Working' && (
                    <div className="mt-4 pt-3 border-t border-slate-700/50">
                      <button
                        onClick={() => cancelOrder(order.OrderId, order.AccountKey)}
                        className="text-red-400 hover:text-red-300 text-sm"
                      >
                        Annuler
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold">Historique</h3>
            <button
              onClick={loadHistory}
              disabled={loading}
              className="bg-slate-700/50 hover:bg-slate-600/50 px-3 py-1.5 rounded-lg text-sm flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Actualiser
            </button>
          </div>

          {history.length === 0 ? (
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-8 text-center">
              <History className="w-12 h-12 text-slate-600 mx-auto mb-3" />
              <p className="text-slate-400">Aucune transaction recente</p>
            </div>
          ) : (
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
              <table className="w-full">
                <thead className="bg-slate-900/50">
                  <tr>
                    <th className="text-left p-3 text-sm text-slate-400">Date</th>
                    <th className="text-left p-3 text-sm text-slate-400">Instrument</th>
                    <th className="text-center p-3 text-sm text-slate-400">Type</th>
                    <th className="text-right p-3 text-sm text-slate-400">Qte</th>
                    <th className="text-right p-3 text-sm text-slate-400">Prix</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((tx, idx) => (
                    <tr key={tx.TradeId || idx} className="border-t border-slate-700/50">
                      <td className="p-3 text-sm">
                        {new Date(tx.TradeExecutionTime || tx.TradeDate).toLocaleDateString('fr-FR')}
                      </td>
                      <td className="p-3">
                        <div className="font-medium">{tx.InstrumentSymbol || tx.UnderlyingInstrumentSymbol}</div>
                      </td>
                      <td className="p-3 text-center">
                        <span className={`px-2 py-1 rounded text-xs ${
                          tx.TradeEventType === 'Bought' || tx.Direction === 'Bought'
                            ? 'bg-emerald-600/20 text-emerald-400'
                            : 'bg-red-600/20 text-red-400'
                        }`}>
                          {tx.TradeEventType === 'Bought' || tx.Direction === 'Bought' ? 'Achat' : 'Vente'}
                        </span>
                      </td>
                      <td className="p-3 text-right">{Math.abs(tx.Amount)}</td>
                      <td className="p-3 text-right">{tx.Price?.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Loading overlay */}
      {loading && portfolio && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
        </div>
      )}

      {/* Alert Modal */}
      {alertModal.show && alertModal.position && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 max-w-md w-full">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-lg font-semibold flex items-center gap-2">
                  <Shield className="w-5 h-5 text-yellow-400" />
                  Configurer Alertes
                </h3>
                <p className="text-slate-400 text-sm mt-1">
                  {alertModal.position.symbol} - Prix: {alertModal.position.current_price?.toFixed(2)}€
                </p>
              </div>
              <button
                onClick={() => setAlertModal({ show: false, position: null })}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              {/* Stop Loss */}
              <div className="bg-red-900/20 border border-red-800/50 rounded-lg p-4">
                <div className="flex justify-between items-center mb-2">
                  <label className="text-sm font-medium text-red-400">Stop Loss</label>
                  <span className="text-red-300 font-mono">
                    {(alertModal.position.current_price * (1 - alertForm.stopLoss / 100)).toFixed(2)}€
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min="1"
                    max="25"
                    value={alertForm.stopLoss}
                    onChange={(e) => setAlertForm({ ...alertForm, stopLoss: Number(e.target.value) })}
                    className="flex-1 accent-red-500"
                  />
                  <span className="text-red-400 font-mono w-12 text-right">-{alertForm.stopLoss}%</span>
                </div>
              </div>

              {/* Take Profit */}
              <div className="bg-emerald-900/20 border border-emerald-800/50 rounded-lg p-4">
                <div className="flex justify-between items-center mb-2">
                  <label className="text-sm font-medium text-emerald-400">Take Profit</label>
                  <span className="text-emerald-300 font-mono">
                    {(alertModal.position.current_price * (1 + alertForm.takeProfit / 100)).toFixed(2)}€
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min="5"
                    max="100"
                    value={alertForm.takeProfit}
                    onChange={(e) => setAlertForm({ ...alertForm, takeProfit: Number(e.target.value) })}
                    className="flex-1 accent-emerald-500"
                  />
                  <span className="text-emerald-400 font-mono w-12 text-right">+{alertForm.takeProfit}%</span>
                </div>
              </div>

              {/* Info */}
              <p className="text-xs text-slate-500 text-center">
                Vous recevrez une notification Telegram quand le prix atteint ces niveaux
              </p>

              {/* Buttons */}
              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => setAlertModal({ show: false, position: null })}
                  className="flex-1 bg-slate-700 hover:bg-slate-600 text-slate-300 py-2.5 rounded-lg font-medium"
                >
                  Annuler
                </button>
                <button
                  onClick={createPositionAlerts}
                  disabled={loading}
                  className="flex-1 bg-yellow-600 hover:bg-yellow-500 text-white py-2.5 rounded-lg font-medium flex items-center justify-center gap-2"
                >
                  {loading ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <Bell className="w-4 h-4" />
                      Creer Alertes
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
