import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, Download, Plus, TrendingUp, ChevronDown, BarChart3, Coins, PieChart, Wallet, Settings } from 'lucide-react'
import { analyzeTicker, analyzeBatch, getMarkets, getMarketTickers, exportCSVFromData, searchTickers } from './api'
import StockTable from './components/StockTable'
import StockChart from './components/StockChart'
import Filters from './components/Filters'
import SaxoPortfolio from './components/SaxoPortfolio'
import DataSourceToggle from './components/DataSourceToggle'
import ProfileConfig from './components/ProfileConfig'

// Process OAuth callback at app level to ensure it's handled
const processOAuthCallback = async () => {
  const urlParams = new URLSearchParams(window.location.search)
  const code = urlParams.get('code')
  const state = urlParams.get('state')

  if (!code) return null

  // IMPORTANT: Nettoyer l'URL immédiatement pour éviter les doubles appels lors d'un refresh
  window.history.replaceState({}, '', window.location.pathname)

  console.log('App: Processing OAuth callback with code:', code.substring(0, 20) + '...')

  try {
    let url = `/api/saxo/auth/callback?code=${encodeURIComponent(code)}`
    if (state) {
      url += `&state=${encodeURIComponent(state)}`
    }

    console.log('App: Fetching callback URL:', url)

    // Ajouter un timeout de 30 secondes
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 30000)

    const response = await fetch(url, { signal: controller.signal })
    clearTimeout(timeoutId)

    console.log('App: Got response, status:', response.status)
    const data = await response.json()

    console.log('App: OAuth callback response:', response.status, data)

    if (!response.ok) {
      const errorMsg = data.detail || data.error_description || data.error || `Erreur ${response.status}`
      return { error: typeof errorMsg === 'object' ? JSON.stringify(errorMsg) : errorMsg }
    }

    if (data.access_token) {
      return { success: true, access_token: data.access_token }
    }

    return { error: data.detail || 'Réponse inattendue' }
  } catch (err) {
    console.error('App: OAuth callback exception:', err)
    return { error: 'Échec de connexion: ' + err.message }
  }
}

// Tab configuration (sans config - c'est en haut a droite)
const TABS = [
  { id: 'stocks', label: 'Actions', icon: BarChart3, color: 'emerald' },
  { id: 'etfs', label: 'ETFs', icon: PieChart, color: 'blue' },
  { id: 'crypto', label: 'Crypto', icon: Coins, color: 'orange' },
  { id: 'saxo', label: 'Mon Portfolio', icon: Wallet, color: 'purple' }
]

// Flatten API response to match frontend expectations
const flattenStockData = (stock) => ({
  ...stock,
  // Flatten performances
  perf_3m: stock.performances?.perf_3m ?? null,
  perf_6m: stock.performances?.perf_6m ?? null,
  perf_1y: stock.performances?.perf_1y ?? null,
  perf_3y: stock.performances?.perf_3y ?? null,
  perf_5y: stock.performances?.perf_5y ?? null,
  // Flatten info
  name: stock.info?.name ?? stock.name,
  sector: stock.info?.sector ?? stock.sector,
  dividend_yield: stock.info?.dividend_yield ?? stock.dividend_yield,
})

