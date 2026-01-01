/**
 * Types pour les stocks et analyses.
 *
 * Ces types correspondent aux DTOs renvoyés par l'API backend.
 * Ils sont utilisés dans toute l'application frontend.
 *
 * ARCHITECTURE:
 * - Types immuables (readonly)
 * - Correspondance exacte avec l'API
 * - Utilisés par les stores et composants
 */

// =============================================================================
// CONSTANTES
// =============================================================================

/** Types d'actifs supportés */
export type AssetType = 'stock' | 'etf' | 'crypto' | 'cfd' | 'bond';

/** Labels des périodes d'analyse */
export const PERIOD_LABELS = ['3M', '6M', '1Y', '3Y', '5Y'] as const;
export type PeriodLabel = (typeof PERIOD_LABELS)[number];

/** Niveaux de volatilité */
export type VolatilityLevel = 'low' | 'medium' | 'high' | 'unknown';

// =============================================================================
// DONNÉES DE PRIX
// =============================================================================

/**
 * Point de données pour les graphiques de prix.
 */
export interface ChartDataPoint {
  readonly date: string;
  readonly price: number;
}

// =============================================================================
// PERFORMANCES
// =============================================================================

/**
 * Performances sur toutes les périodes.
 *
 * Valeurs en pourcentage (ex: 15.5 pour +15.5%).
 * null signifie que les données ne sont pas disponibles.
 */
export interface PerformanceData {
  readonly perf_3m: number | null;
  readonly perf_6m: number | null;
  readonly perf_1y: number | null;
  readonly perf_3y: number | null;
  readonly perf_5y: number | null;
}

// =============================================================================
// INFORMATIONS STOCK
// =============================================================================

/**
 * Métadonnées d'un stock.
 */
export interface StockInfo {
  readonly name: string;
  readonly currency: string;
  readonly exchange: string | null;
  readonly sector: string | null;
  readonly industry: string | null;
  readonly asset_type: AssetType;
  readonly dividend_yield: number | null;
}

// =============================================================================
// ANALYSE COMPLÈTE
// =============================================================================

/**
 * Résultat complet d'une analyse de stock.
 *
 * C'est le type principal retourné par l'API /api/analyze.
 */
export interface StockAnalysis {
  readonly ticker: string;
  readonly info: StockInfo;
  readonly performances: PerformanceData;
  readonly current_price: number | null;
  readonly currency: string;
  readonly volatility: number | null;
  readonly is_resilient: boolean;
  readonly volatility_level: VolatilityLevel;
  readonly score: number;
  readonly chart_data: ChartDataPoint[];
  readonly analyzed_at: string;
}

/**
 * Réponse d'erreur de l'API.
 */
export interface StockError {
  readonly ticker: string;
  readonly error: string;
}

/**
 * Union type pour les résultats d'analyse.
 */
export type StockResult = StockAnalysis | StockError;

/**
 * Type guard pour vérifier si un résultat est une erreur.
 */
export function isStockError(result: StockResult): result is StockError {
  return 'error' in result;
}

/**
 * Type guard pour vérifier si un résultat est une analyse valide.
 */
export function isStockAnalysis(result: StockResult): result is StockAnalysis {
  return 'is_resilient' in result;
}

// =============================================================================
// MARCHÉS
// =============================================================================

/**
 * Définition d'un preset de marché.
 */
export interface MarketPreset {
  readonly id: string;
  readonly name: string;
  readonly count: number;
  readonly description?: string;
}

/**
 * Réponse de l'API pour la liste des marchés.
 */
export interface MarketsResponse {
  readonly markets: MarketPreset[];
}

/**
 * Réponse de l'API pour les tickers d'un marché.
 */
export interface MarketTickersResponse {
  readonly market: string;
  readonly tickers: string[];
  readonly total: number;
}

// =============================================================================
// FILTRES
// =============================================================================

/**
 * État des filtres d'affichage.
 */
export interface StockFilters {
  /** Afficher uniquement les stocks résilients */
  readonly resilientOnly: boolean;

  /** Volatilité maximale (0-100) */
  readonly maxVolatility: number;

  /** Recherche textuelle */
  readonly searchQuery: string;

  /** Types d'actifs à afficher */
  readonly assetTypes: AssetType[];
}

/**
 * Filtres par défaut.
 */
export const DEFAULT_FILTERS: StockFilters = {
  resilientOnly: false,
  maxVolatility: 100,
  searchQuery: '',
  assetTypes: ['stock', 'etf'],
};

// =============================================================================
// REQUÊTES API
// =============================================================================

/**
 * Requête pour analyser un ticker.
 */
export interface AnalyzeRequest {
  readonly ticker: string;
}

/**
 * Requête pour analyser plusieurs tickers.
 */
export interface AnalyzeBatchRequest {
  readonly tickers: string[];
}

/**
 * Réponse de l'API pour une analyse batch.
 */
export interface AnalyzeBatchResponse {
  readonly results: StockResult[];
  readonly success_count: number;
  readonly error_count: number;
}

// =============================================================================
// UTILITAIRES
// =============================================================================

/**
 * Extrait le label de performance à partir de la clé.
 */
export function getPeriodLabel(key: keyof PerformanceData): PeriodLabel {
  const mapping: Record<keyof PerformanceData, PeriodLabel> = {
    perf_3m: '3M',
    perf_6m: '6M',
    perf_1y: '1Y',
    perf_3y: '3Y',
    perf_5y: '5Y',
  };
  return mapping[key];
}

/**
 * Vérifie si toutes les performances sont positives.
 */
export function areAllPerformancesPositive(perfs: PerformanceData): boolean {
  const values = [
    perfs.perf_3m,
    perfs.perf_6m,
    perfs.perf_1y,
    perfs.perf_3y,
    perfs.perf_5y,
  ];
  return values.every((v) => v !== null && v > 0);
}

/**
 * Formate un pourcentage avec signe.
 */
export function formatPercentage(value: number | null): string {
  if (value === null) return 'N/A';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}
