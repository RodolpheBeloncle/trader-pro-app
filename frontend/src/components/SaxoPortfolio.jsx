import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Wallet, RefreshCw, TrendingUp, TrendingDown,
  AlertCircle, ExternalLink, LogOut,
  History, ShoppingCart, Search, X, Bell, Shield, Lightbulb, Target, Wifi, WifiOff
} from 'lucide-react'
import StopLossModal from './StopLossModal'
import PositionDecisionPanel from './PositionDecisionPanel'
import TickerAnalysisModal from './TickerAnalysisModal'

const API_BASE = '/api'
const WS_BASE = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
const WS_URL = `${WS_BASE}//${window.location.host}/ws/prices`

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
  const [instrumentAnalysis, setInstrumentAnalysis] = useState(null)
  const [loadingAnalysis, setLoadingAnalysis] = useState(false)
  const [orderForm, setOrderForm] = useState({
    quantity: 1,
    orderType: 'Market',
    buySell: 'Buy',
    price: ''
  })
  const [initialTickerProcessed, setInitialTickerProcessed] = useState(false)

  // Alert modal state (legacy)
  const [alertModal, setAlertModal] = useState({ show: false, position: null })
  const [alertForm, setAlertForm] = useState({ stopLoss: 8, takeProfit: 24 })

  // New modals/panels state
  const [stopLossModal, setStopLossModal] = useState({ show: false, position: null })
  const [decisionPanel, setDecisionPanel] = useState({ show: false, position: null })
  const [analysisModal, setAnalysisModal] = useState({ show: false, ticker: null, position: null })
  const [stopLossConfig, setStopLossConfig] = useState({}) // {symbol: {sl_price, tp_price, mode}}
  const alertsLoadedRef = useRef(false)

  // WebSocket state for real-time prices
  const [wsConnected, setWsConnected] = useState(false)
  const [realtimePrices, setRealtimePrices] = useState({}) // {symbol: {price, change, change_percent, timestamp, flash}}
  const [streamingMode, setStreamingMode] = useState(null) // Current streaming mode info
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const subscribedTickersRef = useRef(new Set())

  // ==========================================================================
  // WEBSOCKET - Real-time price updates
  // ==========================================================================

  // Connect to WebSocket
  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return // Already connected
    }

    try {
      console.log('[WS] Connecting to', WS_URL)
      const ws = new WebSocket(WS_URL)

      ws.onopen = () => {
        console.log('[WS] Connected')
        setWsConnected(true)
        // Re-subscribe to all tickers we were tracking
        subscribedTickersRef.current.forEach(ticker => {
          ws.send(JSON.stringify({ type: 'subscribe', ticker }))
        })
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)

          if (data.type === 'price_update') {
            const ticker = data.ticker?.toUpperCase()
            if (ticker) {
              setRealtimePrices(prev => {
                const prevPrice = prev[ticker]?.price
                const newPrice = data.price
                const isUp = prevPrice && newPrice > prevPrice
                const isDown = prevPrice && newPrice < prevPrice

                return {
                  ...prev,
                  [ticker]: {
                    price: newPrice,
                    change: data.change,
                    change_percent: data.change_percent,
                    bid: data.bid,
                    ask: data.ask,
                    source: data.source,
                    timestamp: data.timestamp || new Date().toISOString(),
                    flash: isUp ? 'up' : isDown ? 'down' : null
                  }
                }
              })

              // Clear flash after animation
              setTimeout(() => {
                setRealtimePrices(prev => ({
                  ...prev,
                  [ticker]: { ...prev[ticker], flash: null }
                }))
              }, 500)
            }
          } else if (data.type === 'connected') {
            console.log('[WS] Client ID:', data.client_id)
          } else if (data.type === 'subscribed') {
            console.log('[WS] Subscribed to', data.ticker)
          }
        } catch (e) {
          console.error('[WS] Parse error:', e)
        }
      }

      ws.onclose = (event) => {
        console.log('[WS] Disconnected:', event.code, event.reason)
        setWsConnected(false)
        wsRef.current = null

        // Reconnect after delay (unless intentionally closed)
        if (event.code !== 1000) {
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log('[WS] Reconnecting...')
            connectWebSocket()
          }, 3000)
        }
      }

      ws.onerror = (error) => {
        console.error('[WS] Error:', error)
      }

      wsRef.current = ws
    } catch (e) {
      console.error('[WS] Connection error:', e)
    }
  }, [])

  // Subscribe to ticker
  const subscribeToTicker = useCallback((ticker) => {
    if (!ticker) return
    const normalizedTicker = ticker.toUpperCase()

    subscribedTickersRef.current.add(normalizedTicker)

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'subscribe', ticker: normalizedTicker }))
    }
  }, [])

  // Unsubscribe from ticker
  const unsubscribeFromTicker = useCallback((ticker) => {
    if (!ticker) return
    const normalizedTicker = ticker.toUpperCase()

    subscribedTickersRef.current.delete(normalizedTicker)

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'unsubscribe', ticker: normalizedTicker }))
    }
  }, [])

  // Subscribe to all portfolio tickers
  const subscribeToPortfolio = useCallback((positions) => {
    if (!positions?.length) return

    positions.forEach(pos => {
      if (pos.symbol) {
        subscribeToTicker(pos.symbol)
      }
    })
  }, [subscribeToTicker])

  // Load streaming status
  const loadStreamingStatus = useCallback(async () => {
    try {
      const res = await fetch('/ws/streaming/status')
      if (res.ok) {
        const data = await res.json()
        setStreamingMode(data)
      }
    } catch (e) {
      console.error('Error loading streaming status:', e)
    }
  }, [])

  // Connect WebSocket on mount
  useEffect(() => {
    connectWebSocket()
    loadStreamingStatus()

    // Refresh streaming status periodically
    const statusInterval = setInterval(loadStreamingStatus, 30000)

    return () => {
      clearInterval(statusInterval)
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounting')
      }
    }
  }, [connectWebSocket, loadStreamingStatus])

  // Subscribe to portfolio tickers when portfolio loads
  useEffect(() => {
    if (portfolio?.positions?.length > 0) {
      subscribeToPortfolio(portfolio.positions)
    }
  }, [portfolio?.positions, subscribeToPortfolio])

  // ==========================================================================
  // Load active alerts to display SL/TP in table (defined early to be used in useEffect)
  const loadActiveAlerts = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/alerts?active_only=true`)
      if (!res.ok) {
        console.log('loadActiveAlerts: API returned not ok', res.status)
        return
      }

      const alerts = await res.json()
      console.log('loadActiveAlerts: Received alerts:', alerts.length, alerts.map(a => a.ticker))

      // Group alerts by ticker to build stopLossConfig
      const configBySymbol = {}

      for (const alert of alerts) {
        // Normalize symbol to uppercase for matching with portfolio positions
        const symbol = alert.ticker?.toUpperCase()
        if (!symbol) continue

        if (!configBySymbol[symbol]) {
          configBySymbol[symbol] = { mode: 'alert' }
        }

        // Determine if this is a stop loss or take profit based on alert type
        if (alert.alert_type === 'price_below') {
          configBySymbol[symbol].sl_price = alert.target_value
        } else if (alert.alert_type === 'price_above') {
          configBySymbol[symbol].tp_price = alert.target_value
        }
      }

      console.log('loadActiveAlerts: Built config:', configBySymbol)
      setStopLossConfig(configBySymbol)
    } catch (err) {
      console.error('Error loading active alerts:', err)
    }
  }, [])

  // Check status on mount
  // Note: OAuth callback is handled by App.jsx and passed via oauthResult prop
  useEffect(() => {
    // Ne pas traiter le callback ici - c'est fait par App.jsx
    // Juste vérifier le statut
    checkStatus()
    // Charger les alertes actives au démarrage (indépendant de Saxo)
    loadActiveAlerts()
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
        console.log('All position symbols:', data.positions.map(p => p.symbol))
        console.log('Current stopLossConfig keys:', Object.keys(stopLossConfig))
        if (!sample.current_price && !sample.market_value) {
          console.warn('Position sans prix - verifier API Saxo')
        }
      }

      setPortfolio(data)
      // Reload alerts after portfolio to ensure matching
      loadActiveAlerts()
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
          // Use handleSelectInstrument to also load the analysis
          handleSelectInstrument(exactMatch)
        }
      }
    } catch (err) {
      setError('Erreur recherche')
    } finally {
      setLoading(false)
    }
  }

  // Load instrument analysis when an instrument is selected
  const loadInstrumentAnalysis = async (symbol) => {
    if (!symbol) {
      setInstrumentAnalysis(null)
      return
    }

    try {
      setLoadingAnalysis(true)
      const res = await fetch(`${API_BASE}/saxo/instruments/${encodeURIComponent(symbol)}/analyze`)

      if (!res.ok) {
        console.warn('Instrument analysis not available:', res.status)
        setInstrumentAnalysis(null)
        return
      }

      const data = await res.json()
      setInstrumentAnalysis(data)
    } catch (err) {
      console.error('Error loading instrument analysis:', err)
      setInstrumentAnalysis(null)
    } finally {
      setLoadingAnalysis(false)
    }
  }

  // Handle instrument selection with analysis loading
  const handleSelectInstrument = (instrument) => {
    setSelectedInstrument(instrument)
    setSearchResults([])
    setSearchQuery('')
    // Load analysis for the selected instrument
    if (instrument?.symbol) {
      loadInstrumentAnalysis(instrument.symbol)
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
              {/* WebSocket Status */}
              <span className={`px-2 py-0.5 rounded text-xs font-medium flex items-center gap-1 ${
                wsConnected
                  ? 'bg-emerald-600/20 text-emerald-400'
                  : 'bg-slate-600/20 text-slate-400'
              }`} title={wsConnected ? `Streaming: ${streamingMode?.trading_mode_name || 'Actif'}` : 'Streaming deconnecte'}>
                {wsConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
                {streamingMode?.trading_mode_name || (wsConnected ? 'Live' : 'Off')}
              </span>
            </div>
            <p className="text-sm text-slate-400 flex items-center gap-2">
              Connecte
              {streamingMode && (
                <span className="text-xs text-slate-500">
                  • Sources: {streamingMode.sources?.join(', ') || 'yahoo'}
                  {streamingMode.use_websocket ? ' (temps reel)' : ` (${streamingMode.poll_interval}s)`}
                </span>
              )}
            </p>
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
          {/* Calculate real-time totals */}
          {(() => {
            // Calculate live totals from real-time prices
            let liveTotalValue = 0
            let totalCostBasis = 0

            portfolio.positions.forEach(pos => {
              const rtPrice = realtimePrices[pos.symbol?.toUpperCase()]
              const price = rtPrice?.price ?? pos.current_price
              const marketValue = price ? price * pos.quantity : pos.market_value
              liveTotalValue += marketValue || 0
              totalCostBasis += (pos.average_price * pos.quantity) || 0
            })

            const liveTotalPnl = liveTotalValue - totalCostBasis
            const liveTotalPnlPercent = totalCostBasis > 0 ? (liveTotalPnl / totalCostBasis) * 100 : 0
            const hasRealtimeData = Object.keys(realtimePrices).length > 0

            return (
              <>
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
                        {(portfolio.summary.cash_available + liveTotalValue).toLocaleString('fr-FR', {
                          style: 'currency',
                          currency: portfolio.summary.currency || 'EUR'
                        })}
                        {hasRealtimeData && <span className="ml-1 text-[10px] text-emerald-500">●</span>}
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
              <p className="text-sm text-slate-400 flex items-center gap-1">
                Valeur positions
                {hasRealtimeData && <span className="text-[10px] text-emerald-500">● live</span>}
              </p>
              <p className="text-2xl font-bold">
                {liveTotalValue.toLocaleString('fr-FR', {
                  style: 'currency',
                  currency: portfolio.summary.currency || 'EUR'
                })}
              </p>
            </div>
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
              <p className="text-sm text-slate-400 flex items-center gap-1">
                P&L Total
                {hasRealtimeData && <span className="text-[10px] text-emerald-500">● live</span>}
              </p>
              <p className={`text-2xl font-bold ${
                liveTotalPnl >= 0 ? 'text-emerald-400' : 'text-red-400'
              }`}>
                {liveTotalPnl >= 0 ? '+' : ''}
                {liveTotalPnl.toLocaleString('fr-FR', {
                  style: 'currency',
                  currency: portfolio.summary.currency || 'EUR'
                })}
              </p>
            </div>
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
              <p className="text-sm text-slate-400 flex items-center gap-1">
                P&L %
                {hasRealtimeData && <span className="text-[10px] text-emerald-500">● live</span>}
              </p>
              <p className={`text-2xl font-bold ${
                liveTotalPnlPercent >= 0 ? 'text-emerald-400' : 'text-red-400'
              }`}>
                {liveTotalPnlPercent >= 0 ? '+' : ''}
                {liveTotalPnlPercent.toFixed(2)}%
              </p>
            </div>
          </div>

          {/* Positions */}
          {portfolio.positions.length > 0 ? (
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden overflow-x-auto">
              {/* Legend for price indicators */}
              <div className="px-4 py-2 bg-slate-900/30 border-b border-slate-700/50 flex items-center gap-4 text-xs text-slate-400">
                <span className="font-medium">Prix:</span>
                <span className="flex items-center gap-1">
                  <span className="text-emerald-500">●</span> Temps reel
                </span>
                <span className="flex items-center gap-1">
                  <span className="text-amber-500">◐</span> Pas de streaming (prix Saxo)
                </span>
                <span className="flex items-center gap-1">
                  <span className="text-slate-500">○</span> Prix de cloture
                </span>
              </div>
              <table className="w-full min-w-[900px]">
                <thead className="bg-slate-900/50">
                  <tr>
                    <th className="text-left p-3 text-sm font-medium text-slate-400">Position</th>
                    <th className="text-right p-3 text-sm font-medium text-slate-400">Qte</th>
                    <th className="text-right p-3 text-sm font-medium text-slate-400">PRU</th>
                    <th className="text-right p-3 text-sm font-medium text-slate-400">Prix</th>
                    <th className="text-right p-3 text-sm font-medium text-slate-400">Valeur</th>
                    <th className="text-right p-3 text-sm font-medium text-slate-400">P&L</th>
                    <th className="text-center p-3 text-sm font-medium text-slate-400">SL/TP</th>
                    <th className="text-center p-3 text-sm font-medium text-slate-400">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {portfolio.positions.map((pos, idx) => {
                    // Get real-time price if available
                    const rtPrice = realtimePrices[pos.symbol?.toUpperCase()]
                    const displayPrice = rtPrice?.price ?? pos.current_price
                    const priceFlash = rtPrice?.flash

                    // Recalculate P&L with real-time price
                    const liveMarketValue = displayPrice ? displayPrice * pos.quantity : pos.market_value
                    const costBasis = pos.average_price * pos.quantity
                    const livePnl = liveMarketValue - costBasis
                    const livePnlPercent = costBasis > 0 ? (livePnl / costBasis) * 100 : 0

                    return (
                    <tr key={idx} className="border-t border-slate-700/50 hover:bg-slate-700/20">
                      <td className="p-3">
                        <span
                          className="font-semibold text-white hover:text-blue-400 cursor-pointer transition-colors"
                          onClick={() => setAnalysisModal({ show: true, ticker: pos.symbol, position: pos })}
                          title="Voir l'analyse complete"
                        >
                          {pos.symbol}
                        </span>
                        <p className="text-xs text-slate-500 truncate max-w-[180px]">{pos.description}</p>
                        {rtPrice?.source && (
                          <p className="text-[10px] text-slate-600">{rtPrice.source}</p>
                        )}
                      </td>
                      <td className="text-right p-3 font-mono">{pos.quantity}</td>
                      <td className="text-right p-3 font-mono text-slate-400">
                        {pos.average_price?.toLocaleString('fr-FR', {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2
                        })}
                      </td>
                      <td className={`text-right p-3 font-mono font-semibold transition-all duration-300 ${
                        priceFlash === 'up' ? 'bg-emerald-500/30 text-emerald-300' :
                        priceFlash === 'down' ? 'bg-red-500/30 text-red-300' : ''
                      }`}>
                        {displayPrice?.toLocaleString('fr-FR', {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2
                        })}
                        {rtPrice ? (
                          <span className="ml-1 text-[10px] text-emerald-500" title="Prix temps reel">●</span>
                        ) : subscribedTickersRef.current.has(pos.symbol?.toUpperCase()) ? (
                          <span
                            className="ml-1 text-[10px] text-amber-500 cursor-help"
                            title="Pas de streaming disponible pour ce ticker (prix Saxo utilise)"
                          >◐</span>
                        ) : (
                          <span className="ml-1 text-[10px] text-slate-500" title="Prix de cloture">○</span>
                        )}
                      </td>
                      <td className={`text-right p-3 font-mono transition-all duration-300 ${
                        priceFlash === 'up' ? 'bg-emerald-500/20' :
                        priceFlash === 'down' ? 'bg-red-500/20' : ''
                      }`}>
                        {liveMarketValue?.toLocaleString('fr-FR', {
                          style: 'currency',
                          currency: pos.currency || 'EUR'
                        })}
                      </td>
                      <td className={`text-right p-3 transition-all duration-300 ${
                        priceFlash === 'up' ? 'bg-emerald-500/20' :
                        priceFlash === 'down' ? 'bg-red-500/20' : ''
                      }`}>
                        <div className={`font-semibold ${livePnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {livePnl >= 0 ? '+' : ''}{livePnl?.toLocaleString('fr-FR', {
                            style: 'currency',
                            currency: pos.currency || 'EUR'
                          })}
                        </div>
                        <div className={`text-xs ${livePnlPercent >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                          {livePnlPercent >= 0 ? '+' : ''}{livePnlPercent?.toFixed(2)}%
                        </div>
                      </td>
                      {/* SL/TP Column */}
                      <td className="text-center p-3">
                        {(() => {
                          // Normalize symbol for matching (uppercase)
                          const normalizedSymbol = pos.symbol?.toUpperCase()
                          const config = stopLossConfig[normalizedSymbol]

                          if (config) {
                            return (
                              <div className="flex flex-col items-center text-xs">
                                {config.sl_price && (
                                  <span className="text-red-400 font-mono">
                                    SL: {config.sl_price.toFixed(2)}€
                                  </span>
                                )}
                                {config.tp_price && (
                                  <span className="text-emerald-400 font-mono">
                                    TP: {config.tp_price.toFixed(2)}€
                                  </span>
                                )}
                                <span className="text-slate-500 text-[10px] mt-0.5">
                                  {config.mode === 'order' ? '🔒 Ordre' : '🔔 Alerte'}
                                </span>
                              </div>
                            )
                          }

                          return (
                            <button
                              onClick={() => setStopLossModal({ show: true, position: pos })}
                              className="bg-slate-700/50 hover:bg-slate-600/50 text-slate-400 hover:text-white px-2 py-1 rounded text-xs flex items-center gap-1 mx-auto"
                            >
                              <Target className="w-3 h-3" />
                              Configurer
                            </button>
                          )
                        })()}
                      </td>
                      {/* Actions Column */}
                      <td className="text-center p-3">
                        <div className="flex items-center justify-center gap-1">
                          <button
                            onClick={() => setDecisionPanel({ show: true, position: pos })}
                            className="bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 p-1.5 rounded"
                            title="Aide a la decision"
                          >
                            <Lightbulb className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => setStopLossModal({ show: true, position: pos })}
                            className="bg-yellow-600/20 hover:bg-yellow-600/40 text-yellow-400 p-1.5 rounded"
                            title="Configurer SL/TP"
                          >
                            <Shield className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => {
                              const instrument = {
                                uic: pos.uic,
                                symbol: pos.symbol,
                                description: pos.description,
                                asset_type: pos.asset_type
                              }
                              setSelectedInstrument(instrument)
                              setInstrumentAnalysis(null)
                              loadInstrumentAnalysis(pos.symbol)
                              setOrderForm({ ...orderForm, buySell: 'Buy' })
                              setActiveTab('trade')
                            }}
                            className="bg-emerald-600/20 hover:bg-emerald-600/40 text-emerald-400 px-2 py-1 rounded text-xs"
                          >
                            +
                          </button>
                          <button
                            onClick={() => {
                              const instrument = {
                                uic: pos.uic,
                                symbol: pos.symbol,
                                description: pos.description,
                                asset_type: pos.asset_type
                              }
                              setSelectedInstrument(instrument)
                              setInstrumentAnalysis(null)
                              loadInstrumentAnalysis(pos.symbol)
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
                  )})}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="bg-slate-800/30 border border-slate-700 rounded-xl p-8 text-center">
              <Wallet className="w-12 h-12 text-slate-600 mx-auto mb-3" />
              <p className="text-slate-400">Aucune position</p>
            </div>
          )}
              </>
            )
          })()}
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
                    onClick={() => handleSelectInstrument(inst)}
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

          {/* Instrument Analysis Panel */}
          {selectedInstrument && (
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="text-lg font-semibold flex items-center gap-2">
                    <Target className="w-5 h-5 text-blue-400" />
                    Analyse de {selectedInstrument.symbol}
                  </h3>
                  <p className="text-slate-400 mt-1">{selectedInstrument.description}</p>
                </div>
                <button
                  onClick={() => {
                    setSelectedInstrument(null)
                    setInstrumentAnalysis(null)
                  }}
                  className="text-slate-400 hover:text-white"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {loadingAnalysis ? (
                <div className="flex items-center justify-center py-8">
                  <RefreshCw className="w-8 h-8 animate-spin text-blue-400" />
                  <span className="ml-3 text-slate-400">Analyse en cours...</span>
                </div>
              ) : instrumentAnalysis ? (
                <div className="space-y-4">
                  {/* Price & Recommendation Summary */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="bg-slate-900/50 rounded-lg p-3">
                      <div className="text-sm text-slate-400">Prix actuel</div>
                      <div className="text-xl font-bold">{instrumentAnalysis.price?.current_price?.toFixed(2)} {instrumentAnalysis.info?.currency}</div>
                      <div className={`text-sm ${instrumentAnalysis.price?.change_percent >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {instrumentAnalysis.price?.change_percent >= 0 ? '+' : ''}{instrumentAnalysis.price?.change_percent?.toFixed(2)}%
                      </div>
                    </div>

                    <div className="bg-slate-900/50 rounded-lg p-3">
                      <div className="text-sm text-slate-400">Recommandation</div>
                      <div className={`text-xl font-bold ${
                        instrumentAnalysis.recommendation?.action === 'BUY' ? 'text-emerald-400' :
                        instrumentAnalysis.recommendation?.action === 'AVOID' ? 'text-red-400' : 'text-yellow-400'
                      }`}>
                        {instrumentAnalysis.recommendation?.action === 'BUY' ? 'ACHETER' :
                         instrumentAnalysis.recommendation?.action === 'AVOID' ? 'EVITER' : 'ATTENDRE'}
                      </div>
                      <div className="text-sm text-slate-400">
                        {'★'.repeat(instrumentAnalysis.recommendation?.rating || 0)}{'☆'.repeat(5 - (instrumentAnalysis.recommendation?.rating || 0))}
                      </div>
                    </div>

                    <div className="bg-slate-900/50 rounded-lg p-3">
                      <div className="text-sm text-slate-400">RSI</div>
                      <div className={`text-xl font-bold ${
                        instrumentAnalysis.technical?.rsi > 70 ? 'text-red-400' :
                        instrumentAnalysis.technical?.rsi < 30 ? 'text-emerald-400' : 'text-white'
                      }`}>
                        {instrumentAnalysis.technical?.rsi?.toFixed(0)}
                      </div>
                      <div className="text-sm text-slate-400">{instrumentAnalysis.technical?.rsi_signal}</div>
                    </div>

                    <div className="bg-slate-900/50 rounded-lg p-3">
                      <div className="text-sm text-slate-400">Tendance</div>
                      <div className={`text-xl font-bold ${
                        instrumentAnalysis.technical?.trend === 'uptrend' ? 'text-emerald-400' :
                        instrumentAnalysis.technical?.trend === 'downtrend' ? 'text-red-400' : 'text-yellow-400'
                      }`}>
                        {instrumentAnalysis.technical?.trend === 'uptrend' ? '↑ Haussiere' :
                         instrumentAnalysis.technical?.trend === 'downtrend' ? '↓ Baissiere' : '→ Laterale'}
                      </div>
                      <div className="text-sm text-slate-400">{instrumentAnalysis.technical?.trend_strength}</div>
                    </div>
                  </div>

                  {/* Trading Levels */}
                  <div className="bg-slate-900/50 rounded-lg p-4">
                    <h4 className="font-medium mb-3 flex items-center gap-2">
                      <Shield className="w-4 h-4 text-blue-400" />
                      Niveaux de Trading Suggeres
                    </h4>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div>
                        <div className="text-slate-400">Stop Loss</div>
                        <div className="font-medium text-red-400">
                          {instrumentAnalysis.trading_levels?.suggested_stop_loss?.toFixed(2)} ({-instrumentAnalysis.trading_levels?.stop_loss_distance_pct?.toFixed(1)}%)
                        </div>
                      </div>
                      <div>
                        <div className="text-slate-400">Take Profit 1 (2:1)</div>
                        <div className="font-medium text-emerald-400">
                          {instrumentAnalysis.trading_levels?.suggested_take_profit_1?.toFixed(2)} (+{instrumentAnalysis.trading_levels?.take_profit_1_distance_pct?.toFixed(1)}%)
                        </div>
                      </div>
                      <div>
                        <div className="text-slate-400">Take Profit 2 (3:1)</div>
                        <div className="font-medium text-emerald-400">
                          {instrumentAnalysis.trading_levels?.suggested_take_profit_2?.toFixed(2)} (+{instrumentAnalysis.trading_levels?.take_profit_2_distance_pct?.toFixed(1)}%)
                        </div>
                      </div>
                      <div>
                        <div className="text-slate-400">Ratio R/R</div>
                        <div className="font-medium text-blue-400">{instrumentAnalysis.trading_levels?.risk_reward_ratio}:1</div>
                      </div>
                    </div>
                  </div>

                  {/* Technical Indicators */}
                  <div className="bg-slate-900/50 rounded-lg p-4">
                    <h4 className="font-medium mb-3">Indicateurs Techniques</h4>
                    <div className="grid grid-cols-3 md:grid-cols-6 gap-3 text-sm">
                      <div>
                        <div className="text-slate-400">MACD</div>
                        <div className={`font-medium ${instrumentAnalysis.technical?.macd_trend === 'bullish' ? 'text-emerald-400' : instrumentAnalysis.technical?.macd_trend === 'bearish' ? 'text-red-400' : 'text-white'}`}>
                          {instrumentAnalysis.technical?.macd_trend}
                        </div>
                      </div>
                      <div>
                        <div className="text-slate-400">SMA 50</div>
                        <div className="font-medium">{instrumentAnalysis.technical?.sma_50?.toFixed(2)}</div>
                      </div>
                      <div>
                        <div className="text-slate-400">SMA 200</div>
                        <div className="font-medium">{instrumentAnalysis.technical?.sma_200?.toFixed(2)}</div>
                      </div>
                      <div>
                        <div className="text-slate-400">Bollinger</div>
                        <div className="font-medium">{instrumentAnalysis.technical?.bollinger_position}</div>
                      </div>
                      <div>
                        <div className="text-slate-400">ATR</div>
                        <div className="font-medium">{instrumentAnalysis.technical?.atr?.toFixed(2)} ({instrumentAnalysis.technical?.atr_percent?.toFixed(1)}%)</div>
                      </div>
                      <div>
                        <div className="text-slate-400">52W Range</div>
                        <div className="font-medium text-xs">
                          {instrumentAnalysis.price?.week_52_low?.toFixed(0)} - {instrumentAnalysis.price?.week_52_high?.toFixed(0)}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Pros & Cons */}
                  {(instrumentAnalysis.recommendation?.pros?.length > 0 || instrumentAnalysis.recommendation?.cons?.length > 0) && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {instrumentAnalysis.recommendation?.pros?.length > 0 && (
                        <div className="bg-emerald-900/20 border border-emerald-800/50 rounded-lg p-4">
                          <h4 className="font-medium text-emerald-400 mb-2 flex items-center gap-2">
                            <TrendingUp className="w-4 h-4" /> Points Positifs
                          </h4>
                          <ul className="space-y-1 text-sm">
                            {instrumentAnalysis.recommendation.pros.map((pro, i) => (
                              <li key={i} className="text-emerald-300">+ {pro}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {instrumentAnalysis.recommendation?.cons?.length > 0 && (
                        <div className="bg-red-900/20 border border-red-800/50 rounded-lg p-4">
                          <h4 className="font-medium text-red-400 mb-2 flex items-center gap-2">
                            <TrendingDown className="w-4 h-4" /> Points Negatifs
                          </h4>
                          <ul className="space-y-1 text-sm">
                            {instrumentAnalysis.recommendation.cons.map((con, i) => (
                              <li key={i} className="text-red-300">- {con}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Sentiment */}
                  {instrumentAnalysis.sentiment && (
                    <div className="bg-slate-900/50 rounded-lg p-4">
                      <h4 className="font-medium mb-2">Sentiment Marche</h4>
                      <div className="flex items-center gap-4">
                        <span className={`px-3 py-1 rounded-full text-sm ${
                          instrumentAnalysis.sentiment.sentiment_label === 'bullish' ? 'bg-emerald-900/50 text-emerald-400' :
                          instrumentAnalysis.sentiment.sentiment_label === 'bearish' ? 'bg-red-900/50 text-red-400' : 'bg-slate-700 text-slate-300'
                        }`}>
                          {instrumentAnalysis.sentiment.sentiment_label}
                        </span>
                        <span className="text-sm text-slate-400">
                          Score: {instrumentAnalysis.sentiment.sentiment_score?.toFixed(2)} | {instrumentAnalysis.sentiment.news_count} news
                        </span>
                      </div>
                      {instrumentAnalysis.sentiment.recent_headlines?.length > 0 && (
                        <div className="mt-3 space-y-1">
                          {instrumentAnalysis.sentiment.recent_headlines.slice(0, 3).map((news, i) => (
                            <div key={i} className="text-xs text-slate-400 truncate">
                              • {news.headline || news}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-6 text-slate-400">
                  <AlertCircle className="w-8 h-8 mx-auto mb-2" />
                  Analyse non disponible pour cet instrument
                </div>
              )}
            </div>
          )}

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
                  onClick={() => {
                    setSelectedInstrument(null)
                    setInstrumentAnalysis(null)
                  }}
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

      {/* New Stop Loss Modal (dual-mode) */}
      {stopLossModal.show && stopLossModal.position && (
        <StopLossModal
          position={stopLossModal.position}
          accountKey={portfolio?.account_key}
          onClose={() => setStopLossModal({ show: false, position: null })}
          onSuccess={(msg, slPrice, tpPrice, mode) => {
            // Update config state to show SL/TP in table with actual values
            const pos = stopLossModal.position
            setStopLossConfig(prev => ({
              ...prev,
              [pos.symbol]: { sl_price: slPrice, tp_price: tpPrice, mode: mode || 'alert' }
            }))
            setSuccess(msg)
            setTimeout(() => setSuccess(null), 5000)
          }}
          onError={(msg) => setError(msg)}
        />
      )}

      {/* Position Decision Panel */}
      {decisionPanel.show && decisionPanel.position && (
        <PositionDecisionPanel
          position={decisionPanel.position}
          onClose={() => setDecisionPanel({ show: false, position: null })}
          onCreateAlert={(pos) => {
            setDecisionPanel({ show: false, position: null })
            setStopLossModal({ show: true, position: pos })
          }}
          onTrade={(pos, direction) => {
            setDecisionPanel({ show: false, position: null })
            const instrument = {
              uic: pos.uic,
              symbol: pos.symbol,
              description: pos.description,
              asset_type: pos.asset_type
            }
            setSelectedInstrument(instrument)
            setInstrumentAnalysis(null)
            loadInstrumentAnalysis(pos.symbol)
            setOrderForm({ ...orderForm, buySell: direction })
            setActiveTab('trade')
          }}
        />
      )}

      {/* Ticker Analysis Modal */}
      {analysisModal.show && analysisModal.ticker && (
        <TickerAnalysisModal
          ticker={analysisModal.ticker}
          position={analysisModal.position}
          onClose={() => setAnalysisModal({ show: false, ticker: null, position: null })}
        />
      )}
    </div>
  )
}