function App() {
  const [stocks, setStocks] = useState([])
  const [markets, setMarkets] = useState([])
  const [marketLoadState, setMarketLoadState] = useState({}) // Track loaded tickers per market
  const [activeTab, setActiveTab] = useState('stocks') // Current asset type tab
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(null) // Which market is loading more
  const [error, setError] = useState(null)
  const [tickerInput, setTickerInput] = useState('')
  const [selectedStock, setSelectedStock] = useState(null)
  const [filters, setFilters] = useState({
    resilientOnly: false,
    maxVolatility: 100
  })
  const [tickerToTrade, setTickerToTrade] = useState(null)
  const [showConfig, setShowConfig] = useState(false)
  const [oauthResult, setOauthResult] = useState(null) // Result from OAuth callback

  useEffect(() => {
    loadMarkets()

    // Détecter et traiter le callback OAuth Saxo au niveau App
    const urlParams = new URLSearchParams(window.location.search)
    const code = urlParams.get('code')
    if (code) {
      setActiveTab('saxo')
      // Process callback immediately
      processOAuthCallback().then(result => {
        console.log('App: OAuth result:', result)
        setOauthResult(result)
      })
    }
  }, [])

  const loadMarkets = async () => {
    try {
      const data = await getMarkets()
      setMarkets(data.markets)
    } catch (err) {
      console.error('Failed to load markets:', err)
    }
  }

  const addTicker = async () => {
    if (!tickerInput.trim()) return
    setLoading(true)
    setError(null)

    const input = tickerInput.trim()

    // Détecter si c'est probablement un nom (contient des espaces ou > 6 caractères)
    const isProbablyName = input.includes(' ') || input.length > 6

    try {
      // Essayer d'abord comme un ticker direct
      const result = await analyzeTicker(input)
      if (result.error) {
        // Si échec et c'est probablement un nom, essayer la recherche
        if (isProbablyName) {
          const searchResult = await searchTickers(input, activeTab)
          if (searchResult.results && searchResult.results.length > 0) {
            const suggestions = searchResult.results.slice(0, 3).map(r => r.symbol).join(', ')
            setError(`"${input}" n'est pas un symbole valide. Essayez: ${suggestions}`)
          } else {
            setError(`"${input}" non trouvé. Entrez un symbole de ticker (ex: AAPL, MSFT, IWDA.AS)`)
          }
        } else {
          setError(`Ticker "${input}" non trouvé`)
        }
      } else {
        // Ajouter l'assetType (onglet actif) au ticker ajouté manuellement
        const flatResult = { ...flattenStockData(result), assetType: activeTab }
        setStocks(prev => {
          const exists = prev.find(s => s.ticker === flatResult.ticker)
          if (exists) {
            return prev.map(s => s.ticker === flatResult.ticker ? flatResult : s)
          }
          return [...prev, flatResult]
        })
        setTickerInput('')
      }
    } catch (err) {
      // En cas d'erreur, essayer la recherche pour donner des suggestions
      if (isProbablyName) {
        try {
          const searchResult = await searchTickers(input, activeTab)
          if (searchResult.results && searchResult.results.length > 0) {
            const suggestions = searchResult.results.slice(0, 3).map(r => `${r.symbol} (${r.name})`).join(', ')
            setError(`Essayez un de ces symboles: ${suggestions}`)
          } else {
            setError(`"${input}" non trouvé. Entrez un symbole de ticker valide.`)
          }
        } catch {
          setError(err.message)
        }
      } else {
        setError(err.message)
      }
    } finally {
      setLoading(false)
    }
  }

  const loadMarket = async (marketId, loadMore = false) => {
    if (loadMore) {
      setLoadingMore(marketId)
    } else {
      setLoading(true)
    }
    setError(null)

    try {
      // Get current offset for this market
      const currentState = marketLoadState[marketId] || { loaded: 0, total: 0 }
      const offset = loadMore ? currentState.loaded : 0
      const limit = 10

      const marketData = await getMarketTickers(marketId, limit, offset)
      const result = await analyzeBatch(marketData.tickers)
      // Ajouter l'assetType (onglet actif) à chaque stock
      const newStocks = result.results.filter(r => !r.error).map(s => ({
        ...flattenStockData(s),
        assetType: activeTab
      }))

      setStocks(prev => {
        const existing = new Set(prev.map(s => s.ticker))
        const toAdd = newStocks.filter(s => !existing.has(s.ticker))
        return [...prev, ...toAdd]
      })

      // Update market load state
      setMarketLoadState(prev => ({
        ...prev,
        [marketId]: {
          loaded: offset + marketData.tickers.length,
          total: marketData.total,
          hasMore: marketData.has_more,
          name: marketData.name
        }
      }))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
      setLoadingMore(null)
    }
  }

  const loadMoreFromMarket = (marketId) => {
    loadMarket(marketId, true)
  }

  const refreshAll = async () => {
    // Filtrer les stocks de l'onglet actif
    const stocksToRefresh = stocks.filter(s => s.assetType === activeTab)
    if (stocksToRefresh.length === 0) return

    setLoading(true)
    setError(null)
    try {
      const tickers = stocksToRefresh.map(s => s.ticker)
      const result = await analyzeBatch(tickers)
      const refreshedStocks = result.results.filter(r => !r.error).map(s => ({
        ...flattenStockData(s),
        assetType: activeTab
      }))

      // Mettre à jour seulement les stocks de l'onglet actif
      setStocks(prev => {
        const otherStocks = prev.filter(s => s.assetType !== activeTab)
        return [...otherStocks, ...refreshedStocks]
      })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleExportCSV = () => {
    if (filteredStocks.length === 0) return
    // Export what's displayed (filtered stocks)
    exportCSVFromData(filteredStocks)
  }

  const removeStock = (ticker) => {
    setStocks(prev => prev.filter(s => s.ticker !== ticker))
    if (selectedStock?.ticker === ticker) {
      setSelectedStock(null)
    }
  }

  // Handle trade request from stock table
  const handleTrade = (stock) => {
    setTickerToTrade(stock.ticker)
    setActiveTab('saxo')
  }

  // Filtrer les stocks par onglet actif ET par les filtres utilisateur
  const filteredStocks = stocks.filter(stock => {
    // Filtrer par type d'actif (onglet actif)
    if (stock.assetType && stock.assetType !== activeTab) return false
    // Filtres utilisateur
    if (filters.resilientOnly && !stock.is_resilient) return false
    if (stock.volatility > filters.maxVolatility) return false
    return true
  })

  // Compter les stocks résilients de l'onglet actif seulement
  const resilientCount = filteredStocks.filter(s => s.is_resilient).length

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 mb-2">
              <TrendingUp className="w-10 h-10 text-emerald-500" />
              <h1 className="text-3xl font-bold">Stock Analyzer</h1>
            </div>
            {/* Data Source Toggle + Settings */}
            <div className="flex items-center gap-3">
              <DataSourceToggle compact={true} />
              <button
                onClick={() => setShowConfig(true)}
                className="p-2.5 rounded-lg bg-slate-700/50 hover:bg-slate-600/50 border border-slate-600 hover:border-slate-500 transition-all"
                title="Parametres"
              >
                <Settings className="w-5 h-5 text-slate-300" />
              </button>
            </div>
          </div>
          <p className="text-slate-400">
            Multi-period resilience analysis - Find stocks with positive performance across all timeframes
          </p>
        </div>

        {/* Controls */}
        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-xl p-6 mb-6">
          {/* Add ticker */}
          <div className="flex gap-3 mb-6">
            <input
              type="text"
              value={tickerInput}
              onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === 'Enter' && addTicker()}
              placeholder="Symbole ticker (ex: AAPL, MSFT, IWDA.AS)"
              className="flex-1 bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
            />
            <button
              onClick={addTicker}
              disabled={loading}
              className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-6 py-2.5 rounded-lg font-medium flex items-center gap-2"
            >
              <Plus className="w-5 h-5" />
              Add
            </button>
          </div>

          {/* Asset Type Tabs */}
          <div className="mb-6">
            <div className="flex gap-2 mb-4 border-b border-slate-700 pb-4">
              {TABS.map(tab => {
                const Icon = tab.icon
                const isActive = activeTab === tab.id
                const tabMarkets = markets.filter(m => m.type === tab.id)
                const totalCount = tabMarkets.reduce((sum, m) => sum + m.count, 0)

                return (
                  <button
                    key={tab.id}
                    onClick={() => {
                      setActiveTab(tab.id)
                      if (tab.id !== 'saxo') setTickerToTrade(null)
                    }}
                    className={`flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium transition-all ${
                      isActive
                        ? tab.id === 'stocks' ? 'bg-emerald-600 text-white'
                        : tab.id === 'etfs' ? 'bg-blue-600 text-white'
                        : tab.id === 'crypto' ? 'bg-orange-600 text-white'
                        : 'bg-purple-600 text-white'
                        : 'bg-slate-700/50 text-slate-300 hover:bg-slate-600/50'
                    }`}
                  >
                    <Icon className="w-5 h-5" />
                    {tab.label}
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      isActive ? 'bg-white/20' : 'bg-slate-600'
                    }`}>
                      {totalCount}
                    </span>
                  </button>
                )
              })}
            </div>

            {/* Saxo Portfolio Tab */}
            {activeTab === 'saxo' && (
              <SaxoPortfolio
                initialTicker={tickerToTrade}
                key={tickerToTrade || 'saxo'} // Force re-render when ticker changes
                oauthResult={oauthResult}
                onOauthResultHandled={() => setOauthResult(null)}
              />
            )}

            {/* Market presets for active tab (not for Saxo) */}
            {activeTab !== 'saxo' && (
              <>
                <span className="text-sm text-slate-400 mb-2 block">
                  {activeTab === 'stocks' && 'Marchés Actions :'}
                  {activeTab === 'etfs' && 'ETFs disponibles :'}
                  {activeTab === 'crypto' && 'Cryptomonnaies :'}
                </span>
            <div className="flex flex-wrap gap-2">
              {markets
                .filter(market => market.type === activeTab)
                .map(market => {
                  const state = marketLoadState[market.id]
                  const hasMore = state?.hasMore
                  const loaded = state?.loaded || 0
                  const total = state?.total || market.count

                  const buttonColor = activeTab === 'stocks'
                    ? 'hover:border-emerald-500'
                    : activeTab === 'etfs'
                    ? 'hover:border-blue-500'
                    : 'hover:border-orange-500'

                  const loadMoreColor = activeTab === 'stocks'
                    ? 'bg-emerald-600/50 hover:bg-emerald-500/50 border-emerald-600'
                    : activeTab === 'etfs'
                    ? 'bg-blue-600/50 hover:bg-blue-500/50 border-blue-600'
                    : 'bg-orange-600/50 hover:bg-orange-500/50 border-orange-600'

                  return (
                    <div key={market.id} className="flex items-center gap-1">
                      <button
                        onClick={() => loadMarket(market.id)}
                        disabled={loading || loadingMore}
                        className={`bg-slate-700/50 hover:bg-slate-600/50 disabled:opacity-50 border border-slate-600 ${buttonColor} px-4 py-2 rounded-lg text-sm font-medium transition-colors`}
                      >
                        {market.name} ({loaded > 0 ? `${loaded}/${total}` : total})
                      </button>
                      {hasMore && (
                        <button
                          onClick={() => loadMoreFromMarket(market.id)}
                          disabled={loading || loadingMore === market.id}
                          className={`${loadMoreColor} disabled:opacity-50 border px-2 py-2 rounded-lg text-sm`}
                          title={`Load 10 more from ${market.name}`}
                        >
                          {loadingMore === market.id ? (
                            <RefreshCw className="w-4 h-4 animate-spin" />
                          ) : (
                            <ChevronDown className="w-4 h-4" />
                          )}
                        </button>
                      )}
                    </div>
                  )
                })}
            </div>
              </>
            )}
          </div>

          {/* Actions - only show when not on Saxo tab */}
          {activeTab !== 'saxo' && (
          <div className="flex flex-wrap items-center justify-between gap-4">
            <Filters filters={filters} onChange={setFilters} />

            <div className="flex gap-3">
              <button
                onClick={refreshAll}
                disabled={loading || filteredStocks.length === 0}
                className="bg-slate-700/50 hover:bg-slate-600/50 disabled:opacity-50 border border-slate-600 px-4 py-2 rounded-lg flex items-center gap-2"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
              <button
                onClick={handleExportCSV}
                disabled={filteredStocks.length === 0}
                className="bg-slate-700/50 hover:bg-slate-600/50 disabled:opacity-50 border border-slate-600 px-4 py-2 rounded-lg flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                Export CSV
              </button>
            </div>
          </div>
          )}
        </div>

        {/* Error message */}
        {error && (
          <div className="bg-red-900/30 border border-red-700 rounded-xl p-4 mb-6">
            <p className="text-red-400">{error}</p>
          </div>
        )}

        {/* Stats, Loading, Table, Chart - only show when not on Saxo tab */}
        {activeTab !== 'saxo' && (
          <>
            <div className="flex items-center gap-4 mb-4">
              <span className="text-slate-400">
                Showing <span className="text-white font-semibold">{filteredStocks.length}</span> {activeTab === 'etfs' ? 'ETFs' : activeTab === 'crypto' ? 'cryptos' : 'actions'}
              </span>
              <span className="text-slate-500">|</span>
              <span className="text-emerald-400">
                <span className="font-semibold">{resilientCount}</span> resilient
              </span>
            </div>

            {/* Loading indicator */}
            {loading && (
              <div className="flex items-center justify-center py-12">
                <div className="flex items-center gap-3 text-slate-400">
                  <RefreshCw className="w-6 h-6 animate-spin" />
                  <span>Analyzing stocks...</span>
                </div>
              </div>
            )}

            {/* Main content */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Table */}
              <div className="lg:col-span-2">
                <StockTable
                  stocks={filteredStocks}
                  onSelect={setSelectedStock}
                  onRemove={removeStock}
                  onTrade={handleTrade}
                  selectedTicker={selectedStock?.ticker}
                />
              </div>

              {/* Chart */}
              <div className="lg:col-span-1">
                <StockChart stock={selectedStock} />
              </div>
            </div>

            {/* Empty state */}
            {!loading && stocks.length === 0 && (
              <div className="text-center py-16">
                <TrendingUp className="w-16 h-16 text-slate-600 mx-auto mb-4" />
                <h3 className="text-xl font-medium text-slate-400 mb-2">No stocks analyzed yet</h3>
                <p className="text-slate-500">Add a ticker or load a market preset to get started</p>
              </div>
            )}
          </>
        )}
      </div>

      {/* Configuration Panel (Overlay) */}
      {showConfig && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 overflow-auto">
          <div className="min-h-screen py-8">
            <ProfileConfig onClose={() => setShowConfig(false)} />
          </div>
        </div>
      )}
    </div>
  )
}

export default App
