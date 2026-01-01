/**
 * Types pour le portefeuille et le trading.
 *
 * Correspondent aux types du broker (Saxo, etc.).
 * Utilisés par useBrokerStore et les features portfolio/trading.
 */

import type { AssetType } from './stock.types';

// =============================================================================
// ORDRES
// =============================================================================

/** Types d'ordres supportés */
export type OrderType = 'Market' | 'Limit' | 'Stop' | 'StopLimit';

/** Direction de l'ordre */
export type OrderSide = 'Buy' | 'Sell';

/** Statuts possibles d'un ordre */
export type OrderStatus =
  | 'pending'
  | 'working'
  | 'filled'
  | 'partially_filled'
  | 'cancelled'
  | 'rejected'
  | 'expired';

// =============================================================================
// POSITIONS
// =============================================================================

/**
 * Position dans le portefeuille.
 */
export interface Position {
  /** Symbole de l'instrument */
  readonly symbol: string;

  /** Description/nom */
  readonly description?: string;

  /** Quantité détenue */
  readonly quantity: number;

  /** Prix actuel */
  readonly current_price: number;

  /** Prix d'achat moyen */
  readonly average_price: number;

  /** Valeur de marché totale */
  readonly market_value: number;

  /** Profit/perte en valeur */
  readonly pnl: number;

  /** Profit/perte en pourcentage */
  readonly pnl_percent: number;

  /** Devise */
  readonly currency: string;

  /** Type d'actif */
  readonly asset_type: AssetType;

  /** ID interne du broker */
  readonly broker_id?: string;

  /** Universal Instrument Code (Saxo) */
  readonly uic?: number;

  // Enrichissement par analyse (optionnel)
  readonly perf_3m?: number | null;
  readonly perf_6m?: number | null;
  readonly perf_1y?: number | null;
  readonly is_resilient?: boolean;
  readonly volatility?: number | null;
  readonly analysis_error?: string;
}

// =============================================================================
// PORTEFEUILLE
// =============================================================================

/**
 * Résumé du portefeuille.
 */
export interface PortfolioSummary {
  /** Nombre total de positions */
  readonly total_positions: number;

  /** Valeur totale du portefeuille */
  readonly total_value: number;

  /** Profit/perte total */
  readonly total_pnl: number;

  /** Profit/perte en pourcentage */
  readonly total_pnl_percent: number;

  /** Nombre de positions résilientes */
  readonly resilient_count: number;

  /** Pourcentage de positions résilientes */
  readonly resilient_percent: number;
}

/**
 * Portefeuille complet.
 */
export interface Portfolio {
  /** Liste des positions */
  readonly positions: Position[];

  /** Clé du compte */
  readonly account_key: string | null;

  /** Résumé */
  readonly summary: PortfolioSummary;

  /** Horodatage de mise à jour */
  readonly updated_at: string;
}

// =============================================================================
// ORDRES
// =============================================================================

/**
 * Ordre existant.
 */
export interface Order {
  /** ID unique */
  readonly order_id: string;

  /** Symbole */
  readonly symbol: string;

  /** Direction */
  readonly side: OrderSide;

  /** Type d'ordre */
  readonly order_type: OrderType;

  /** Quantité demandée */
  readonly quantity: number;

  /** Quantité exécutée */
  readonly filled_quantity: number;

  /** Prix (pour Limit orders) */
  readonly price: number | null;

  /** Statut */
  readonly status: OrderStatus;

  /** Date de création */
  readonly created_at: string;

  /** Date de mise à jour */
  readonly updated_at?: string;
}

/**
 * Formulaire pour placer un ordre.
 */
export interface OrderForm {
  /** Symbole ou UIC */
  symbol: string;

  /** Type d'actif */
  asset_type: AssetType;

  /** Quantité */
  quantity: number;

  /** Type d'ordre */
  order_type: OrderType;

  /** Direction */
  side: OrderSide;

  /** Prix limite (optionnel) */
  price?: number;

  /** UIC (Saxo) */
  uic?: number;
}

/**
 * Valeurs par défaut du formulaire d'ordre.
 */
export const DEFAULT_ORDER_FORM: OrderForm = {
  symbol: '',
  asset_type: 'stock',
  quantity: 1,
  order_type: 'Market',
  side: 'Buy',
};

// =============================================================================
// INSTRUMENTS
// =============================================================================

/**
 * Instrument (résultat de recherche).
 */
export interface Instrument {
  /** Symbole */
  readonly symbol: string;

  /** Nom complet */
  readonly name: string;

  /** Type d'actif */
  readonly asset_type: AssetType;

  /** Bourse */
  readonly exchange?: string;

  /** Devise */
  readonly currency?: string;

  /** Universal Instrument Code (Saxo) */
  readonly uic?: number;
}

// =============================================================================
// TRANSACTIONS
// =============================================================================

/**
 * Transaction historique.
 */
export interface Transaction {
  /** ID */
  readonly id: string;

  /** Symbole */
  readonly symbol: string;

  /** Direction */
  readonly side: OrderSide;

  /** Quantité */
  readonly quantity: number;

  /** Prix d'exécution */
  readonly price: number;

  /** Montant total */
  readonly amount: number;

  /** Date */
  readonly date: string;

  /** Devise */
  readonly currency: string;
}

// =============================================================================
// COMPTES
// =============================================================================

/**
 * Compte de trading.
 */
export interface Account {
  /** Clé du compte */
  readonly account_key: string;

  /** ID du compte */
  readonly account_id: string;

  /** Nom */
  readonly name?: string;

  /** Devise */
  readonly currency: string;

  /** Solde */
  readonly balance?: number;
}

// =============================================================================
// AUTHENTIFICATION
// =============================================================================

/** Brokers supportés */
export type BrokerName = 'saxo';

/**
 * État de l'authentification broker.
 */
export interface BrokerAuthState {
  /** Broker actuellement connecté */
  readonly broker: BrokerName | null;

  /** L'utilisateur est-il authentifié? */
  readonly isAuthenticated: boolean;

  /** Chargement en cours */
  readonly isLoading: boolean;

  /** Message d'erreur */
  readonly error: string | null;
}

// =============================================================================
// RÉPONSES API
// =============================================================================

/**
 * Réponse de statut de configuration.
 */
export interface BrokerStatusResponse {
  readonly configured: boolean;
  readonly message: string;
}

/**
 * Réponse d'URL d'autorisation.
 */
export interface AuthUrlResponse {
  readonly auth_url: string;
  readonly state?: string;
}

/**
 * Réponse de callback OAuth.
 */
export interface AuthCallbackResponse {
  readonly success: boolean;
  readonly access_token?: string;
  readonly expires_at?: string;
  readonly error?: string;
}

// =============================================================================
// UTILITAIRES
// =============================================================================

/**
 * Vérifie si une position est profitable.
 */
export function isProfitable(position: Position): boolean {
  return position.pnl > 0;
}

/**
 * Calcule le pourcentage de positions profitables.
 */
export function getProfitablePercentage(positions: Position[]): number {
  if (positions.length === 0) return 0;
  const profitable = positions.filter(isProfitable).length;
  return (profitable / positions.length) * 100;
}

/**
 * Formate un montant avec la devise.
 */
export function formatMoney(amount: number, currency: string): string {
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency,
  }).format(amount);
}
