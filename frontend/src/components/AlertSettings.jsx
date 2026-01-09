import { useState, useEffect } from 'react'
import {
  Settings, Bell, BellOff, Clock, RefreshCw, Activity, TrendingUp,
  TrendingDown, Sliders, History, Trash2, ChevronDown, ChevronUp,
  Zap, Shield, Target, BarChart3, Save, RotateCcw, Play, CheckCircle, AlertTriangle
} from 'lucide-react'

const API_BASE = '/api'

// Configuration des presets
const PRESET_CONFIG = {
  conservative: {
    icon: Shield,
    color: 'blue',
    label: 'Conservateur',
    description: 'Alertes prudentes, scan 5min',
  },
  moderate: {
    icon: Target,
    color: 'yellow',
    label: 'Modere',
    description: 'Equilibre, scan 1min',
  },
  aggressive: {
    icon: Zap,
    color: 'red',
    label: 'Agressif',
    description: 'Alertes frequentes, scan 30s',
  },
  disabled: {
    icon: BellOff,
    color: 'slate',
    label: 'Desactive',
    description: 'Aucun scan automatique',
  },
}

// Unites de temps pour l'intervalle
const TIME_UNITS = [
  { value: 1, label: 'secondes', min: 10, max: 60 },
  { value: 60, label: 'minutes', min: 1, max: 60 },
  { value: 3600, label: 'heures', min: 1, max: 24 },
]

