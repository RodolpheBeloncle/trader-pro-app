/**
 * TradingView Chart Component using lightweight-charts
 *
 * Features:
 * - Candlestick chart with OHLC data
 * - Volume histogram
 * - Crosshair with tooltips
 * - Auto-resize
 * - Dark theme matching app design
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import { createChart, CrosshairMode } from 'lightweight-charts'
import { Loader2, TrendingUp, AlertCircle } from 'lucide-react'

// Chart theme matching dark UI
const CHART_THEME = {
  layout: {
    background: { type: 'solid', color: 'transparent' },
    textColor: '#94a3b8',
  },
  grid: {
    vertLines: { color: 'rgba(51, 65, 85, 0.5)' },
    horzLines: { color: 'rgba(51, 65, 85, 0.5)' },
  },
  crosshair: {
    mode: CrosshairMode.Normal,
    vertLine: {
      color: '#64748b',
      width: 1,
      style: 2,
      labelBackgroundColor: '#1e293b',
    },
    horzLine: {
      color: '#64748b',
      width: 1,
      style: 2,
      labelBackgroundColor: '#1e293b',
    },
  },
  rightPriceScale: {
    borderColor: '#334155',
    scaleMargins: {
      top: 0.1,
      bottom: 0.2,
    },
  },
  timeScale: {
    borderColor: '#334155',
    timeVisible: true,
    secondsVisible: false,
  },
}

// Candlestick colors
const CANDLE_COLORS = {
  upColor: '#10b981',
  downColor: '#ef4444',
  borderUpColor: '#10b981',
  borderDownColor: '#ef4444',
  wickUpColor: '#10b981',
  wickDownColor: '#ef4444',
}

export default function TradingViewChart({
  ticker,
  height = 400,
  showVolume = true,
  className = '',
}) {
  const chartContainerRef = useRef(null)
  const chartRef = useRef(null)
  const candlestickSeriesRef = useRef(null)
  const volumeSeriesRef = useRef(null)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [data, setData] = useState(null)
  const abortControllerRef = useRef(null)

  // Fetch OHLC data from API
  const fetchOHLCData = useCallback(async (tickerToFetch) => {
    if (!tickerToFetch) return

    // Annuler la requête précédente si elle existe
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    const abortController = new AbortController()
    abortControllerRef.current = abortController

    setLoading(true)
    setError(null)
    setData(null) // Reset data pour éviter d'afficher les anciennes données

    try {
      // Use relative URL to leverage Vite proxy
      const response = await fetch(`/api/stocks/ohlc/${tickerToFetch}?days=365`, {
        signal: abortController.signal
      })

      if (!response.ok) {
        throw new Error(`Failed to fetch data: ${response.statusText}`)
      }

      const result = await response.json()
      setData(result)
    } catch (err) {
      // Ignorer les erreurs d'annulation
      if (err.name === 'AbortError') {
        return
      }
      console.error('Error fetching OHLC data:', err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  // Initialize chart (only once, not when ticker changes)
  useEffect(() => {
    if (!chartContainerRef.current) return

    // Clean up previous chart if exists
    if (chartRef.current) {
      chartRef.current.remove()
      chartRef.current = null
    }

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: height,
      ...CHART_THEME,
    })

    chartRef.current = chart

    // Create candlestick series
    const candlestickSeries = chart.addCandlestickSeries({
      ...CANDLE_COLORS,
    })
    candlestickSeriesRef.current = candlestickSeries

    // Create volume series if enabled
    if (showVolume) {
      const volumeSeries = chart.addHistogramSeries({
        priceFormat: {
          type: 'volume',
        },
        priceScaleId: '',
        scaleMargins: {
          top: 0.8,
          bottom: 0,
        },
      })
      volumeSeriesRef.current = volumeSeries
    }

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        })
      }
    }

    window.addEventListener('resize', handleResize)

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize)
      if (chartRef.current) {
        chartRef.current.remove()
        chartRef.current = null
      }
    }
  }, [height, showVolume]) // Retirer ticker des dépendances - le chart n'a pas besoin d'être recréé

  // Fetch data when ticker changes
  useEffect(() => {
    if (ticker) {
      fetchOHLCData(ticker)
    }
  }, [ticker, fetchOHLCData])

  // Update chart data when data changes
  useEffect(() => {
    if (!data || !candlestickSeriesRef.current || !chartRef.current) return

    try {
      // Set candlestick data
      if (data.candles && data.candles.length > 0) {
        candlestickSeriesRef.current.setData(data.candles)

        // Set volume data if enabled
        if (showVolume && volumeSeriesRef.current && data.volume && data.volume.length > 0) {
          volumeSeriesRef.current.setData(data.volume)
        }

        // Resize chart to container width (important after visibility change)
        if (chartContainerRef.current) {
          chartRef.current.applyOptions({
            width: chartContainerRef.current.clientWidth,
          })
        }

        // Fit content after data is set
        chartRef.current.timeScale().fitContent()
      }
    } catch (err) {
      console.error('Error updating chart:', err)
    }
  }, [data, showVolume])

  // Determine overlay state
  const showLoading = loading
  const showError = !loading && error
  const showNoData = !loading && !error && (!data || !data.candles || data.candles.length === 0)

  return (
    <div className={`relative ${className}`} style={{ height }}>
      {/* Chart container - always rendered to maintain ref */}
      <div
        ref={chartContainerRef}
        style={{ height, visibility: (showLoading || showError || showNoData) ? 'hidden' : 'visible' }}
      />

      {/* Loading overlay */}
      {showLoading && (
        <div
          className="absolute inset-0 flex items-center justify-center bg-slate-800/30 rounded-xl"
        >
          <div className="flex flex-col items-center gap-3 text-slate-400">
            <Loader2 className="w-8 h-8 animate-spin" />
            <span>Loading chart...</span>
          </div>
        </div>
      )}

      {/* Error overlay */}
      {showError && (
        <div
          className="absolute inset-0 flex items-center justify-center bg-slate-800/30 rounded-xl"
        >
          <div className="flex flex-col items-center gap-3 text-red-400">
            <AlertCircle className="w-8 h-8" />
            <span>Failed to load chart</span>
            <button
              onClick={() => fetchOHLCData(ticker)}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm"
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {/* No data overlay */}
      {showNoData && (
        <div
          className="absolute inset-0 flex items-center justify-center bg-slate-800/30 rounded-xl"
        >
          <div className="flex flex-col items-center gap-3 text-slate-400">
            <TrendingUp className="w-8 h-8 opacity-50" />
            <span>No chart data available</span>
          </div>
        </div>
      )}
    </div>
  )
}
