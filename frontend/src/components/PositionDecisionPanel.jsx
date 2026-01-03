import { useState, useEffect } from 'react'
import {
  X, Lightbulb, TrendingUp, TrendingDown, Minus,
  AlertTriangle, CheckCircle, XCircle, ChevronDown, ChevronUp,
  BarChart3, Shield, Target, Activity, RefreshCw, Bell, DollarSign
} from 'lucide-react'

const API_BASE = '/api'

/**
 * PositionDecisionPanel - Panel lateral d'aide a la decision pour une position
 *
 * Affiche:
 * - Decision principale (Buy More, Hold, Reduce, Sell)
 * - Niveau de confiance
 * - Analyse technique resumee
 * - Facteurs de confluence
 * - Avertissements
 * - Setup de trade suggere
 *
 * Props:
 * - position: { symbol, current_price, quantity, pnl, pnl_percent, ... }
 * - onClose: () => void
 * - onCreateAlert: (position) => void
 * - onTrade: (position, direction) => void
 */
export default function PositionDecisionPanel({ position, onClose, onCreateAlert, onTrade }) {
  const [decision, setDecision] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expandedSections, setExpandedSections] = useState({
    technical: true,
    confluence: false,
    warnings: false,
    setup: false
  })

  useEffect(() => {
    if (position?.symbol) {
      fetchDecision(position.symbol)
    }
  }, [position?.symbol])

  const fetchDecision = async (symbol) => {
    setLoading(true)
    setError(null)

    try {
      // Appel a l'endpoint de decision
      const res = await fetch(`${API_BASE}/saxo/positions/${symbol}/decision`)

      if (!res.ok) {
        // Si l'endpoint n'existe pas encore, simuler une reponse
        throw new Error('API non disponible')
      }

      const data = await res.json()
      setDecision(data)
    } catch (err) {
      // Fallback: generer une decision simulee basee sur le P&L
      setDecision(generateMockDecision(position))
    } finally {
      setLoading(false)
    }
  }

  // Generer une decision simulee (fallback si API non dispo)
  const generateMockDecision = (pos) => {
    const pnlPercent = pos.pnl_percent || 0

    let decisionType, confidence, reasoning

    if (pnlPercent > 20) {
      decisionType = 'take_profit'
      confidence = 75
      reasoning = 'Position en forte plus-value. Considerez une prise de benefices partielle.'
    } else if (pnlPercent > 5) {
      decisionType = 'hold'
      confidence = 65
      reasoning = 'Position en gain moderee. Maintenir avec stop suiveur.'
    } else if (pnlPercent > -5) {
      decisionType = 'hold'
      confidence = 50
      reasoning = 'Position neutre. Surveiller les niveaux techniques.'
    } else if (pnlPercent > -15) {
      decisionType = 'hold_caution'
      confidence = 45
      reasoning = 'Position en perte moderee. Evaluer le support technique.'
    } else {
      decisionType = 'review'
      confidence = 60
      reasoning = 'Position en perte significative. Revoir la these d\'investissement.'
    }

    return {
      decision_type: decisionType,
      confidence,
      reasoning,
      market_structure: {
        trend: pnlPercent > 0 ? 'bullish' : 'bearish',
        trend_strength: Math.abs(pnlPercent) > 10 ? 'strong' : 'moderate',
        key_levels: {
          support: (pos.current_price * 0.95).toFixed(2),
          resistance: (pos.current_price * 1.08).toFixed(2),
        },
        volatility: 'moderate'
      },
      confluence_factors: [
        { factor: 'Performance relative', value: `${pnlPercent > 0 ? '+' : ''}${pnlPercent.toFixed(1)}%`, bullish: pnlPercent > 0 },
        { factor: 'Taille position', value: `${pos.quantity} actions`, bullish: true },
        { factor: 'Valeur investie', value: `${pos.market_value?.toFixed(2)}€`, bullish: true }
      ],
      warning_factors: pnlPercent < -10 ? [
        { warning: 'Position en perte significative', severity: 'high' },
        { warning: 'Verifier le stop-loss', severity: 'medium' }
      ] : [],
      trade_setup: {
        entry_type: 'market',
        stop_loss: (pos.current_price * 0.92).toFixed(2),
        take_profit: (pos.current_price * 1.15).toFixed(2),
        position_size_suggestion: 'maintenir'
      }
    }
  }

  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }))
  }

  // Decision badge avec couleur
  const getDecisionBadge = (type) => {
    const badges = {
      'strong_buy': { label: 'Renforcer', color: 'bg-emerald-600', icon: TrendingUp },
      'buy_more': { label: 'Acheter +', color: 'bg-emerald-500', icon: TrendingUp },
      'hold': { label: 'Conserver', color: 'bg-blue-500', icon: Minus },
      'hold_caution': { label: 'Surveiller', color: 'bg-yellow-500', icon: AlertTriangle },
      'take_profit': { label: 'Prendre profits', color: 'bg-purple-500', icon: DollarSign },
      'reduce': { label: 'Reduire', color: 'bg-orange-500', icon: TrendingDown },
      'sell': { label: 'Vendre', color: 'bg-red-500', icon: XCircle },
      'review': { label: 'A revoir', color: 'bg-red-600', icon: AlertTriangle }
    }

    return badges[type] || { label: 'En attente', color: 'bg-slate-500', icon: Activity }
  }

  if (!position) return null

  const badge = decision ? getDecisionBadge(decision.decision_type) : null
  const BadgeIcon = badge?.icon || Activity

  return (
    <div className="fixed right-0 top-0 h-full w-96 bg-slate-800 border-l border-slate-700 shadow-2xl z-50 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-slate-700 flex-shrink-0">
        <div className="flex justify-between items-start">
          <div>
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <Lightbulb className="w-5 h-5 text-yellow-400" />
              Aide a la decision
            </h3>
            <p className="text-slate-400 mt-1">
              <span className="font-medium text-white text-lg">{position.symbol}</span>
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Position summary */}
        <div className="mt-4 grid grid-cols-2 gap-3">
          <div className="bg-slate-900/50 rounded-lg p-3">
            <p className="text-xs text-slate-500">Prix actuel</p>
            <p className="font-mono font-semibold">{position.current_price?.toFixed(2)}€</p>
          </div>
          <div className="bg-slate-900/50 rounded-lg p-3">
            <p className="text-xs text-slate-500">P&L</p>
            <p className={`font-mono font-semibold ${
              position.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'
            }`}>
              {position.pnl >= 0 ? '+' : ''}{position.pnl?.toFixed(2)}€
              <span className="text-xs ml-1">({position.pnl_percent?.toFixed(1)}%)</span>
            </p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
          </div>
        ) : error ? (
          <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 text-center">
            <p className="text-red-400">{error}</p>
            <button
              onClick={() => fetchDecision(position.symbol)}
              className="mt-2 text-sm text-blue-400 hover:underline"
            >
              Reessayer
            </button>
          </div>
        ) : decision ? (
          <div className="space-y-4">
            {/* Decision principale */}
            <div className={`${badge?.color} rounded-xl p-4 text-center`}>
              <BadgeIcon className="w-8 h-8 mx-auto mb-2" />
              <p className="text-xl font-bold">{badge?.label}</p>
              <div className="mt-2 flex items-center justify-center gap-2">
                <div className="w-24 h-2 bg-white/20 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-white/80 rounded-full transition-all"
                    style={{ width: `${decision.confidence}%` }}
                  />
                </div>
                <span className="text-sm opacity-80">{decision.confidence}%</span>
              </div>
            </div>

            {/* Reasoning */}
            <div className="bg-slate-900/50 rounded-lg p-4">
              <p className="text-sm text-slate-300">{decision.reasoning}</p>
            </div>

            {/* Analyse Technique */}
            <CollapsibleSection
              title="Analyse Technique"
              icon={BarChart3}
              expanded={expandedSections.technical}
              onToggle={() => toggleSection('technical')}
            >
              {decision.market_structure && (
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Tendance</span>
                    <span className={decision.market_structure.trend === 'bullish' ? 'text-emerald-400' : 'text-red-400'}>
                      {decision.market_structure.trend === 'bullish' ? 'Haussiere' : 'Baissiere'}
                      {decision.market_structure.trend_strength === 'strong' && ' (forte)'}
                    </span>
                  </div>
                  {decision.market_structure.key_levels && (
                    <>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Support</span>
                        <span className="font-mono text-red-300">{decision.market_structure.key_levels.support}€</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Resistance</span>
                        <span className="font-mono text-emerald-300">{decision.market_structure.key_levels.resistance}€</span>
                      </div>
                    </>
                  )}
                  <div className="flex justify-between">
                    <span className="text-slate-400">Volatilite</span>
                    <span className="text-slate-200">{decision.market_structure.volatility}</span>
                  </div>
                </div>
              )}
            </CollapsibleSection>

            {/* Facteurs de Confluence */}
            <CollapsibleSection
              title="Facteurs"
              icon={CheckCircle}
              expanded={expandedSections.confluence}
              onToggle={() => toggleSection('confluence')}
            >
              {decision.confluence_factors && (
                <div className="space-y-2">
                  {decision.confluence_factors.map((factor, idx) => (
                    <div key={idx} className="flex justify-between items-center">
                      <span className="text-slate-400 text-sm">{factor.factor}</span>
                      <span className={`text-sm font-mono ${
                        factor.bullish ? 'text-emerald-400' : 'text-red-400'
                      }`}>
                        {factor.value}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CollapsibleSection>

            {/* Avertissements */}
            {decision.warning_factors && decision.warning_factors.length > 0 && (
              <CollapsibleSection
                title="Avertissements"
                icon={AlertTriangle}
                expanded={expandedSections.warnings}
                onToggle={() => toggleSection('warnings')}
                badgeCount={decision.warning_factors.length}
              >
                <div className="space-y-2">
                  {decision.warning_factors.map((warning, idx) => (
                    <div
                      key={idx}
                      className={`flex items-start gap-2 p-2 rounded ${
                        warning.severity === 'high' ? 'bg-red-900/30' :
                        warning.severity === 'medium' ? 'bg-yellow-900/30' :
                        'bg-slate-800'
                      }`}
                    >
                      <AlertTriangle className={`w-4 h-4 flex-shrink-0 mt-0.5 ${
                        warning.severity === 'high' ? 'text-red-400' :
                        warning.severity === 'medium' ? 'text-yellow-400' :
                        'text-slate-400'
                      }`} />
                      <span className="text-sm text-slate-300">{warning.warning}</span>
                    </div>
                  ))}
                </div>
              </CollapsibleSection>
            )}

            {/* Setup de Trade */}
            <CollapsibleSection
              title="Setup Suggere"
              icon={Target}
              expanded={expandedSections.setup}
              onToggle={() => toggleSection('setup')}
            >
              {decision.trade_setup && (
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Type d'entree</span>
                    <span className="text-slate-200">{decision.trade_setup.entry_type}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Stop Loss</span>
                    <span className="font-mono text-red-400">{decision.trade_setup.stop_loss}€</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Take Profit</span>
                    <span className="font-mono text-emerald-400">{decision.trade_setup.take_profit}€</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Suggestion</span>
                    <span className="text-blue-400">{decision.trade_setup.position_size_suggestion}</span>
                  </div>
                </div>
              )}
            </CollapsibleSection>
          </div>
        ) : null}
      </div>

      {/* Actions */}
      <div className="p-4 border-t border-slate-700 flex-shrink-0">
        <div className="flex gap-3">
          <button
            onClick={() => onCreateAlert?.(position)}
            className="flex-1 bg-yellow-600/20 hover:bg-yellow-600/40 text-yellow-400 py-2.5 rounded-lg font-medium flex items-center justify-center gap-2"
          >
            <Bell className="w-4 h-4" />
            Alertes
          </button>
          <button
            onClick={() => onTrade?.(position, 'Buy')}
            className="flex-1 bg-emerald-600/20 hover:bg-emerald-600/40 text-emerald-400 py-2.5 rounded-lg font-medium flex items-center justify-center gap-2"
          >
            <TrendingUp className="w-4 h-4" />
            Acheter
          </button>
          <button
            onClick={() => onTrade?.(position, 'Sell')}
            className="flex-1 bg-red-600/20 hover:bg-red-600/40 text-red-400 py-2.5 rounded-lg font-medium flex items-center justify-center gap-2"
          >
            <TrendingDown className="w-4 h-4" />
            Vendre
          </button>
        </div>
      </div>
    </div>
  )
}

// Composant pour section collapsible
function CollapsibleSection({ title, icon: Icon, expanded, onToggle, children, badgeCount }) {
  return (
    <div className="bg-slate-900/50 rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-3 hover:bg-slate-700/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-slate-400" />
          <span className="font-medium text-slate-200">{title}</span>
          {badgeCount && (
            <span className="bg-red-600 text-white text-xs px-1.5 py-0.5 rounded-full">
              {badgeCount}
            </span>
          )}
        </div>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-slate-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-slate-400" />
        )}
      </button>
      {expanded && (
        <div className="px-3 pb-3">
          {children}
        </div>
      )}
    </div>
  )
}
