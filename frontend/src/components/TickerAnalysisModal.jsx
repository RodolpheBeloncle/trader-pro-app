import { useState, useEffect } from 'react'
import {
  X, BarChart2, TrendingUp, Newspaper, Lightbulb, History,
  RefreshCw, ExternalLink, AlertTriangle, CheckCircle, DollarSign,
  Activity, Target, Shield, Calendar, Percent, ArrowUp, ArrowDown
} from 'lucide-react'

const API_BASE = '/api'

/**
 * TickerAnalysisModal - Modal d'analyse complete d'un ticker
 *
 * 5 Onglets:
 * 1. Analyse - Vue d'ensemble et metriques fondamentales
 * 2. Technique - Indicateurs techniques et niveaux
 * 3. News & Sentiment - Actualites et analyse de sentiment
 * 4. Decision - Aide a la decision avec scoring
 * 5. Backtest - Backtest rapide sur 1-5 ans
 */
export default function TickerAnalysisModal({ ticker, position, onClose }) {
  const [activeTab, setActiveTab] = useState('analysis')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [data, setData] = useState({
    analysis: null,
    technical: null,
    news: null,
    decision: null,
    backtest: null
  })

  // Nettoyer le ticker (enlever :exchange si present)
  const cleanTicker = ticker?.split(':')[0]?.toUpperCase() || ticker

  const TABS = [
    { id: 'analysis', label: 'Analyse', icon: BarChart2 },
    { id: 'technical', label: 'Technique', icon: TrendingUp },
    { id: 'news', label: 'News', icon: Newspaper },
    { id: 'decision', label: 'Decision', icon: Lightbulb },
    { id: 'backtest', label: 'Backtest', icon: History }
  ]

  useEffect(() => {
    if (cleanTicker) {
      loadTabData(activeTab)
    }
  }, [cleanTicker, activeTab])

  const loadTabData = async (tab) => {
    if (data[tab]) {
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)

    try {
      let result = null

      switch (tab) {
        case 'analysis':
          result = await fetchAnalysis(cleanTicker)
          break
        case 'technical':
          result = await fetchTechnical(cleanTicker)
          break
        case 'news':
          result = await fetchNews(cleanTicker)
          break
        case 'decision':
          result = await fetchDecision(cleanTicker)
          break
        case 'backtest':
          result = await fetchBacktest(cleanTicker)
          break
      }

      setData(prev => ({ ...prev, [tab]: result }))
    } catch (err) {
      console.error(`Error loading ${tab}:`, err)
      setError(err.message || 'Erreur de chargement')
    } finally {
      setLoading(false)
    }
  }

  // ==========================================================================
  // FETCH FUNCTIONS - Routes corrigees
  // ==========================================================================

  const fetchAnalysis = async (symbol) => {
    try {
      // Route: GET /api/stocks/analyze?ticker=SYMBOL
      const res = await fetch(`${API_BASE}/stocks/analyze?ticker=${encodeURIComponent(symbol)}`)
      if (res.ok) {
        const data = await res.json()
        return {
          symbol: data.ticker,
          name: data.info?.name || symbol,
          sector: data.info?.sector || 'N/A',
          market_cap: null,
          pe_ratio: null,
          dividend_yield: data.info?.dividend_yield,
          beta: null,
          price: data.current_price,
          change_percent: data.performances?.perf_1y,
          volatility: data.volatility,
          is_resilient: data.is_resilient,
          score: data.score
        }
      }
    } catch (e) {
      console.error('Fetch analysis error:', e)
    }

    // Fallback avec position
    return {
      symbol,
      name: position?.description || symbol,
      sector: 'N/A',
      market_cap: null,
      pe_ratio: null,
      dividend_yield: null,
      beta: null,
      price: position?.current_price || null,
      change_percent: position?.pnl_percent || null
    }
  }

  const fetchTechnical = async (symbol) => {
    try {
      // Route: GET /api/stocks/technical/{symbol}
      const res = await fetch(`${API_BASE}/stocks/technical/${encodeURIComponent(symbol)}`)
      if (res.ok) {
        return await res.json()
      }
    } catch (e) {
      console.error('Fetch technical error:', e)
    }

    // Fallback - calculer depuis position
    const price = position?.current_price || 100
    return {
      trend: position?.pnl_percent > 0 ? 'bullish' : position?.pnl_percent < 0 ? 'bearish' : 'neutral',
      rsi: 50,
      macd: { value: 0, signal: 0, histogram: 0 },
      moving_averages: {
        sma_20: price * 0.98,
        sma_50: price * 0.95,
        sma_200: price * 0.90
      },
      support_resistance: {
        support: price * 0.92,
        resistance: price * 1.08
      },
      volume_trend: 'normal'
    }
  }

  const fetchNews = async (symbol) => {
    try {
      // Route: GET /api/news/{ticker}
      const res = await fetch(`${API_BASE}/news/${encodeURIComponent(symbol)}?limit=10`)
      if (res.ok) {
        const articles = await res.json()
        // Calculer sentiment global
        const sentiments = articles.filter(a => a.sentiment_score != null)
        const avgScore = sentiments.length > 0
          ? sentiments.reduce((sum, a) => sum + a.sentiment_score, 0) / sentiments.length
          : 50

        return {
          articles: articles.map(a => ({
            title: a.headline,
            source: a.source,
            url: a.url,
            date: a.published_at,
            sentiment: a.sentiment
          })),
          sentiment: avgScore > 60 ? 'positive' : avgScore < 40 ? 'negative' : 'neutral',
          sentiment_score: avgScore
        }
      }
    } catch (e) {
      console.error('Fetch news error:', e)
    }

    return {
      articles: [],
      sentiment: 'neutral',
      sentiment_score: 50
    }
  }

  const fetchDecision = async (symbol) => {
    try {
      // Route: GET /api/stocks/decision/{symbol}
      const res = await fetch(`${API_BASE}/stocks/decision/${encodeURIComponent(symbol)}`)
      if (res.ok) {
        return await res.json()
      }
    } catch (e) {
      console.error('Fetch decision error:', e)
    }

    // Fallback base sur position
    const pnlPercent = position?.pnl_percent || 0
    let decision = 'hold'
    let confidence = 55

    if (pnlPercent > 20) {
      decision = 'take_profit'
      confidence = 70
    } else if (pnlPercent > 5) {
      decision = 'hold'
      confidence = 65
    } else if (pnlPercent < -10) {
      decision = 'review'
      confidence = 60
    } else if (pnlPercent < -5) {
      decision = 'monitor'
      confidence = 55
    }

    return {
      decision,
      confidence,
      factors: [
        { name: 'Performance', score: Math.max(0, Math.min(100, 50 + pnlPercent * 2)) },
        { name: 'Tendance', score: pnlPercent > 0 ? 65 : 35 },
        { name: 'Risque/Reward', score: 50 },
        { name: 'Momentum', score: pnlPercent > 0 ? 60 : 40 }
      ],
      summary: pnlPercent > 5
        ? 'Position en profit. Considerez un trailing stop pour proteger les gains.'
        : pnlPercent < -5
        ? 'Position en perte. Evaluez si les fondamentaux ont change.'
        : 'Position stable. Continuez a surveiller.'
    }
  }

  const fetchBacktest = async (symbol) => {
    try {
      // Route: GET /api/backtest/simple/{symbol}
      const res = await fetch(`${API_BASE}/backtest/simple/${encodeURIComponent(symbol)}?years=3`)
      if (res.ok) {
        return await res.json()
      }
    } catch (e) {
      console.error('Fetch backtest error:', e)
    }

    return {
      period: '3 ans',
      cagr: null,
      volatility: null,
      sharpe_ratio: null,
      max_drawdown: null,
      total_return: null,
      message: 'Backtest non disponible. Utilisez le module complet pour plus de details.'
    }
  }

  if (!ticker) return null

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 border border-slate-700 rounded-xl w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-slate-700 flex-shrink-0">
          <div className="flex justify-between items-start">
            <div>
              <h2 className="text-2xl font-bold flex items-center gap-3">
                <Activity className="w-7 h-7 text-blue-400" />
                {cleanTicker}
                {ticker !== cleanTicker && (
                  <span className="text-sm text-slate-500 font-normal">({ticker})</span>
                )}
              </h2>
              {position && (
                <div className="mt-2 flex items-center gap-4 text-sm">
                  <span className="text-slate-400">
                    Prix: <span className="text-white font-mono">{position.current_price?.toFixed(2)}€</span>
                  </span>
                  <span className={position.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                    P&L: {position.pnl >= 0 ? '+' : ''}{position.pnl?.toFixed(2)}€
                    ({position.pnl_percent?.toFixed(1)}%)
                  </span>
                </div>
              )}
            </div>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-white p-2"
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          {/* Tabs */}
          <div className="mt-4 flex gap-2 overflow-x-auto">
            {TABS.map(tab => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium whitespace-nowrap transition-colors ${
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
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <RefreshCw className="w-10 h-10 animate-spin text-blue-500" />
            </div>
          ) : error ? (
            <div className="bg-red-900/30 border border-red-700 rounded-lg p-6 text-center">
              <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-3" />
              <p className="text-red-400">{error}</p>
              <button
                onClick={() => {
                  setData(prev => ({ ...prev, [activeTab]: null }))
                  loadTabData(activeTab)
                }}
                className="mt-4 text-blue-400 hover:underline"
              >
                Reessayer
              </button>
            </div>
          ) : (
            <>
              {activeTab === 'analysis' && <AnalysisTab data={data.analysis} />}
              {activeTab === 'technical' && <TechnicalTab data={data.technical} />}
              {activeTab === 'news' && <NewsTab data={data.news} />}
              {activeTab === 'decision' && <DecisionTab data={data.decision} />}
              {activeTab === 'backtest' && <BacktestTab data={data.backtest} ticker={cleanTicker} />}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ==========================================================================
// TAB COMPONENTS
// ==========================================================================

function AnalysisTab({ data }) {
  if (!data) return null

  const metrics = [
    { label: 'Secteur', value: data.sector || 'N/A' },
    { label: 'Market Cap', value: data.market_cap ? `${(data.market_cap / 1e9).toFixed(1)}B` : 'N/A' },
    { label: 'P/E Ratio', value: data.pe_ratio?.toFixed(1) || 'N/A' },
    { label: 'Dividend Yield', value: data.dividend_yield ? `${data.dividend_yield.toFixed(2)}%` : 'N/A' },
    { label: 'Volatilite', value: data.volatility ? `${data.volatility.toFixed(1)}%` : 'N/A' },
    { label: 'Score', value: data.score || 'N/A' }
  ]

  return (
    <div className="space-y-6">
      {/* Header avec nom */}
      <div className="bg-slate-900/50 rounded-lg p-4">
        <h3 className="text-xl font-semibold">{data.name}</h3>
        <p className="text-slate-400 mt-1">{data.symbol}</p>
        {data.is_resilient && (
          <span className="inline-flex items-center gap-1 mt-2 px-2 py-1 bg-emerald-900/50 text-emerald-400 rounded text-sm">
            <CheckCircle className="w-4 h-4" />
            Resilient
          </span>
        )}
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {metrics.map((m, i) => (
          <div key={i} className="bg-slate-900/50 rounded-lg p-4">
            <p className="text-xs text-slate-500 uppercase tracking-wide">{m.label}</p>
            <p className="text-lg font-semibold mt-1">{m.value}</p>
          </div>
        ))}
      </div>

      {/* Prix et variation */}
      {data.price && (
        <div className="bg-slate-900/50 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-400">Prix actuel</p>
              <p className="text-3xl font-bold">{data.price.toFixed(2)}€</p>
            </div>
            {data.change_percent != null && (
              <div className={`flex items-center gap-2 text-2xl font-semibold ${
                data.change_percent >= 0 ? 'text-emerald-400' : 'text-red-400'
              }`}>
                {data.change_percent >= 0 ? <ArrowUp /> : <ArrowDown />}
                {Math.abs(data.change_percent).toFixed(1)}%
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function TechnicalTab({ data }) {
  if (!data) return null

  const getTrendColor = (trend) => {
    if (trend === 'bullish') return 'text-emerald-400'
    if (trend === 'bearish') return 'text-red-400'
    return 'text-yellow-400'
  }

  const getRsiColor = (rsi) => {
    if (rsi > 70) return 'text-red-400'
    if (rsi < 30) return 'text-emerald-400'
    return 'text-slate-300'
  }

  return (
    <div className="space-y-6">
      {/* Trend */}
      <div className="bg-slate-900/50 rounded-lg p-4">
        <div className="flex items-center justify-between">
          <span className="text-slate-400">Tendance</span>
          <span className={`font-semibold ${getTrendColor(data.trend)}`}>
            {data.trend === 'bullish' ? 'Haussiere' : data.trend === 'bearish' ? 'Baissiere' : 'Neutre'}
          </span>
        </div>
      </div>

      {/* RSI */}
      <div className="bg-slate-900/50 rounded-lg p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-slate-400">RSI (14)</span>
          <span className={`font-mono font-semibold ${getRsiColor(data.rsi)}`}>{data.rsi}</span>
        </div>
        <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
          <div
            className={`h-full ${data.rsi > 70 ? 'bg-red-500' : data.rsi < 30 ? 'bg-emerald-500' : 'bg-blue-500'}`}
            style={{ width: `${data.rsi}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-slate-500 mt-1">
          <span>Survendu (30)</span>
          <span>Surachete (70)</span>
        </div>
      </div>

      {/* Moving Averages */}
      <div className="bg-slate-900/50 rounded-lg p-4">
        <h4 className="font-medium text-slate-300 mb-3">Moyennes Mobiles</h4>
        <div className="space-y-2">
          {data.moving_averages && Object.entries(data.moving_averages).map(([key, value]) => (
            <div key={key} className="flex justify-between">
              <span className="text-slate-400">{key.toUpperCase().replace('_', ' ')}</span>
              <span className="font-mono">{value?.toFixed(2) || 'N/A'}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Support/Resistance */}
      {data.support_resistance && (
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-red-900/20 border border-red-800/50 rounded-lg p-4 text-center">
            <p className="text-sm text-red-400 mb-1">Support</p>
            <p className="text-xl font-mono font-semibold text-red-300">
              {data.support_resistance.support?.toFixed(2) || 'N/A'}
            </p>
          </div>
          <div className="bg-emerald-900/20 border border-emerald-800/50 rounded-lg p-4 text-center">
            <p className="text-sm text-emerald-400 mb-1">Resistance</p>
            <p className="text-xl font-mono font-semibold text-emerald-300">
              {data.support_resistance.resistance?.toFixed(2) || 'N/A'}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

function NewsTab({ data }) {
  if (!data) return null

  const getSentimentColor = (sentiment) => {
    if (sentiment === 'positive' || sentiment === 'bullish') return 'text-emerald-400'
    if (sentiment === 'negative' || sentiment === 'bearish') return 'text-red-400'
    return 'text-yellow-400'
  }

  return (
    <div className="space-y-6">
      {/* Sentiment */}
      <div className="bg-slate-900/50 rounded-lg p-4">
        <div className="flex items-center justify-between">
          <span className="text-slate-400">Sentiment Global</span>
          <span className={`font-semibold ${getSentimentColor(data.sentiment)}`}>
            {data.sentiment === 'positive' ? 'Positif' : data.sentiment === 'negative' ? 'Negatif' : 'Neutre'}
          </span>
        </div>
        {data.sentiment_score != null && (
          <div className="mt-3">
            <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
              <div
                className={`h-full ${
                  data.sentiment_score > 60 ? 'bg-emerald-500' :
                  data.sentiment_score < 40 ? 'bg-red-500' : 'bg-yellow-500'
                }`}
                style={{ width: `${data.sentiment_score}%` }}
              />
            </div>
            <div className="flex justify-between text-xs text-slate-500 mt-1">
              <span>Negatif</span>
              <span>{data.sentiment_score.toFixed(0)}%</span>
              <span>Positif</span>
            </div>
          </div>
        )}
      </div>

      {/* Articles */}
      {data.articles && data.articles.length > 0 ? (
        <div className="space-y-3">
          {data.articles.map((article, i) => (
            <div key={i} className="bg-slate-900/50 rounded-lg p-4 hover:bg-slate-700/50 transition-colors">
              <a
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-start gap-3"
              >
                <Newspaper className="w-5 h-5 text-slate-400 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <h4 className="font-medium text-white hover:text-blue-400">{article.title}</h4>
                  <p className="text-sm text-slate-400 mt-1">{article.source}</p>
                  {article.date && (
                    <p className="text-xs text-slate-500 mt-1">{article.date}</p>
                  )}
                </div>
                <ExternalLink className="w-4 h-4 text-slate-500" />
              </a>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-slate-900/50 rounded-lg p-8 text-center">
          <Newspaper className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400">Aucune actualite recente</p>
          <p className="text-sm text-slate-500 mt-2">
            Les news sont mises en cache et rafraichies periodiquement.
          </p>
        </div>
      )}
    </div>
  )
}

function DecisionTab({ data }) {
  if (!data) return null

  const getDecisionColor = (decision) => {
    if (['strong_buy', 'buy', 'take_profit'].includes(decision)) return 'bg-emerald-600'
    if (['hold', 'monitor'].includes(decision)) return 'bg-blue-600'
    if (['review', 'sell', 'stop_loss'].includes(decision)) return 'bg-red-600'
    return 'bg-slate-600'
  }

  const getDecisionLabel = (decision) => {
    const labels = {
      strong_buy: 'Achat Fort',
      buy: 'Acheter',
      hold: 'Conserver',
      monitor: 'Surveiller',
      review: 'A Revoir',
      sell: 'Vendre',
      take_profit: 'Prendre Profit',
      stop_loss: 'Stop Loss'
    }
    return labels[decision] || decision
  }

  return (
    <div className="space-y-6">
      {/* Decision principale */}
      <div className={`${getDecisionColor(data.decision)} rounded-xl p-6 text-center`}>
        <Lightbulb className="w-10 h-10 mx-auto mb-2" />
        <p className="text-2xl font-bold">{getDecisionLabel(data.decision)}</p>
        <div className="mt-3 flex items-center justify-center gap-2">
          <div className="w-32 h-2 bg-white/20 rounded-full overflow-hidden">
            <div
              className="h-full bg-white/80 rounded-full"
              style={{ width: `${data.confidence}%` }}
            />
          </div>
          <span className="text-sm opacity-80">Confiance: {data.confidence}%</span>
        </div>
      </div>

      {/* Summary */}
      {data.summary && (
        <div className="bg-slate-900/50 rounded-lg p-4">
          <p className="text-slate-300">{data.summary}</p>
        </div>
      )}

      {/* Factors */}
      {data.factors && (
        <div className="bg-slate-900/50 rounded-lg p-4">
          <h4 className="font-medium text-slate-300 mb-4">Facteurs de Scoring</h4>
          <div className="space-y-4">
            {data.factors.map((factor, i) => (
              <div key={i}>
                <div className="flex justify-between mb-1">
                  <span className="text-slate-400">{factor.name}</span>
                  <span className={`font-semibold ${
                    factor.score >= 60 ? 'text-emerald-400' :
                    factor.score >= 40 ? 'text-yellow-400' : 'text-red-400'
                  }`}>
                    {factor.score}/100
                  </span>
                </div>
                <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${
                      factor.score >= 60 ? 'bg-emerald-500' :
                      factor.score >= 40 ? 'bg-yellow-500' : 'bg-red-500'
                    }`}
                    style={{ width: `${factor.score}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function BacktestTab({ data, ticker }) {
  const [years, setYears] = useState(3)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(data)

  const runBacktest = async () => {
    setRunning(true)
    try {
      // Essayer d'abord la route simple
      let res = await fetch(`/api/backtest/simple/${encodeURIComponent(ticker)}?years=${years}`)

      if (!res.ok) {
        // Fallback sur la route complete
        res = await fetch('/api/backtest/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ticker: ticker,
            strategy: 'buy_and_hold',
            initial_capital: 10000,
            start_date: new Date(Date.now() - years * 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
          })
        })
      }

      if (res.ok) {
        const data = await res.json()
        setResult({
          period: `${years} ans`,
          cagr: data.metrics?.annualized_return || data.cagr,
          volatility: data.metrics?.volatility || data.volatility,
          sharpe_ratio: data.metrics?.sharpe_ratio || data.sharpe_ratio,
          max_drawdown: data.metrics?.max_drawdown || data.max_drawdown,
          total_return: data.metrics?.total_return || data.total_return
        })
      }
    } catch (e) {
      console.error('Backtest error:', e)
    } finally {
      setRunning(false)
    }
  }

  const metrics = result ? [
    { label: 'Periode', value: result.period || `${years} ans`, icon: Calendar },
    { label: 'CAGR', value: result.cagr != null ? `${result.cagr.toFixed(1)}%` : 'N/A', icon: TrendingUp },
    { label: 'Volatilite', value: result.volatility != null ? `${result.volatility.toFixed(1)}%` : 'N/A', icon: Activity },
    { label: 'Sharpe Ratio', value: result.sharpe_ratio != null ? result.sharpe_ratio.toFixed(2) : 'N/A', icon: Target },
    { label: 'Max Drawdown', value: result.max_drawdown != null ? `${result.max_drawdown.toFixed(1)}%` : 'N/A', icon: Shield },
    { label: 'Return Total', value: result.total_return != null ? `${result.total_return.toFixed(1)}%` : 'N/A', icon: Percent }
  ] : []

  return (
    <div className="space-y-6">
      {/* Period selector */}
      <div className="bg-slate-900/50 rounded-lg p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="text-slate-400">Periode:</span>
            <div className="flex gap-2">
              {[1, 3, 5, 10].map(y => (
                <button
                  key={y}
                  onClick={() => setYears(y)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    years === y
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                  }`}
                >
                  {y} an{y > 1 ? 's' : ''}
                </button>
              ))}
            </div>
          </div>
          <button
            onClick={runBacktest}
            disabled={running}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-4 py-2 rounded-lg font-medium flex items-center gap-2"
          >
            {running ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <History className="w-4 h-4" />
            )}
            Lancer
          </button>
        </div>
      </div>

      {/* Message si pas de données */}
      {result?.message && (
        <div className="bg-yellow-900/20 border border-yellow-800/50 rounded-lg p-4">
          <p className="text-yellow-400 text-sm">{result.message}</p>
        </div>
      )}

      {/* Results */}
      {result && !result.message ? (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {metrics.map((m, i) => {
            const Icon = m.icon
            return (
              <div key={i} className="bg-slate-900/50 rounded-lg p-4">
                <div className="flex items-center gap-2 text-slate-500 mb-1">
                  <Icon className="w-4 h-4" />
                  <span className="text-xs uppercase tracking-wide">{m.label}</span>
                </div>
                <p className="text-xl font-semibold">{m.value}</p>
              </div>
            )
          })}
        </div>
      ) : !result?.message && (
        <div className="bg-slate-900/50 rounded-lg p-8 text-center">
          <History className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400">Lancez un backtest pour voir les resultats</p>
        </div>
      )}
    </div>
  )
}
