import { useState, useEffect } from 'react'
import {
  Zap, Clock, TrendingUp, Activity, RefreshCw, CheckCircle, Settings, Wifi, WifiOff
} from 'lucide-react'

// Note: Les routes streaming sont montees sans /api
const API_BASE = ''

// Configuration des modes avec leurs icones et couleurs
const MODE_CONFIG = {
  long_term: {
    icon: Clock,
    color: 'blue',
    bgClass: 'bg-blue-600/20',
    borderClass: 'border-blue-600',
    textClass: 'text-blue-400',
    activeClass: 'bg-blue-600',
  },
  swing: {
    icon: TrendingUp,
    color: 'yellow',
    bgClass: 'bg-yellow-600/20',
    borderClass: 'border-yellow-600',
    textClass: 'text-yellow-400',
    activeClass: 'bg-yellow-600',
  },
  scalping: {
    icon: Zap,
    color: 'red',
    bgClass: 'bg-red-600/20',
    borderClass: 'border-red-600',
    textClass: 'text-red-400',
    activeClass: 'bg-red-600',
  },
}

export default function TradingModeSelector({ compact = false, onModeChange }) {
  const [modes, setModes] = useState([])
  const [currentMode, setCurrentMode] = useState('long_term')
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [expanded, setExpanded] = useState(false)
  const [successMessage, setSuccessMessage] = useState(null)

  useEffect(() => {
    loadModes()
    loadStatus()
  }, [])

  const loadModes = async () => {
    try {
      const res = await fetch(`${API_BASE}/ws/streaming/modes`)
      if (res.ok) {
        const data = await res.json()
        setModes(data.modes || [])
        setCurrentMode(data.current_mode || 'long_term')
      }
    } catch (err) {
      console.error('Error loading modes:', err)
    }
  }

  const loadStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/ws/streaming/status`)
      if (res.ok) {
        const data = await res.json()
        setStatus(data)
      }
    } catch (err) {
      console.error('Error loading status:', err)
    }
  }

  const changeMode = async (modeId) => {
    if (modeId === currentMode || loading) return

    setLoading(true)
    setError(null)

    try {
      const res = await fetch(`${API_BASE}/ws/streaming/mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: modeId }),
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Erreur changement de mode')
      }

      const data = await res.json()
      setCurrentMode(modeId)
      await loadStatus()

      // Show success notification
      const modeName = data.display_name || modes.find(m => m.id === modeId)?.name || modeId
      const interval = data.use_websocket ? 'temps reel' : `${data.poll_interval}s`
      setSuccessMessage(`Mode "${modeName}" active (${interval})`)
      setTimeout(() => setSuccessMessage(null), 4000)

      if (onModeChange) {
        onModeChange(modeId, data)
      }

    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const currentModeConfig = MODE_CONFIG[currentMode] || MODE_CONFIG.long_term
  const CurrentIcon = currentModeConfig.icon
  const currentModeData = modes.find(m => m.id === currentMode)

  // Version compacte (pour la barre de header)
  if (compact) {
    return (
      <div className="relative">
        {/* Toast notification */}
        {successMessage && (
          <div className="fixed top-4 right-4 z-[100] animate-in slide-in-from-top-2 duration-300">
            <div className="flex items-center gap-3 px-4 py-3 bg-emerald-600 text-white rounded-xl shadow-lg shadow-emerald-600/20">
              <CheckCircle className="w-5 h-5 flex-shrink-0" />
              <span className="font-medium">{successMessage}</span>
            </div>
          </div>
        )}

        <button
          onClick={() => setExpanded(!expanded)}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${currentModeConfig.bgClass} ${currentModeConfig.borderClass} transition-all hover:opacity-80`}
        >
          <CurrentIcon className={`w-4 h-4 ${currentModeConfig.textClass}`} />
          <span className={`text-sm font-medium ${currentModeConfig.textClass}`}>
            {currentModeData?.name || 'Long Terme'}
          </span>
          {status?.use_websocket && (
            <Wifi className="w-3 h-3 text-emerald-400" title="Temps reel actif" />
          )}
        </button>

        {/* Dropdown */}
        {expanded && (
          <>
            <div
              className="fixed inset-0 z-40"
              onClick={() => setExpanded(false)}
            />
            <div className="absolute top-full right-0 mt-2 w-72 bg-slate-800 border border-slate-700 rounded-xl shadow-xl z-50 overflow-hidden">
              <div className="p-3 border-b border-slate-700">
                <h3 className="font-medium flex items-center gap-2">
                  <Settings className="w-4 h-4 text-slate-400" />
                  Mode de Trading
                </h3>
              </div>

              <div className="p-2">
                {modes.map((mode) => {
                  const config = MODE_CONFIG[mode.id] || MODE_CONFIG.long_term
                  const Icon = config.icon
                  const isActive = mode.id === currentMode

                  return (
                    <button
                      key={mode.id}
                      onClick={() => {
                        changeMode(mode.id)
                        setExpanded(false)
                      }}
                      disabled={loading}
                      className={`w-full flex items-start gap-3 p-3 rounded-lg text-left transition-all ${
                        isActive
                          ? `${config.bgClass} ${config.borderClass} border`
                          : 'hover:bg-slate-700/50'
                      }`}
                    >
                      <div className={`p-2 rounded-lg ${config.bgClass}`}>
                        <Icon className={`w-4 h-4 ${config.textClass}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className={`font-medium ${isActive ? config.textClass : 'text-white'}`}>
                            {mode.name}
                          </span>
                          {isActive && (
                            <CheckCircle className={`w-4 h-4 ${config.textClass}`} />
                          )}
                        </div>
                        <p className="text-xs text-slate-400 mt-0.5 line-clamp-2">
                          {mode.description}
                        </p>
                        <div className="flex items-center gap-2 mt-1.5">
                          {mode.use_websocket ? (
                            <span className="inline-flex items-center gap-1 text-xs text-emerald-400">
                              <Wifi className="w-3 h-3" />
                              Temps reel
                            </span>
                          ) : (
                            <span className="text-xs text-slate-500">
                              Refresh: {mode.poll_interval}s
                            </span>
                          )}
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>

              {/* Status */}
              {status && (
                <div className="p-3 border-t border-slate-700 bg-slate-900/50">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-400">Sources actives:</span>
                    <span className="text-white">
                      {status.sources?.join(', ') || 'yahoo'}
                    </span>
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    )
  }

  // Version complete (pour une page dediee)
  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${currentModeConfig.bgClass}`}>
            <Activity className={`w-5 h-5 ${currentModeConfig.textClass}`} />
          </div>
          <div>
            <h3 className="font-semibold">Mode de Trading</h3>
            <p className="text-sm text-slate-400">
              Configurez la frequence de rafraichissement des prix
            </p>
          </div>
        </div>
        <button
          onClick={() => { loadModes(); loadStatus(); }}
          disabled={loading}
          className="p-2 rounded-lg bg-slate-700/50 hover:bg-slate-600/50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-900/30 border border-red-700 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {modes.map((mode) => {
          const config = MODE_CONFIG[mode.id] || MODE_CONFIG.long_term
          const Icon = config.icon
          const isActive = mode.id === currentMode

          return (
            <button
              key={mode.id}
              onClick={() => changeMode(mode.id)}
              disabled={loading}
              className={`relative p-4 rounded-xl border-2 text-left transition-all ${
                isActive
                  ? `${config.bgClass} ${config.borderClass}`
                  : 'border-slate-700 hover:border-slate-600 hover:bg-slate-700/30'
              }`}
            >
              {isActive && (
                <div className="absolute top-3 right-3">
                  <CheckCircle className={`w-5 h-5 ${config.textClass}`} />
                </div>
              )}

              <div className={`inline-flex p-2.5 rounded-lg ${config.bgClass} mb-3`}>
                <Icon className={`w-6 h-6 ${config.textClass}`} />
              </div>

              <h4 className={`font-semibold mb-1 ${isActive ? config.textClass : 'text-white'}`}>
                {mode.name}
              </h4>

              <p className="text-sm text-slate-400 mb-3">
                {mode.description}
              </p>

              <div className="flex items-center gap-3 text-xs">
                {mode.use_websocket ? (
                  <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full bg-emerald-600/20 text-emerald-400">
                    <Wifi className="w-3 h-3" />
                    Temps reel
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full bg-slate-600/50 text-slate-400">
                    <Clock className="w-3 h-3" />
                    {mode.poll_interval}s
                  </span>
                )}

                <div className="flex items-center gap-1 flex-wrap">
                  {mode.sources?.map((src) => {
                    const isAvailable = status?.sources?.includes(src) || status?.realtime_sources?.includes(src)
                    return (
                      <span
                        key={src}
                        className={`text-xs px-1.5 py-0.5 rounded ${
                          isAvailable
                            ? 'bg-emerald-600/20 text-emerald-400'
                            : 'bg-slate-600/30 text-slate-500 line-through'
                        }`}
                        title={isAvailable ? 'Source disponible' : 'Source non configuree'}
                      >
                        {src}
                      </span>
                    )
                  })}
                </div>
              </div>
            </button>
          )
        })}
      </div>

      {/* Status detail */}
      {status && (
        <div className="mt-6 space-y-4">
          <div className="p-4 bg-slate-900/50 rounded-lg">
            <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
              <Activity className="w-4 h-4 text-slate-400" />
              Statut du Streaming
            </h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-slate-400">Statut:</span>
                <span className={`ml-2 ${status.status === 'running' ? 'text-emerald-400' : 'text-slate-500'}`}>
                  {status.status === 'running' ? 'Actif' : 'Inactif'}
                </span>
              </div>
              <div>
                <span className="text-slate-400">Intervalle:</span>
                <span className="ml-2 text-white">
                  {status.use_websocket ? 'Temps reel' : `${status.poll_interval}s`}
                </span>
              </div>
              <div>
                <span className="text-slate-400">Sources:</span>
                <span className="ml-2 text-white">
                  {status.sources?.join(', ') || '-'}
                </span>
              </div>
              <div>
                <span className="text-slate-400">Abonnes:</span>
                <span className="ml-2 text-white">{status.subscribed_count || 0}</span>
              </div>
            </div>
          </div>

          {/* Source Availability */}
          {status.source_availability && (
            <div className="p-4 bg-slate-900/50 rounded-lg">
              <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                <Wifi className="w-4 h-4 text-slate-400" />
                Disponibilite des Sources
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {Object.entries(status.source_availability).map(([source, info]) => (
                  <div
                    key={source}
                    className={`p-3 rounded-lg border ${
                      info.available
                        ? 'bg-emerald-600/10 border-emerald-600/30'
                        : 'bg-slate-700/30 border-slate-600/30'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium capitalize">{source}</span>
                      {info.available ? (
                        <CheckCircle className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <WifiOff className="w-4 h-4 text-slate-500" />
                      )}
                    </div>
                    <p className={`text-xs ${info.available ? 'text-emerald-400' : 'text-slate-500'}`}>
                      {info.reason}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
