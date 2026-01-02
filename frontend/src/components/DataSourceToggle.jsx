import { useState, useEffect } from 'react'
import { Database, Wifi, WifiOff, RefreshCw, AlertCircle, CheckCircle, Settings } from 'lucide-react'
import { getDataSources, getSourcesHealth, switchDataSource } from '../api'

/**
 * Composant Toggle pour switcher entre les sources de données (Yahoo/Saxo)
 *
 * Features:
 * - Affiche la source actuelle
 * - Permet de switcher entre les sources disponibles
 * - Affiche le statut de santé des sources
 * - Indicateur visuel du mode (polling vs temps réel)
 */
export default function DataSourceToggle({ onSourceChange, compact = false }) {
  const [sources, setSources] = useState([])
  const [currentSource, setCurrentSource] = useState('yahoo')
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(false)
  const [switching, setSwitching] = useState(false)
  const [error, setError] = useState(null)
  const [showDetails, setShowDetails] = useState(false)

  useEffect(() => {
    loadSources()
    loadHealth()

    // Refresh health toutes les 30 secondes
    const interval = setInterval(loadHealth, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadSources = async () => {
    try {
      setLoading(true)
      const data = await getDataSources()
      setSources(data.sources || [])
      setCurrentSource(data.default_source)
    } catch (err) {
      console.error('Failed to load sources:', err)
      setError('Impossible de charger les sources')
    } finally {
      setLoading(false)
    }
  }

  const loadHealth = async () => {
    try {
      const data = await getSourcesHealth()
      setHealth(data)
    } catch (err) {
      console.error('Failed to load health:', err)
    }
  }

  const handleSwitch = async (sourceName) => {
    if (sourceName === currentSource || switching) return

    try {
      setSwitching(true)
      setError(null)
      const result = await switchDataSource(sourceName)
      setCurrentSource(result.new_source)
      if (onSourceChange) {
        onSourceChange(result.new_source)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setSwitching(false)
    }
  }

  const getSourceIcon = (source) => {
    if (source.name === 'yahoo') {
      return <Database className="w-4 h-4" />
    }
    return source.is_realtime ? <Wifi className="w-4 h-4" /> : <WifiOff className="w-4 h-4" />
  }

  const getHealthStatus = (sourceName) => {
    if (!health) return null
    const sourceHealth = health.sources?.find(s => s.name === sourceName)
    return sourceHealth?.status || 'unknown'
  }

  const getHealthColor = (status) => {
    switch (status) {
      case 'healthy': return 'text-emerald-400'
      case 'degraded': return 'text-yellow-400'
      case 'unavailable': return 'text-red-400'
      default: return 'text-slate-400'
    }
  }

  const getHealthIcon = (status) => {
    switch (status) {
      case 'healthy': return <CheckCircle className="w-3 h-3 text-emerald-400" />
      case 'degraded': return <AlertCircle className="w-3 h-3 text-yellow-400" />
      case 'unavailable': return <WifiOff className="w-3 h-3 text-red-400" />
      default: return null
    }
  }

  // Mode compact pour l'intégration dans la barre
  if (compact) {
    const currentSourceData = sources.find(s => s.name === currentSource)
    const healthStatus = getHealthStatus(currentSource)

    return (
      <div className="relative">
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="flex items-center gap-2 bg-slate-700/50 hover:bg-slate-600/50 border border-slate-600 px-3 py-2 rounded-lg text-sm"
        >
          {loading ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <>
              {getSourceIcon(currentSourceData || {})}
              <span className="capitalize">{currentSource}</span>
              {getHealthIcon(healthStatus)}
            </>
          )}
        </button>

        {/* Dropdown */}
        {showDetails && (
          <div className="absolute right-0 mt-2 w-64 bg-slate-800 border border-slate-700 rounded-xl shadow-xl z-50">
            <div className="p-3 border-b border-slate-700">
              <h4 className="font-medium text-sm">Source de Donnees</h4>
              <p className="text-xs text-slate-400 mt-1">
                Selectionnez la source de prix en temps reel
              </p>
            </div>

            <div className="p-2">
              {sources.map(source => {
                const status = getHealthStatus(source.name)
                const isActive = source.name === currentSource

                return (
                  <button
                    key={source.name}
                    onClick={() => {
                      handleSwitch(source.name)
                      setShowDetails(false)
                    }}
                    disabled={!source.is_available || switching}
                    className={`w-full flex items-center justify-between p-3 rounded-lg text-left transition-colors ${
                      isActive
                        ? 'bg-blue-600/20 border border-blue-500/30'
                        : source.is_available
                        ? 'hover:bg-slate-700/50'
                        : 'opacity-50 cursor-not-allowed'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-lg ${isActive ? 'bg-blue-600' : 'bg-slate-700'}`}>
                        {getSourceIcon(source)}
                      </div>
                      <div>
                        <div className="font-medium capitalize flex items-center gap-2">
                          {source.name}
                          {source.is_realtime && (
                            <span className="text-xs bg-emerald-600/20 text-emerald-400 px-1.5 py-0.5 rounded">
                              Live
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-slate-400">
                          {source.description?.slice(0, 40)}...
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {getHealthIcon(status)}
                      {switching && source.name !== currentSource && (
                        <RefreshCw className="w-4 h-4 animate-spin" />
                      )}
                    </div>
                  </button>
                )
              })}
            </div>

            {error && (
              <div className="p-3 border-t border-slate-700">
                <p className="text-xs text-red-400">{error}</p>
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

  // Mode complet
  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Settings className="w-5 h-5 text-slate-400" />
          <h3 className="font-medium">Sources de Donnees</h3>
        </div>
        <button
          onClick={loadSources}
          disabled={loading}
          className="p-2 hover:bg-slate-700/50 rounded-lg"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-3 mb-4">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      <div className="space-y-2">
        {sources.map(source => {
          const status = getHealthStatus(source.name)
          const isActive = source.name === currentSource

          return (
            <div
              key={source.name}
              className={`flex items-center justify-between p-4 rounded-lg border transition-colors ${
                isActive
                  ? 'bg-blue-600/10 border-blue-500/30'
                  : 'bg-slate-900/30 border-slate-700/50'
              }`}
            >
              <div className="flex items-center gap-4">
                <div className={`p-3 rounded-lg ${isActive ? 'bg-blue-600' : 'bg-slate-700'}`}>
                  {getSourceIcon(source)}
                </div>
                <div>
                  <div className="font-medium flex items-center gap-2">
                    <span className="capitalize">{source.name}</span>
                    {source.is_realtime && (
                      <span className="text-xs bg-emerald-600/20 text-emerald-400 px-2 py-0.5 rounded-full">
                        Temps reel
                      </span>
                    )}
                    {isActive && (
                      <span className="text-xs bg-blue-600/20 text-blue-400 px-2 py-0.5 rounded-full">
                        Actif
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-slate-400 mt-1">
                    {source.description}
                  </p>
                  <div className="flex items-center gap-2 mt-2">
                    <span className={`text-xs ${getHealthColor(status)}`}>
                      {status === 'healthy' && 'Fonctionnel'}
                      {status === 'degraded' && 'Degrade'}
                      {status === 'unavailable' && 'Indisponible'}
                    </span>
                    {health?.sources?.find(s => s.name === source.name)?.success_rate && (
                      <span className="text-xs text-slate-500">
                        ({health.sources.find(s => s.name === source.name).success_rate}% succes)
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <button
                onClick={() => handleSwitch(source.name)}
                disabled={isActive || !source.is_available || switching}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white cursor-default'
                    : source.is_available
                    ? 'bg-slate-700 hover:bg-slate-600 text-white'
                    : 'bg-slate-800 text-slate-500 cursor-not-allowed'
                }`}
              >
                {switching && source.name !== currentSource ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : isActive ? (
                  'Actif'
                ) : source.is_available ? (
                  'Utiliser'
                ) : (
                  'Indisponible'
                )}
              </button>
            </div>
          )
        })}
      </div>

      {/* Stats */}
      {health && (
        <div className="mt-4 pt-4 border-t border-slate-700">
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-400">Statut global</span>
            <span className={`flex items-center gap-2 ${getHealthColor(health.overall_status)}`}>
              {getHealthIcon(health.overall_status)}
              {health.overall_status === 'healthy' ? 'Optimal' : 'Degrade'}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