export default function AlertSettings() {
  const [config, setConfig] = useState(null)
  const [presets, setPresets] = useState({})
  const [history, setHistory] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)

  // Test state
  const [testing, setTesting] = useState(false)
  const [testResults, setTestResults] = useState(null)

  // UI State
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [intervalValue, setIntervalValue] = useState(60)
  const [intervalUnit, setIntervalUnit] = useState(1) // 1=sec, 60=min, 3600=hour

  useEffect(() => {
    loadConfig()
    loadHistory()
  }, [])

  useEffect(() => {
    if (config) {
      // Convertir l'intervalle en valeur + unite
      const interval = config.scan_interval
      if (interval >= 3600 && interval % 3600 === 0) {
        setIntervalValue(interval / 3600)
        setIntervalUnit(3600)
      } else if (interval >= 60 && interval % 60 === 0) {
        setIntervalValue(interval / 60)
        setIntervalUnit(60)
      } else {
        setIntervalValue(interval)
        setIntervalUnit(1)
      }
    }
  }, [config])

  const loadConfig = async () => {
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/alerts/technical/config`)
      if (res.ok) {
        const data = await res.json()
        setConfig(data.config)
        setPresets(data.presets || {})
      }
    } catch (err) {
      setError('Erreur chargement configuration')
    } finally {
      setLoading(false)
    }
  }

  const loadHistory = async () => {
    try {
      const res = await fetch(`${API_BASE}/alerts/technical/history?limit=50`)
      if (res.ok) {
        const data = await res.json()
        setHistory(data.history || [])
        setStats(data.stats || null)
      }
    } catch (err) {
      console.error('Error loading history:', err)
    }
  }

  const saveConfig = async (updates) => {
    try {
      setSaving(true)
      setError(null)

      const res = await fetch(`${API_BASE}/alerts/technical/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      })

      if (!res.ok) throw new Error('Erreur sauvegarde')

      const data = await res.json()
      setConfig(data.config)
      showSuccessMessage('Configuration sauvegardee')
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const applyPreset = async (presetName) => {
    try {
      setSaving(true)
      const res = await fetch(`${API_BASE}/alerts/technical/preset/${presetName}`, {
        method: 'POST',
      })

      if (!res.ok) throw new Error('Erreur application preset')

      const data = await res.json()
      setConfig(data.config)
      showSuccessMessage(`Preset "${PRESET_CONFIG[presetName]?.label}" applique`)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const toggleEnabled = async () => {
    try {
      const res = await fetch(`${API_BASE}/alerts/technical/toggle`, {
        method: 'POST',
      })

      if (res.ok) {
        const data = await res.json()
        setConfig(prev => ({ ...prev, enabled: data.enabled }))
        showSuccessMessage(data.message)
      }
    } catch (err) {
      setError('Erreur toggle')
    }
  }

  const clearHistory = async () => {
    if (!confirm('Effacer tout l\'historique des signaux ?')) return

    try {
      const res = await fetch(`${API_BASE}/alerts/technical/history`, {
        method: 'DELETE',
      })

      if (res.ok) {
        setHistory([])
        setStats(null)
        showSuccessMessage('Historique efface')
      }
    } catch (err) {
      setError('Erreur suppression')
    }
  }

  const runTest = async () => {
    try {
      setTesting(true)
      setTestResults(null)
      setError(null)

      const res = await fetch(`${API_BASE}/alerts/test-scan`, {
        method: 'POST',
      })

      if (!res.ok) throw new Error('Erreur lors du test')

      const data = await res.json()
      setTestResults(data)

      if (data.signals_detected > 0) {
        showSuccessMessage(`${data.signals_detected} signal(s) detecte(s), ${data.notifications_sent} notification(s) envoyee(s)`)
      } else {
        showSuccessMessage('Aucun signal detecte sur le portfolio')
      }

      // Refresh history after test
      loadHistory()
    } catch (err) {
      setError(err.message)
    } finally {
      setTesting(false)
    }
  }

  const handleIntervalChange = () => {
    const newInterval = intervalValue * intervalUnit
    if (newInterval >= 10 && newInterval <= 86400) {
      saveConfig({ scan_interval: newInterval })
    }
  }

  const showSuccessMessage = (msg) => {
    setSuccess(msg)
    setTimeout(() => setSuccess(null), 3000)
  }

  const formatInterval = (seconds) => {
    if (seconds >= 3600) {
      const hours = seconds / 3600
      return `${hours}h`
    } else if (seconds >= 60) {
      const mins = seconds / 60
      return `${mins}min`
    }
    return `${seconds}s`
  }

  const formatTimestamp = (iso) => {
    const date = new Date(iso)
    return date.toLocaleString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="w-8 h-8 animate-spin text-yellow-500" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Messages */}
      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 text-red-400">
          {error}
        </div>
      )}
      {success && (
        <div className="bg-emerald-900/30 border border-emerald-700 rounded-lg p-4 text-emerald-400">
          {success}
        </div>
      )}

      {/* Header avec Toggle principal */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className={`p-3 rounded-xl ${config?.enabled ? 'bg-emerald-600/20' : 'bg-slate-600/20'}`}>
              {config?.enabled ? (
                <Bell className="w-6 h-6 text-emerald-400" />
              ) : (
                <BellOff className="w-6 h-6 text-slate-400" />
              )}
            </div>
            <div>
              <h3 className="text-lg font-semibold">Alertes Techniques Automatiques</h3>
              <p className="text-sm text-slate-400">
                Scan automatique du portfolio pour RSI, MACD, Bollinger
              </p>
            </div>
          </div>

          <button
            onClick={toggleEnabled}
            className={`relative w-14 h-8 rounded-full transition-colors ${
              config?.enabled ? 'bg-emerald-600' : 'bg-slate-600'
            }`}
          >
            <span
              className={`absolute top-1 w-6 h-6 bg-white rounded-full transition-transform ${
                config?.enabled ? 'left-7' : 'left-1'
              }`}
            />
          </button>
        </div>

        {/* Intervalle de scan */}
        {config?.enabled && (
          <div className="mt-6 pt-6 border-t border-slate-700">
            <label className="block text-sm text-slate-400 mb-3">
              Frequence de scan du portfolio
            </label>
            <div className="flex items-center gap-3">
              <div className="flex items-center bg-slate-700/50 rounded-lg overflow-hidden">
                <input
                  type="number"
                  value={intervalValue}
                  onChange={(e) => setIntervalValue(Math.max(1, parseInt(e.target.value) || 1))}
                  className="w-20 bg-transparent px-3 py-2 text-center text-white focus:outline-none"
                  min="1"
                />
                <select
                  value={intervalUnit}
                  onChange={(e) => setIntervalUnit(parseInt(e.target.value))}
                  className="bg-slate-600 px-3 py-2 text-white border-l border-slate-500 focus:outline-none"
                >
                  {TIME_UNITS.map((unit) => (
                    <option key={unit.value} value={unit.value}>
                      {unit.label}
                    </option>
                  ))}
                </select>
              </div>
              <button
                onClick={handleIntervalChange}
                disabled={saving}
                className="bg-yellow-600 hover:bg-yellow-500 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2"
              >
                {saving ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                Appliquer
              </button>
              <span className="text-slate-500 text-sm">
                Actuel: {formatInterval(config?.scan_interval)}
              </span>
            </div>
          </div>
        )}

        {/* Bouton de test */}
        <div className="mt-6 pt-6 border-t border-slate-700">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="font-medium">Tester maintenant</h4>
              <p className="text-sm text-slate-400">
                Execute un scan immediat du portfolio et envoie les notifications
              </p>
            </div>
            <button
              onClick={runTest}
              disabled={testing}
              className="bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2"
            >
              {testing ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              {testing ? 'Scan en cours...' : 'Lancer le test'}
            </button>
          </div>

          {/* Resultats du test */}
          {testResults && (
            <div className="mt-4 p-4 bg-slate-900/50 rounded-lg">
              <div className="flex items-center gap-2 mb-3">
                {testResults.signals_detected > 0 ? (
                  <AlertTriangle className="w-5 h-5 text-yellow-400" />
                ) : (
                  <CheckCircle className="w-5 h-5 text-emerald-400" />
                )}
                <span className="font-medium">
                  {testResults.signals_detected} signal(s) detecte(s)
                </span>
                {testResults.notifications_sent > 0 && (
                  <span className="text-sm text-slate-400">
                    ({testResults.notifications_sent} notification(s) Telegram)
                  </span>
                )}
              </div>

              {testResults.signals?.length > 0 && (
                <div className="space-y-2">
                  {testResults.signals.map((signal, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-2 bg-slate-800/50 rounded text-sm"
                    >
                      <div className="flex items-center gap-3">
                        <span className="font-mono font-medium">{signal.ticker}</span>
                        <span className={`px-2 py-0.5 rounded text-xs ${
                          signal.signal_type.includes('overbought') || signal.signal_type.includes('bearish')
                            ? 'bg-red-600/20 text-red-400'
                            : 'bg-emerald-600/20 text-emerald-400'
                        }`}>
                          {signal.signal_type.replace(/_/g, ' ')}
                        </span>
                        <span className={`text-xs px-1.5 py-0.5 rounded ${
                          signal.severity === 'high' ? 'bg-red-600/30 text-red-300' :
                          signal.severity === 'medium' ? 'bg-yellow-600/30 text-yellow-300' :
                          'bg-slate-600/30 text-slate-300'
                        }`}>
                          {signal.severity}
                        </span>
                      </div>
                      <div className="text-slate-400 text-xs">
                        {signal.message}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {testResults.signals?.length === 0 && (
                <p className="text-slate-400 text-sm">
                  Aucun signal technique detecte. Tous les indicateurs sont dans les limites normales.
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Presets */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
        <h4 className="font-medium mb-4 flex items-center gap-2">
          <Sliders className="w-4 h-4 text-slate-400" />
          Presets de Configuration
        </h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Object.entries(PRESET_CONFIG).map(([key, preset]) => {
            const Icon = preset.icon
            const isActive = !config?.enabled && key === 'disabled'

            return (
              <button
                key={key}
                onClick={() => applyPreset(key)}
                disabled={saving}
                className={`p-4 rounded-xl border-2 text-left transition-all ${
                  isActive
                    ? `border-${preset.color}-600 bg-${preset.color}-600/20`
                    : 'border-slate-700 hover:border-slate-600 hover:bg-slate-700/30'
                }`}
              >
                <Icon className={`w-5 h-5 mb-2 text-${preset.color}-400`} />
                <p className="font-medium text-sm">{preset.label}</p>
                <p className="text-xs text-slate-400 mt-1">{preset.description}</p>
              </button>
            )
          })}
        </div>
      </div>

      {/* Configuration avancee */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="w-full p-4 flex items-center justify-between hover:bg-slate-700/30"
        >
          <span className="font-medium flex items-center gap-2">
            <Settings className="w-4 h-4 text-slate-400" />
            Configuration Avancee
          </span>
          {showAdvanced ? (
            <ChevronUp className="w-5 h-5 text-slate-400" />
          ) : (
            <ChevronDown className="w-5 h-5 text-slate-400" />
          )}
        </button>

        {showAdvanced && config && (
          <div className="p-6 pt-2 border-t border-slate-700 space-y-6">
            {/* Indicateurs */}
            <div>
              <h5 className="text-sm font-medium text-slate-300 mb-3">Indicateurs actifs</h5>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* RSI */}
                <div className="bg-slate-900/50 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-medium">RSI</span>
                    <button
                      onClick={() => saveConfig({ rsi_enabled: !config.rsi_enabled })}
                      className={`w-10 h-6 rounded-full transition-colors ${
                        config.rsi_enabled ? 'bg-emerald-600' : 'bg-slate-600'
                      }`}
                    >
                      <span className={`block w-4 h-4 bg-white rounded-full transition-transform mx-1 ${
                        config.rsi_enabled ? 'translate-x-4' : ''
                      }`} />
                    </button>
                  </div>
                  {config.rsi_enabled && (
                    <div className="space-y-2 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Surachat</span>
                        <input
                          type="number"
                          value={config.rsi_overbought}
                          onChange={(e) => saveConfig({ rsi_overbought: parseInt(e.target.value) })}
                          className="w-16 bg-slate-700 rounded px-2 py-1 text-center"
                          min="50"
                          max="95"
                        />
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Survente</span>
                        <input
                          type="number"
                          value={config.rsi_oversold}
                          onChange={(e) => saveConfig({ rsi_oversold: parseInt(e.target.value) })}
                          className="w-16 bg-slate-700 rounded px-2 py-1 text-center"
                          min="5"
                          max="50"
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* MACD */}
                <div className="bg-slate-900/50 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-medium">MACD</span>
                    <button
                      onClick={() => saveConfig({ macd_enabled: !config.macd_enabled })}
                      className={`w-10 h-6 rounded-full transition-colors ${
                        config.macd_enabled ? 'bg-emerald-600' : 'bg-slate-600'
                      }`}
                    >
                      <span className={`block w-4 h-4 bg-white rounded-full transition-transform mx-1 ${
                        config.macd_enabled ? 'translate-x-4' : ''
                      }`} />
                    </button>
                  </div>
                  <p className="text-xs text-slate-500">
                    Crossover haussier/baissier
                  </p>
                </div>

                {/* Bollinger */}
                <div className="bg-slate-900/50 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-medium">Bollinger</span>
                    <button
                      onClick={() => saveConfig({ bollinger_enabled: !config.bollinger_enabled })}
                      className={`w-10 h-6 rounded-full transition-colors ${
                        config.bollinger_enabled ? 'bg-emerald-600' : 'bg-slate-600'
                      }`}
                    >
                      <span className={`block w-4 h-4 bg-white rounded-full transition-transform mx-1 ${
                        config.bollinger_enabled ? 'translate-x-4' : ''
                      }`} />
                    </button>
                  </div>
                  <p className="text-xs text-slate-500">
                    Breakout bandes
                  </p>
                </div>
              </div>
            </div>

            {/* Options notifications */}
            <div>
              <h5 className="text-sm font-medium text-slate-300 mb-3">Notifications</h5>
              <div className="space-y-3">
                <label className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg cursor-pointer">
                  <span className="text-sm">Envoyer via Telegram</span>
                  <button
                    onClick={() => saveConfig({ notify_telegram: !config.notify_telegram })}
                    className={`w-10 h-6 rounded-full transition-colors ${
                      config.notify_telegram ? 'bg-emerald-600' : 'bg-slate-600'
                    }`}
                  >
                    <span className={`block w-4 h-4 bg-white rounded-full transition-transform mx-1 ${
                      config.notify_telegram ? 'translate-x-4' : ''
                    }`} />
                  </button>
                </label>

                <label className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg cursor-pointer">
                  <span className="text-sm">Uniquement severite haute</span>
                  <button
                    onClick={() => saveConfig({ notify_only_high_severity: !config.notify_only_high_severity })}
                    className={`w-10 h-6 rounded-full transition-colors ${
                      config.notify_only_high_severity ? 'bg-emerald-600' : 'bg-slate-600'
                    }`}
                  >
                    <span className={`block w-4 h-4 bg-white rounded-full transition-transform mx-1 ${
                      config.notify_only_high_severity ? 'translate-x-4' : ''
                    }`} />
                  </button>
                </label>

                <div className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg">
                  <span className="text-sm">Cooldown entre alertes</span>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      value={config.cooldown_minutes}
                      onChange={(e) => saveConfig({ cooldown_minutes: parseInt(e.target.value) })}
                      className="w-16 bg-slate-700 rounded px-2 py-1 text-center text-sm"
                      min="5"
                      max="1440"
                    />
                    <span className="text-sm text-slate-400">min</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Heures de trading */}
            <div>
              <h5 className="text-sm font-medium text-slate-300 mb-3">Heures de trading</h5>
              <label className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg cursor-pointer mb-3">
                <span className="text-sm">Scanner uniquement pendant les heures de marche</span>
                <button
                  onClick={() => saveConfig({ trading_hours_only: !config.trading_hours_only })}
                  className={`w-10 h-6 rounded-full transition-colors ${
                    config.trading_hours_only ? 'bg-emerald-600' : 'bg-slate-600'
                  }`}
                >
                  <span className={`block w-4 h-4 bg-white rounded-full transition-transform mx-1 ${
                    config.trading_hours_only ? 'translate-x-4' : ''
                  }`} />
                </button>
              </label>

              {config.trading_hours_only && (
                <div className="flex items-center gap-4 p-3 bg-slate-900/50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-400">De</span>
                    <input
                      type="number"
                      value={config.trading_start_hour}
                      onChange={(e) => saveConfig({ trading_start_hour: parseInt(e.target.value) })}
                      className="w-14 bg-slate-700 rounded px-2 py-1 text-center text-sm"
                      min="0"
                      max="23"
                    />
                    <span className="text-sm text-slate-400">h</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-400">a</span>
                    <input
                      type="number"
                      value={config.trading_end_hour}
                      onChange={(e) => saveConfig({ trading_end_hour: parseInt(e.target.value) })}
                      className="w-14 bg-slate-700 rounded px-2 py-1 text-center text-sm"
                      min="0"
                      max="23"
                    />
                    <span className="text-sm text-slate-400">h</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Historique des signaux */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
        <button
          onClick={() => { setShowHistory(!showHistory); if (!showHistory) loadHistory(); }}
          className="w-full p-4 flex items-center justify-between hover:bg-slate-700/30"
        >
          <span className="font-medium flex items-center gap-2">
            <History className="w-4 h-4 text-slate-400" />
            Historique des Signaux
            {stats && (
              <span className="text-sm text-slate-500">
                ({stats.signals_24h} dernières 24h)
              </span>
            )}
          </span>
          {showHistory ? (
            <ChevronUp className="w-5 h-5 text-slate-400" />
          ) : (
            <ChevronDown className="w-5 h-5 text-slate-400" />
          )}
        </button>

        {showHistory && (
          <div className="border-t border-slate-700">
            {/* Stats */}
            {stats && (
              <div className="p-4 bg-slate-900/30 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="text-slate-400">Total</span>
                  <p className="font-semibold text-lg">{stats.total_signals}</p>
                </div>
                <div>
                  <span className="text-slate-400">24h</span>
                  <p className="font-semibold text-lg text-yellow-400">{stats.signals_24h}</p>
                </div>
                <div>
                  <span className="text-slate-400">7 jours</span>
                  <p className="font-semibold text-lg">{stats.signals_7d}</p>
                </div>
                <div>
                  <span className="text-slate-400">Top ticker</span>
                  <p className="font-semibold">{stats.top_tickers?.[0]?.[0] || '-'}</p>
                </div>
              </div>
            )}

            {/* Liste */}
            <div className="max-h-80 overflow-y-auto">
              {history.length === 0 ? (
                <div className="p-8 text-center text-slate-500">
                  Aucun signal enregistre
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-slate-900/50 sticky top-0">
                    <tr>
                      <th className="text-left p-3 font-medium text-slate-400">Date</th>
                      <th className="text-left p-3 font-medium text-slate-400">Ticker</th>
                      <th className="text-left p-3 font-medium text-slate-400">Signal</th>
                      <th className="text-right p-3 font-medium text-slate-400">Valeur</th>
                      <th className="text-right p-3 font-medium text-slate-400">Prix</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((signal, idx) => (
                      <tr key={idx} className="border-t border-slate-700/50 hover:bg-slate-700/20">
                        <td className="p-3 text-slate-400">{formatTimestamp(signal.timestamp)}</td>
                        <td className="p-3 font-medium">{signal.ticker}</td>
                        <td className="p-3">
                          <span className={`px-2 py-0.5 rounded text-xs ${
                            signal.signal_type.includes('overbought') || signal.signal_type.includes('bearish')
                              ? 'bg-red-600/20 text-red-400'
                              : 'bg-emerald-600/20 text-emerald-400'
                          }`}>
                            {signal.signal_type.replace('_', ' ')}
                          </span>
                        </td>
                        <td className="p-3 text-right font-mono">{signal.indicator_value?.toFixed(2)}</td>
                        <td className="p-3 text-right font-mono">{signal.price?.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* Actions */}
            {history.length > 0 && (
              <div className="p-4 border-t border-slate-700 flex justify-between items-center">
                <button
                  onClick={loadHistory}
                  className="text-sm text-slate-400 hover:text-white flex items-center gap-1"
                >
                  <RefreshCw className="w-4 h-4" />
                  Actualiser
                </button>
                <button
                  onClick={clearHistory}
                  className="text-sm text-red-400 hover:text-red-300 flex items-center gap-1"
                >
                  <Trash2 className="w-4 h-4" />
                  Effacer l'historique
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
