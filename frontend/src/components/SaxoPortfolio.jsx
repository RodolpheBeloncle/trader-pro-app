import { useState, useEffect } from 'react'
import {
  Wallet, RefreshCw, TrendingUp, TrendingDown,
  AlertCircle, CheckCircle, ExternalLink, LogOut,
  History, ShoppingCart, Search, Plus, X
} from 'lucide-react'
import {
  getSaxoStatus, getSaxoAuthUrl, getSaxoPortfolio,
  getSaxoOrders, getSaxoHistory, searchSaxoInstrument,
  placeSaxoOrder, cancelSaxoOrder
} from '../api'

// Sub-tabs for Saxo section
const SAXO_TABS = [
  { id: 'portfolio', label: 'Portefeuille', icon: Wallet },
  { id: 'trade', label: 'Trading', icon: TrendingUp },
  { id: 'orders', label: 'Ordres', icon: ShoppingCart },
  { id: 'history', label: 'Historique', icon: History }
]

export default function SaxoPortfolio({ initialTicker = null }) {
  const [isConfigured, setIsConfigured] = useState(false)
  const [accessToken, setAccessToken] = useState(localStorage.getItem('saxo_token') || '')
  const [portfolio, setPortfolio] = useState(null)
  const [orders, setOrders] = useState([])
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
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
  const [accountKey, setAccountKey] = useState('')
  const [pendingSearch, setPendingSearch] = useState(initialTicker || null)

  useEffect(() => {
    checkSaxoStatus()

    // Check for OAuth callback
    const urlParams = new URLSearchParams(window.location.search)
    const code = urlParams.get('code')
    if (code) {
      handleOAuthCallback(code)
    }
  }, [])

  useEffect(() => {
    if (accessToken) {
      loadPortfolio()
      // Auto-search if we have a pending search from initialTicker
      if (pendingSearch) {
        handleSearch()
        setPendingSearch(null)
      }
    }
  }, [accessToken])

  // Handle initialTicker changes (when user clicks Trade from another tab)
  useEffect(() => {
    if (initialTicker && accessToken) {
      setSearchQuery(initialTicker)
      setActiveTab('trade')
      // Trigger search after a small delay to ensure state is updated
      setTimeout(() => {
        searchSaxoInstrument(accessToken, initialTicker)
          .then(data => {
            const instruments = (data.results || []).map(inst => ({
              uic: inst.Identifier || inst.Uic,
              symbol: inst.Symbol || inst.Identifier,
              description: inst.Description || '',
              asset_type: inst.AssetType || 'Stock',
              exchange: inst.ExchangeId || ''
            }))
            setSearchResults(instruments)
          })
          .catch(err => setError('Échec de la recherche'))
      }, 100)
    }
  }, [initialTicker, accessToken])

  const checkSaxoStatus = async () => {
    try {
      const status = await getSaxoStatus()
      setIsConfigured(status.configured)
    } catch (err) {
      console.error('Failed to check Saxo status:', err)
    }
  }

  const handleOAuthCallback = async (code) => {
    try {
      setLoading(true)
      const response = await fetch(`/api/saxo/auth/callback?code=${code}`)
      const data = await response.json()

      if (data.access_token) {
        setAccessToken(data.access_token)
        localStorage.setItem('saxo_token', data.access_token)
        // Clean URL
        window.history.replaceState({}, '', window.location.pathname)
      }
    } catch (err) {
      setError('Échec de connexion Saxo')
    } finally {
      setLoading(false)
    }
  }

  const connectSaxo = async () => {
    try {
      const { auth_url } = await getSaxoAuthUrl()
      window.location.href = auth_url
    } catch (err) {
      setError('Impossible de se connecter à Saxo. Vérifiez la configuration API.')
    }
  }

  const disconnectSaxo = () => {
    setAccessToken('')
    setPortfolio(null)
    setOrders([])
    setHistory([])
    localStorage.removeItem('saxo_token')
  }

  const loadPortfolio = async () => {
    if (!accessToken) return
    setLoading(true)
    setError(null)

    try {
      const data = await getSaxoPortfolio(accessToken, true)
      setPortfolio(data)
      // Save account key for trading
      if (data.account_key) {
        setAccountKey(data.account_key)
      }
    } catch (err) {
      setError('Échec du chargement du portefeuille. Token expiré ?')
      if (err.message.includes('401')) {
        disconnectSaxo()
      }
    } finally {
      setLoading(false)
    }
  }

  const loadOrders = async () => {
    if (!accessToken) return
    setLoading(true)

    try {
      const data = await getSaxoOrders(accessToken)
      setOrders(data.orders || [])
    } catch (err) {
      setError('Échec du chargement des ordres')
    } finally {
      setLoading(false)
    }
  }

  const loadHistory = async () => {
    if (!accessToken) return
    setLoading(true)

    try {
      const data = await getSaxoHistory(accessToken, 30)
      setHistory(data.transactions || [])
    } catch (err) {
      setError('Échec du chargement de l\'historique')
    } finally {
      setLoading(false)
    }
  }

  const handleTabChange = (tabId) => {
    setActiveTab(tabId)
    if (tabId === 'orders') loadOrders()
    if (tabId === 'history') loadHistory()
  }

  // Search for instruments
  const handleSearch = async () => {
    if (!searchQuery.trim() || !accessToken) return
    setLoading(true)
    setError(null)

    try {
      const data = await searchSaxoInstrument(accessToken, searchQuery)
      // Saxo returns Data array with Identifier, Description, Symbol, AssetType, etc.
      const instruments = (data.results || []).map(inst => ({
        uic: inst.Identifier || inst.Uic,
        symbol: inst.Symbol || inst.Identifier,
        description: inst.Description || '',
        asset_type: inst.AssetType || 'Stock',
        exchange: inst.ExchangeId || ''
      }))
      setSearchResults(instruments)
    } catch (err) {
      setError('Échec de la recherche')
    } finally {
      setLoading(false)
    }
  }

  // Select an instrument for trading
  const selectInstrument = (instrument) => {
    setSelectedInstrument(instrument)
    setSearchResults([])
    setSearchQuery('')
    setActiveTab('trade')
    setSuccess(null)
    setError(null)
  }

  // Trade from portfolio position
  const tradeFromPosition = (position) => {
    setSelectedInstrument({
      uic: position.uic || position.Uic,
      symbol: position.symbol,
      description: position.description,
      asset_type: position.asset_type || 'Stock'
    })
    setActiveTab('trade')
    setSuccess(null)
    setError(null)
  }

  // Place order
  const submitOrder = async () => {
    if (!selectedInstrument || !accessToken) return

    // Get account key from portfolio
    const accKey = portfolio?.account_key || accountKey
    if (!accKey) {
      setError('Compte non trouvé. Rechargez le portefeuille.')
      return
    }

    setLoading(true)
    setError(null)
    setSuccess(null)

    try {
      // Ensure UIC is a string for the API
      const uic = String(selectedInstrument.uic)

      const orderData = {
        symbol: uic, // Backend uses symbol field for UIC
        asset_type: selectedInstrument.asset_type || 'Stock',
        buy_sell: orderForm.buySell,
        quantity: parseInt(orderForm.quantity, 10),
        order_type: orderForm.orderType,
        account_key: accKey
      }

      if (orderForm.orderType === 'Limit' && orderForm.price) {
        orderData.price = parseFloat(orderForm.price)
      }

      console.log('Placing order:', orderData) // Debug log
      await placeSaxoOrder(accessToken, orderData)
      setSuccess(`Ordre ${orderForm.buySell === 'Buy' ? 'Achat' : 'Vente'} de ${orderForm.quantity} ${selectedInstrument.symbol} placé avec succès ! Consultez l'onglet Ordres.`)
      setSelectedInstrument(null)
      setOrderForm({ quantity: 1, orderType: 'Market', buySell: 'Buy', price: '' })
      // Refresh orders and portfolio
      loadOrders()
      loadPortfolio()
    } catch (err) {
      setError(err.message || 'Échec du placement de l\'ordre')
    } finally {
      setLoading(false)
    }
  }

  // Not configured state
  if (!isConfigured) {
    return (
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-8 text-center">
        <AlertCircle className="w-16 h-16 text-yellow-500 mx-auto mb-4" />
        <h3 className="text-xl font-semibold mb-2">Configuration Saxo requise</h3>
        <p className="text-slate-400 mb-4">
          Pour connecter votre compte Saxo, configurez les variables d'environnement :
        </p>
        <pre className="bg-slate-900 rounded-lg p-4 text-left text-sm mb-4">
          <code className="text-emerald-400">
            SAXO_APP_KEY=votre_app_key{'\n'}
            SAXO_APP_SECRET=votre_app_secret
          </code>
        </pre>
        <a
          href="https://www.developer.saxo/openapi/appmanagement"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 text-blue-400 hover:text-blue-300"
        >
          Créer une app Saxo <ExternalLink className="w-4 h-4" />
        </a>
      </div>
    )
  }

  // Not connected state
  if (!accessToken) {
    return (
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-8 text-center">
        <Wallet className="w-16 h-16 text-blue-500 mx-auto mb-4" />
        <h3 className="text-xl font-semibold mb-2">Connecter Saxo Trader</h3>
        <p className="text-slate-400 mb-4">
          Collez votre token 24h depuis le portail Saxo Developer
        </p>
        <div className="max-w-md mx-auto mb-4">
          <input
            type="text"
            placeholder="Collez votre access token ici..."
            className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-3 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && e.target.value) {
                setAccessToken(e.target.value)
                localStorage.setItem('saxo_token', e.target.value)
              }
            }}
            onChange={(e) => {
              if (e.target.value.length > 100) {
                setAccessToken(e.target.value)
                localStorage.setItem('saxo_token', e.target.value)
              }
            }}
          />
        </div>
        <p className="text-xs text-slate-500 mb-4">
          Obtenez un token sur{' '}
          <a href="https://www.developer.saxo/openapi/token" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">
            developer.saxo/openapi/token
          </a>
        </p>
        <button
          onClick={connectSaxo}
          disabled={loading}
          className="bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white px-6 py-3 rounded-lg font-medium inline-flex items-center gap-2"
        >
          {loading ? (
            <RefreshCw className="w-5 h-5 animate-spin" />
          ) : (
            <Wallet className="w-5 h-5" />
          )}
          Ou connexion OAuth (si configuré)
        </button>
      </div>
    )
  }

  // Connected state
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
            <Wallet className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-semibold">Saxo Portfolio</h2>
            <p className="text-sm text-slate-400">Connecté</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadPortfolio}
            disabled={loading}
            className="bg-slate-700/50 hover:bg-slate-600/50 p-2 rounded-lg"
          >
            <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={disconnectSaxo}
            className="bg-red-600/20 hover:bg-red-600/30 text-red-400 p-2 rounded-lg"
            title="Déconnecter"
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4">
          <p className="text-red-400">{error}</p>
        </div>
      )}

      {/* Success */}
      {success && (
        <div className="bg-emerald-900/30 border border-emerald-700 rounded-lg p-4">
          <p className="text-emerald-400">{success}</p>
        </div>
      )}

      {/* Sub-tabs */}
      <div className="flex gap-2 border-b border-slate-700 pb-2">
        {SAXO_TABS.map(tab => {
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
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
              <p className="text-sm text-slate-400">Positions</p>
              <p className="text-2xl font-bold">{portfolio.summary.total_positions}</p>
            </div>
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
              <p className="text-sm text-slate-400">Valeur totale</p>
              <p className="text-2xl font-bold">
                {portfolio.summary.total_value.toLocaleString('fr-FR', {
                  style: 'currency',
                  currency: 'EUR'
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
                  currency: 'EUR'
                })}
              </p>
            </div>
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
              <p className="text-sm text-slate-400">Résilients</p>
              <p className="text-2xl font-bold text-emerald-400">
                {portfolio.summary.resilient_count}/{portfolio.summary.total_positions}
              </p>
              <p className="text-xs text-slate-500">
                {portfolio.summary.resilient_percent}%
              </p>
            </div>
          </div>

          {/* Positions Table */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-900/50">
                <tr>
                  <th className="text-left p-4 text-sm font-medium text-slate-400">Position</th>
                  <th className="text-right p-4 text-sm font-medium text-slate-400">Qté</th>
                  <th className="text-right p-4 text-sm font-medium text-slate-400">Prix actuel</th>
                  <th className="text-right p-4 text-sm font-medium text-slate-400">P&L</th>
                  <th className="text-center p-4 text-sm font-medium text-slate-400">Status</th>
                  <th className="text-center p-4 text-sm font-medium text-slate-400">Actions</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.positions.map((pos, idx) => (
                  <tr key={idx} className="border-t border-slate-700/50 hover:bg-slate-700/20">
                    <td className="p-4">
                      <div>
                        <span className="font-medium">{pos.symbol}</span>
                        <p className="text-sm text-slate-400 truncate max-w-xs">
                          {pos.description}
                        </p>
                      </div>
                    </td>
                    <td className="text-right p-4">{pos.quantity}</td>
                    <td className="text-right p-4">
                      {pos.current_price?.toLocaleString('fr-FR', {
                        style: 'currency',
                        currency: pos.currency || 'EUR'
                      })}
                    </td>
                    <td className="text-right p-4">
                      <span className={pos.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                        {pos.pnl >= 0 ? '+' : ''}{pos.pnl_percent?.toFixed(2)}%
                      </span>
                    </td>
                    <td className="text-center p-4">
                      {pos.is_resilient === true ? (
                        <span className="inline-flex items-center gap-1 text-emerald-400">
                          <CheckCircle className="w-4 h-4" />
                          Résilient
                        </span>
                      ) : pos.is_resilient === false ? (
                        <span className="inline-flex items-center gap-1 text-yellow-400">
                          <AlertCircle className="w-4 h-4" />
                          À surveiller
                        </span>
                      ) : (
                        <span className="text-slate-500">-</span>
                      )}
                    </td>
                    <td className="text-center p-4">
                      <div className="flex items-center justify-center gap-2">
                        <button
                          onClick={() => {
                            tradeFromPosition(pos)
                            setOrderForm({ ...orderForm, buySell: 'Buy' })
                          }}
                          className="bg-emerald-600/20 hover:bg-emerald-600/40 text-emerald-400 px-3 py-1 rounded text-sm font-medium transition-colors"
                        >
                          Acheter
                        </button>
                        <button
                          onClick={() => {
                            tradeFromPosition(pos)
                            setOrderForm({ ...orderForm, buySell: 'Sell' })
                          }}
                          className="bg-red-600/20 hover:bg-red-600/40 text-red-400 px-3 py-1 rounded text-sm font-medium transition-colors"
                        >
                          Vendre
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Trading Tab */}
      {activeTab === 'trade' && (
        <div className="space-y-6">
          {/* Search Section */}
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
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Entrez un symbole ou nom (ex: AAPL, Microsoft)..."
                className="flex-1 bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={handleSearch}
                disabled={loading || !searchQuery.trim()}
                className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-6 py-2 rounded-lg font-medium flex items-center gap-2"
              >
                {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                Rechercher
              </button>
            </div>

            {/* Search Results */}
            {searchResults.length > 0 && (
              <div className="mt-4 space-y-2">
                <p className="text-sm text-slate-400">{searchResults.length} résultat(s)</p>
                <div className="max-h-60 overflow-y-auto space-y-2">
                  {searchResults.map((inst, idx) => (
                    <div
                      key={idx}
                      onClick={() => selectInstrument(inst)}
                      className="bg-slate-900/50 hover:bg-slate-700/50 border border-slate-600 rounded-lg p-3 cursor-pointer transition-colors"
                    >
                      <div className="flex justify-between items-center">
                        <div>
                          <span className="font-medium text-white">{inst.symbol}</span>
                          <span className="text-slate-400 ml-2">{inst.description}</span>
                        </div>
                        <div className="text-right text-sm">
                          <span className="text-slate-400">{inst.asset_type}</span>
                          <span className="text-slate-500 ml-2">{inst.exchange}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
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
                {/* Buy/Sell Toggle */}
                <div>
                  <label className="block text-sm text-slate-400 mb-2">Direction</label>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setOrderForm({ ...orderForm, buySell: 'Buy' })}
                      className={`flex-1 py-3 rounded-lg font-semibold transition-colors ${
                        orderForm.buySell === 'Buy'
                          ? 'bg-emerald-600 text-white'
                          : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                      }`}
                    >
                      Acheter
                    </button>
                    <button
                      onClick={() => setOrderForm({ ...orderForm, buySell: 'Sell' })}
                      className={`flex-1 py-3 rounded-lg font-semibold transition-colors ${
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
                  <label className="block text-sm text-slate-400 mb-2">Type d'ordre</label>
                  <select
                    value={orderForm.orderType}
                    onChange={(e) => setOrderForm({ ...orderForm, orderType: e.target.value })}
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="Market">Market (au marché)</option>
                    <option value="Limit">Limit (prix limite)</option>
                  </select>
                </div>

                {/* Quantity */}
                <div>
                  <label className="block text-sm text-slate-400 mb-2">Quantité</label>
                  <input
                    type="number"
                    min="1"
                    value={orderForm.quantity}
                    onChange={(e) => setOrderForm({ ...orderForm, quantity: parseInt(e.target.value) || 1 })}
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                {/* Price (for Limit orders) */}
                {orderForm.orderType === 'Limit' && (
                  <div>
                    <label className="block text-sm text-slate-400 mb-2">Prix limite</label>
                    <input
                      type="number"
                      step="0.01"
                      value={orderForm.price}
                      onChange={(e) => setOrderForm({ ...orderForm, price: e.target.value })}
                      placeholder="0.00"
                      className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                )}
              </div>

              {/* Submit Button */}
              <div className="mt-6">
                <button
                  onClick={submitOrder}
                  disabled={loading || (orderForm.orderType === 'Limit' && !orderForm.price)}
                  className={`w-full py-4 rounded-lg font-semibold text-lg transition-colors disabled:opacity-50 ${
                    orderForm.buySell === 'Buy'
                      ? 'bg-emerald-600 hover:bg-emerald-500'
                      : 'bg-red-600 hover:bg-red-500'
                  }`}
                >
                  {loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <RefreshCw className="w-5 h-5 animate-spin" />
                      Envoi en cours...
                    </span>
                  ) : (
                    `${orderForm.buySell === 'Buy' ? 'Acheter' : 'Vendre'} ${orderForm.quantity} ${selectedInstrument.symbol}`
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Help Text */}
          {!selectedInstrument && searchResults.length === 0 && (
            <div className="bg-slate-800/30 border border-slate-700 rounded-xl p-6 text-center">
              <TrendingUp className="w-12 h-12 text-slate-600 mx-auto mb-3" />
              <p className="text-slate-400">
                Recherchez un instrument pour commencer à trader
              </p>
              <p className="text-sm text-slate-500 mt-2">
                Actions, ETFs, et plus disponibles via Saxo Bank
              </p>
            </div>
          )}
        </div>
      )}

      {/* Orders Tab */}
      {activeTab === 'orders' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold">Ordres en cours ({orders.length})</h3>
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
                      <div className={`px-3 py-1 rounded-lg font-semibold text-sm ${
                        order.BuySell === 'Buy'
                          ? 'bg-emerald-600/20 text-emerald-400'
                          : 'bg-red-600/20 text-red-400'
                      }`}>
                        {order.BuySell === 'Buy' ? 'ACHAT' : 'VENTE'}
                      </div>
                      <div>
                        <span className="font-semibold text-white">{order.AssetType}</span>
                        <span className="text-slate-400 ml-2">UIC: {order.Uic}</span>
                      </div>
                    </div>
                    <div className={`px-2 py-1 rounded text-xs font-medium ${
                      order.Status === 'Working' ? 'bg-yellow-600/20 text-yellow-400' :
                      order.Status === 'Filled' ? 'bg-emerald-600/20 text-emerald-400' :
                      'bg-slate-600/20 text-slate-400'
                    }`}>
                      {order.Status === 'Working' ? 'En attente' :
                       order.Status === 'Filled' ? 'Exécuté' : order.Status}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 text-sm">
                    <div>
                      <p className="text-slate-500">Quantité</p>
                      <p className="font-medium">{order.Amount?.toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="text-slate-500">Type</p>
                      <p className="font-medium">{order.OpenOrderType}</p>
                    </div>
                    <div>
                      <p className="text-slate-500">Prix {order.OpenOrderType === 'Limit' ? 'limite' : 'marché'}</p>
                      <p className="font-medium">
                        {order.Price ? order.Price.toFixed(2) : order.MarketPrice?.toFixed(2) || '-'}
                      </p>
                    </div>
                    <div>
                      <p className="text-slate-500">Marché</p>
                      <p className={`font-medium ${order.IsMarketOpen ? 'text-emerald-400' : 'text-yellow-400'}`}>
                        {order.IsMarketOpen ? 'Ouvert' : 'Fermé'}
                      </p>
                    </div>
                  </div>

                  <div className="flex justify-between items-center mt-4 pt-3 border-t border-slate-700/50">
                    <div className="text-xs text-slate-500">
                      {order.Exchange?.Description} • {new Date(order.OrderTime).toLocaleString('fr-FR')}
                    </div>
                    <button
                      onClick={async () => {
                        try {
                          await cancelSaxoOrder(accessToken, order.OrderId, order.AccountKey)
                          setSuccess('Ordre annulé')
                          loadOrders()
                        } catch (err) {
                          setError('Échec de l\'annulation')
                        }
                      }}
                      className="text-red-400 hover:text-red-300 text-xs px-2 py-1 hover:bg-red-600/20 rounded"
                    >
                      Annuler
                    </button>
                  </div>
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
            <h3 className="text-lg font-semibold">Historique des transactions</h3>
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
              <p className="text-slate-400">Aucune transaction récente</p>
            </div>
          ) : (
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
              <table className="w-full">
                <thead className="bg-slate-900/50">
                  <tr>
                    <th className="text-left p-3 text-sm font-medium text-slate-400">Date</th>
                    <th className="text-left p-3 text-sm font-medium text-slate-400">Instrument</th>
                    <th className="text-center p-3 text-sm font-medium text-slate-400">Type</th>
                    <th className="text-right p-3 text-sm font-medium text-slate-400">Quantité</th>
                    <th className="text-right p-3 text-sm font-medium text-slate-400">Prix</th>
                    <th className="text-right p-3 text-sm font-medium text-slate-400">Valeur</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((tx, idx) => (
                    <tr key={tx.TradeId || idx} className="border-t border-slate-700/50 hover:bg-slate-700/20">
                      <td className="p-3 text-sm">
                        {new Date(tx.TradeExecutionTime || tx.TradeDate).toLocaleDateString('fr-FR')}
                      </td>
                      <td className="p-3">
                        <div className="font-medium">{tx.InstrumentSymbol || tx.UnderlyingInstrumentSymbol}</div>
                        <div className="text-xs text-slate-400 truncate max-w-[200px]">{tx.InstrumentDescription}</div>
                      </td>
                      <td className="p-3 text-center">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          tx.TradeEventType === 'Bought' || tx.Direction === 'Bought'
                            ? 'bg-emerald-600/20 text-emerald-400'
                            : 'bg-red-600/20 text-red-400'
                        }`}>
                          {tx.TradeEventType === 'Bought' || tx.Direction === 'Bought' ? 'Achat' : 'Vente'}
                        </span>
                      </td>
                      <td className="p-3 text-right font-medium">
                        {Math.abs(tx.Amount)?.toLocaleString()}
                      </td>
                      <td className="p-3 text-right">
                        {tx.Price?.toFixed(4)}
                      </td>
                      <td className="p-3 text-right font-medium">
                        {tx.TradedValue?.toLocaleString()} {tx.ClientCurrency}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Loading state */}
      {loading && !portfolio && (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
        </div>
      )}
    </div>
  )
}
