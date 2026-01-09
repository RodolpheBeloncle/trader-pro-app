import { useState, useEffect, useCallback } from 'react'
import {
  Bell, RefreshCw, Trash2, Edit3, Search, Filter, X,
  TrendingUp, TrendingDown, Percent, AlertCircle, Check,
  CheckSquare, Square, MoreVertical, PlayCircle, XCircle
} from 'lucide-react'

const API_BASE = '/api'

// Alert type labels and colors
const ALERT_TYPE_CONFIG = {
  price_above: {
    label: 'Prix au-dessus',
    icon: TrendingUp,
    color: 'emerald',
    bgClass: 'bg-emerald-600/20',
    textClass: 'text-emerald-400',
    borderClass: 'border-emerald-600/30'
  },
  price_below: {
    label: 'Prix en-dessous',
    icon: TrendingDown,
    color: 'red',
    bgClass: 'bg-red-600/20',
    textClass: 'text-red-400',
    borderClass: 'border-red-600/30'
  },
  percent_change: {
    label: 'Variation %',
    icon: Percent,
    color: 'blue',
    bgClass: 'bg-blue-600/20',
    textClass: 'text-blue-400',
    borderClass: 'border-blue-600/30'
  }
}

export default function AlertsManager() {
  // State
  const [alerts, setAlerts] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)

  // Filters
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState('all') // all, price_above, price_below, percent_change
  const [filterStatus, setFilterStatus] = useState('all') // all, active, triggered, inactive

  // Selection for bulk operations
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [showBulkMenu, setShowBulkMenu] = useState(false)

  // Edit modal
  const [editModal, setEditModal] = useState({ show: false, alert: null })
  const [editForm, setEditForm] = useState({ target_value: '', notes: '', is_active: true })

  // Load data on mount
  useEffect(() => {
    loadAlerts()
    loadStats()
  }, [])

  // ==========================================================================
  // API CALLS
  // ==========================================================================

  const loadAlerts = async () => {
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/alerts`)
      if (!res.ok) throw new Error('Erreur chargement alertes')
      const data = await res.json()
      setAlerts(data)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const loadStats = async () => {
    try {
      const res = await fetch(`${API_BASE}/alerts/stats`)
      if (res.ok) {
        const data = await res.json()
        setStats(data)
      }
    } catch (err) {
      console.error('Error loading stats:', err)
    }
  }

  const deleteAlert = async (alertId) => {
    try {
      const res = await fetch(`${API_BASE}/alerts/${alertId}`, { method: 'DELETE' })
      if (!res.ok && res.status !== 204) throw new Error('Erreur suppression')

      setAlerts(prev => prev.filter(a => a.id !== alertId))
      setSelectedIds(prev => {
        const newSet = new Set(prev)
        newSet.delete(alertId)
        return newSet
      })
      loadStats()
      showSuccessMessage('Alerte supprimee')
    } catch (err) {
      setError(err.message)
    }
  }

  const deleteMultipleAlerts = async (ids) => {
    setLoading(true)
    let deleted = 0
    let errors = 0

    for (const id of ids) {
      try {
        const res = await fetch(`${API_BASE}/alerts/${id}`, { method: 'DELETE' })
        if (res.ok || res.status === 204) {
          deleted++
        } else {
          errors++
        }
      } catch {
        errors++
      }
    }

    setSelectedIds(new Set())
    await loadAlerts()
    await loadStats()
    setLoading(false)

    if (errors > 0) {
      showSuccessMessage(`${deleted} alerte(s) supprimee(s), ${errors} erreur(s)`)
    } else {
      showSuccessMessage(`${deleted} alerte(s) supprimee(s)`)
    }
  }

  const updateAlert = async (alertId, updates) => {
    try {
      const res = await fetch(`${API_BASE}/alerts/${alertId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      })

      if (!res.ok) throw new Error('Erreur modification')

      const updated = await res.json()
      setAlerts(prev => prev.map(a => a.id === alertId ? updated : a))
      loadStats()
      return true
    } catch (err) {
      setError(err.message)
      return false
    }
  }

  const testNotification = async (alertId) => {
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/alerts/${alertId}/test`, { method: 'POST' })
      if (!res.ok) throw new Error('Echec envoi notification')
      showSuccessMessage('Notification de test envoyee!')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const checkAlerts = async () => {
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/alerts/check`, { method: 'POST' })
      if (!res.ok) throw new Error('Erreur verification')
      const data = await res.json()
      showSuccessMessage(`${data.checked} alertes verifiees, ${data.triggered} declenchee(s)`)
      await loadAlerts()
      await loadStats()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // ==========================================================================
  // HELPERS
  // ==========================================================================

  const showSuccessMessage = (msg) => {
    setSuccess(msg)
    setTimeout(() => setSuccess(null), 3000)
  }

  // Find duplicates (same ticker + alert_type + target_value)
  const findDuplicates = useCallback(() => {
    const seen = new Map()
    const duplicateIds = []

    for (const alert of alerts) {
      const key = `${alert.ticker}-${alert.alert_type}-${alert.target_value}`
      if (seen.has(key)) {
        duplicateIds.push(alert.id)
      } else {
        seen.set(key, alert.id)
      }
    }

    return duplicateIds
  }, [alerts])

  const duplicateCount = findDuplicates().length

  // Filter alerts
  const filteredAlerts = alerts.filter(alert => {
    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      if (!alert.ticker.toLowerCase().includes(query) &&
          !(alert.notes || '').toLowerCase().includes(query)) {
        return false
      }
    }

    // Type filter
    if (filterType !== 'all' && alert.alert_type !== filterType) {
      return false
    }

    // Status filter
    if (filterStatus === 'active' && (!alert.is_active || alert.is_triggered)) return false
    if (filterStatus === 'triggered' && !alert.is_triggered) return false
    if (filterStatus === 'inactive' && alert.is_active) return false

    return true
  })

  // Selection helpers
  const allSelected = filteredAlerts.length > 0 && filteredAlerts.every(a => selectedIds.has(a.id))
  const someSelected = selectedIds.size > 0

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filteredAlerts.map(a => a.id)))
    }
  }

  const toggleSelect = (id) => {
    setSelectedIds(prev => {
      const newSet = new Set(prev)
      if (newSet.has(id)) {
        newSet.delete(id)
      } else {
        newSet.add(id)
      }
      return newSet
    })
  }

  // Open edit modal
  const openEditModal = (alert) => {
    setEditForm({
      target_value: alert.target_value.toString(),
      notes: alert.notes || '',
      is_active: alert.is_active
    })
    setEditModal({ show: true, alert })
  }

  // Save edit
  const saveEdit = async () => {
    if (!editModal.alert) return

    const updates = {}
    if (editForm.target_value) {
      updates.target_value = parseFloat(editForm.target_value)
    }
    if (editForm.notes !== editModal.alert.notes) {
      updates.notes = editForm.notes
    }
    if (editForm.is_active !== editModal.alert.is_active) {
      updates.is_active = editForm.is_active
    }

    const success = await updateAlert(editModal.alert.id, updates)
    if (success) {
      setEditModal({ show: false, alert: null })
      showSuccessMessage('Alerte modifiee')
    }
  }

  // ==========================================================================
  // RENDER
  // ==========================================================================

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-yellow-600 rounded-lg flex items-center justify-center">
            <Bell className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-semibold">Gestion des Alertes</h2>
            <p className="text-sm text-slate-400">
              {stats ? `${stats.total} alertes (${stats.active} actives)` : 'Chargement...'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={checkAlerts}
            disabled={loading}
            className="bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 px-3 py-2 rounded-lg text-sm flex items-center gap-2"
            title="Verifier les alertes maintenant"
          >
            <PlayCircle className="w-4 h-4" />
            Verifier
          </button>
          <button
            onClick={() => { loadAlerts(); loadStats(); }}
            disabled={loading}
            className="bg-slate-700/50 hover:bg-slate-600/50 p-2 rounded-lg"
            title="Rafraichir"
          >
            <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 flex items-center justify-between">
          <p className="text-red-400">{error}</p>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
      {success && (
        <div className="bg-emerald-900/30 border border-emerald-700 rounded-lg p-4">
          <p className="text-emerald-400">{success}</p>
        </div>
      )}

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
            <p className="text-sm text-slate-400">Total</p>
            <p className="text-2xl font-bold">{stats.total}</p>
          </div>
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
            <p className="text-sm text-slate-400">Actives</p>
            <p className="text-2xl font-bold text-emerald-400">{stats.active}</p>
          </div>
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
            <p className="text-sm text-slate-400">Declenchees</p>
            <p className="text-2xl font-bold text-yellow-400">{stats.triggered}</p>
          </div>
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
            <p className="text-sm text-slate-400">Inactives</p>
            <p className="text-2xl font-bold text-slate-500">{stats.inactive}</p>
          </div>
        </div>
      )}

      {/* Duplicate Warning */}
      {duplicateCount > 0 && (
        <div className="bg-yellow-900/30 border border-yellow-700 rounded-lg p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-yellow-400" />
            <span className="text-yellow-400">
              {duplicateCount} alerte(s) en double detectee(s)
            </span>
          </div>
          <button
            onClick={() => deleteMultipleAlerts(findDuplicates())}
            disabled={loading}
            className="bg-yellow-600 hover:bg-yellow-500 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2"
          >
            <Trash2 className="w-4 h-4" />
            Supprimer les doublons
          </button>
        </div>
      )}

      {/* Filters & Search */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
        <div className="flex flex-wrap items-center gap-4">
          {/* Search */}
          <div className="flex-1 min-w-[200px]">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Rechercher par ticker ou notes..."
                className="w-full bg-slate-700/50 border border-slate-600 rounded-lg pl-10 pr-4 py-2 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-yellow-500"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>

          {/* Type Filter */}
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-400" />
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-sm"
            >
              <option value="all">Tous types</option>
              <option value="price_above">Prix au-dessus</option>
              <option value="price_below">Prix en-dessous</option>
              <option value="percent_change">Variation %</option>
            </select>
          </div>

          {/* Status Filter */}
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-sm"
          >
            <option value="all">Tous statuts</option>
            <option value="active">Actives</option>
            <option value="triggered">Declenchees</option>
            <option value="inactive">Inactives</option>
          </select>
        </div>

        {/* Bulk Actions */}
        {someSelected && (
          <div className="mt-4 pt-4 border-t border-slate-700 flex items-center justify-between">
            <span className="text-sm text-slate-400">
              {selectedIds.size} alerte(s) selectionnee(s)
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setSelectedIds(new Set())}
                className="text-slate-400 hover:text-white text-sm"
              >
                Deselectionner
              </button>
              <button
                onClick={() => {
                  if (confirm(`Supprimer ${selectedIds.size} alerte(s) ?`)) {
                    deleteMultipleAlerts(Array.from(selectedIds))
                  }
                }}
                disabled={loading}
                className="bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2"
              >
                <Trash2 className="w-4 h-4" />
                Supprimer la selection
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Alerts Table */}
      {loading && alerts.length === 0 ? (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="w-8 h-8 animate-spin text-yellow-500" />
        </div>
      ) : filteredAlerts.length === 0 ? (
        <div className="bg-slate-800/30 border border-slate-700 rounded-xl p-8 text-center">
          <Bell className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400">
            {alerts.length === 0 ? 'Aucune alerte configuree' : 'Aucune alerte ne correspond aux filtres'}
          </p>
        </div>
      ) : (
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[800px]">
              <thead className="bg-slate-900/50">
                <tr>
                  <th className="text-left p-3 w-10">
                    <button onClick={toggleSelectAll} className="text-slate-400 hover:text-white">
                      {allSelected ? (
                        <CheckSquare className="w-5 h-5 text-yellow-400" />
                      ) : (
                        <Square className="w-5 h-5" />
                      )}
                    </button>
                  </th>
                  <th className="text-left p-3 text-sm font-medium text-slate-400">Ticker</th>
                  <th className="text-left p-3 text-sm font-medium text-slate-400">Type</th>
                  <th className="text-right p-3 text-sm font-medium text-slate-400">Cible</th>
                  <th className="text-right p-3 text-sm font-medium text-slate-400">Prix initial</th>
                  <th className="text-center p-3 text-sm font-medium text-slate-400">Statut</th>
                  <th className="text-left p-3 text-sm font-medium text-slate-400">Notes</th>
                  <th className="text-left p-3 text-sm font-medium text-slate-400">Creee le</th>
                  <th className="text-center p-3 text-sm font-medium text-slate-400">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredAlerts.map((alert) => {
                  const typeConfig = ALERT_TYPE_CONFIG[alert.alert_type] || ALERT_TYPE_CONFIG.price_above
                  const TypeIcon = typeConfig.icon
                  const isSelected = selectedIds.has(alert.id)

                  return (
                    <tr
                      key={alert.id}
                      className={`border-t border-slate-700/50 hover:bg-slate-700/20 ${
                        isSelected ? 'bg-yellow-900/10' : ''
                      }`}
                    >
                      <td className="p-3">
                        <button
                          onClick={() => toggleSelect(alert.id)}
                          className="text-slate-400 hover:text-white"
                        >
                          {isSelected ? (
                            <CheckSquare className="w-5 h-5 text-yellow-400" />
                          ) : (
                            <Square className="w-5 h-5" />
                          )}
                        </button>
                      </td>
                      <td className="p-3">
                        <span className="font-semibold text-white">{alert.ticker}</span>
                      </td>
                      <td className="p-3">
                        <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium ${typeConfig.bgClass} ${typeConfig.textClass}`}>
                          <TypeIcon className="w-3 h-3" />
                          {typeConfig.label}
                        </span>
                      </td>
                      <td className="text-right p-3 font-mono">
                        {alert.alert_type === 'percent_change' ? (
                          `${alert.target_value > 0 ? '+' : ''}${alert.target_value}%`
                        ) : (
                          alert.target_value.toFixed(2)
                        )}
                      </td>
                      <td className="text-right p-3 font-mono text-slate-400">
                        {alert.current_value?.toFixed(2) || '-'}
                      </td>
                      <td className="text-center p-3">
                        {alert.is_triggered ? (
                          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-yellow-600/20 text-yellow-400">
                            <Check className="w-3 h-3" />
                            Declenchee
                          </span>
                        ) : alert.is_active ? (
                          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-emerald-600/20 text-emerald-400">
                            <Bell className="w-3 h-3" />
                            Active
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-slate-600/20 text-slate-400">
                            <XCircle className="w-3 h-3" />
                            Inactive
                          </span>
                        )}
                      </td>
                      <td className="p-3">
                        <span className="text-slate-400 text-sm truncate max-w-[150px] block">
                          {alert.notes || '-'}
                        </span>
                      </td>
                      <td className="p-3 text-sm text-slate-500">
                        {new Date(alert.created_at).toLocaleDateString('fr-FR')}
                      </td>
                      <td className="p-3">
                        <div className="flex items-center justify-center gap-1">
                          <button
                            onClick={() => openEditModal(alert)}
                            className="bg-slate-700/50 hover:bg-slate-600/50 text-slate-300 p-1.5 rounded"
                            title="Modifier"
                          >
                            <Edit3 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => testNotification(alert.id)}
                            className="bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 p-1.5 rounded"
                            title="Tester notification"
                          >
                            <Bell className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => {
                              if (confirm(`Supprimer l'alerte ${alert.ticker} ?`)) {
                                deleteAlert(alert.id)
                              }
                            }}
                            className="bg-red-600/20 hover:bg-red-600/40 text-red-400 p-1.5 rounded"
                            title="Supprimer"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div className="flex flex-wrap gap-3">
        {stats?.triggered > 0 && (
          <button
            onClick={() => {
              const triggeredIds = alerts.filter(a => a.is_triggered).map(a => a.id)
              if (confirm(`Supprimer ${triggeredIds.length} alerte(s) declenchee(s) ?`)) {
                deleteMultipleAlerts(triggeredIds)
              }
            }}
            disabled={loading}
            className="bg-yellow-600/20 hover:bg-yellow-600/40 text-yellow-400 px-4 py-2 rounded-lg text-sm flex items-center gap-2"
          >
            <Trash2 className="w-4 h-4" />
            Nettoyer les declenchees ({stats.triggered})
          </button>
        )}
        {stats?.inactive > 0 && (
          <button
            onClick={() => {
              const inactiveIds = alerts.filter(a => !a.is_active).map(a => a.id)
              if (confirm(`Supprimer ${inactiveIds.length} alerte(s) inactive(s) ?`)) {
                deleteMultipleAlerts(inactiveIds)
              }
            }}
            disabled={loading}
            className="bg-slate-600/20 hover:bg-slate-600/40 text-slate-400 px-4 py-2 rounded-lg text-sm flex items-center gap-2"
          >
            <Trash2 className="w-4 h-4" />
            Nettoyer les inactives ({stats.inactive})
          </button>
        )}
      </div>

      {/* Edit Modal */}
      {editModal.show && editModal.alert && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 max-w-md w-full">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-lg font-semibold flex items-center gap-2">
                  <Edit3 className="w-5 h-5 text-yellow-400" />
                  Modifier l'alerte
                </h3>
                <p className="text-slate-400 text-sm mt-1">
                  {editModal.alert.ticker} - {ALERT_TYPE_CONFIG[editModal.alert.alert_type]?.label}
                </p>
              </div>
              <button
                onClick={() => setEditModal({ show: false, alert: null })}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              {/* Target Value */}
              <div>
                <label className="block text-sm text-slate-400 mb-2">
                  Valeur cible {editModal.alert.alert_type === 'percent_change' ? '(%)' : '(prix)'}
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={editForm.target_value}
                  onChange={(e) => setEditForm({ ...editForm, target_value: e.target.value })}
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-yellow-500"
                />
              </div>

              {/* Notes */}
              <div>
                <label className="block text-sm text-slate-400 mb-2">Notes</label>
                <textarea
                  value={editForm.notes}
                  onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
                  placeholder="Notes personnelles..."
                  rows={3}
                  maxLength={500}
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-yellow-500 resize-none"
                />
              </div>

              {/* Active Toggle */}
              <div className="flex items-center justify-between">
                <label className="text-sm text-slate-400">Alerte active</label>
                <button
                  onClick={() => setEditForm({ ...editForm, is_active: !editForm.is_active })}
                  className={`relative w-12 h-6 rounded-full transition-colors ${
                    editForm.is_active ? 'bg-emerald-600' : 'bg-slate-600'
                  }`}
                >
                  <span
                    className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                      editForm.is_active ? 'left-7' : 'left-1'
                    }`}
                  />
                </button>
              </div>

              {/* Buttons */}
              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => setEditModal({ show: false, alert: null })}
                  className="flex-1 bg-slate-700 hover:bg-slate-600 text-slate-300 py-2.5 rounded-lg font-medium"
                >
                  Annuler
                </button>
                <button
                  onClick={saveEdit}
                  disabled={loading}
                  className="flex-1 bg-yellow-600 hover:bg-yellow-500 text-white py-2.5 rounded-lg font-medium flex items-center justify-center gap-2"
                >
                  {loading ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <Check className="w-4 h-4" />
                      Enregistrer
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
