/**
 * Store Zustand pour la gestion des stocks analysés.
 *
 * Centralise l'état des stocks, des filtres et des marchés.
 * Remplace la gestion d'état dispersée dans App.jsx.
 *
 * ARCHITECTURE:
 * - État global accessible partout
 * - Actions pour modifier l'état
 * - Sélecteurs pour accéder aux données filtrées
 *
 * UTILISATION:
 *   import { useStockStore } from '@/stores/useStockStore';
 *
 *   // Dans un composant
 *   const stocks = useStockStore((state) => state.stocks);
 *   const addStock = useStockStore((state) => state.addStock);
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

import type {
  StockAnalysis,
  StockFilters,
  MarketPreset,
} from '@/types/stock.types';
import { DEFAULT_FILTERS } from '@/types/stock.types';

// =============================================================================
// TYPES
// =============================================================================

/**
 * État de chargement par marché.
 */
interface MarketLoadState {
  [marketId: string]: {
    loadedCount: number;
    isLoading: boolean;
  };
}

/**
 * État du store.
 */
interface StockState {
  // Données
  stocks: StockAnalysis[];
  markets: MarketPreset[];
  marketLoadState: MarketLoadState;

  // UI
  selectedTicker: string | null;
  filters: StockFilters;

  // Chargement
  isLoading: boolean;
  loadingTickers: Set<string>;
  error: string | null;
}

/**
 * Actions du store.
 */
interface StockActions {
  // Stocks
  addStock: (stock: StockAnalysis) => void;
  addStocks: (stocks: StockAnalysis[]) => void;
  removeStock: (ticker: string) => void;
  clearStocks: () => void;

  // Sélection
  selectStock: (ticker: string | null) => void;

  // Filtres
  setFilters: (filters: Partial<StockFilters>) => void;
  resetFilters: () => void;

  // Marchés
  setMarkets: (markets: MarketPreset[]) => void;
  updateMarketLoadState: (
    marketId: string,
    update: Partial<MarketLoadState[string]>
  ) => void;

  // Chargement
  setLoading: (isLoading: boolean) => void;
  setLoadingTicker: (ticker: string, isLoading: boolean) => void;
  setError: (error: string | null) => void;

  // Utilitaires
  getFilteredStocks: () => StockAnalysis[];
  getStockByTicker: (ticker: string) => StockAnalysis | undefined;
}

/**
 * Type complet du store.
 */
type StockStore = StockState & StockActions;

// =============================================================================
// ÉTAT INITIAL
// =============================================================================

const initialState: StockState = {
  stocks: [],
  markets: [],
  marketLoadState: {},
  selectedTicker: null,
  filters: DEFAULT_FILTERS,
  isLoading: false,
  loadingTickers: new Set(),
  error: null,
};

// =============================================================================
// STORE
// =============================================================================

/**
 * Store Zustand pour les stocks.
 *
 * Utilise le middleware devtools pour le debugging Redux DevTools.
 */
export const useStockStore = create<StockStore>()(
  devtools(
    (set, get) => ({
      // État initial
      ...initialState,

      // =========================================================================
      // ACTIONS STOCKS
      // =========================================================================

      addStock: (stock: StockAnalysis) => {
        set(
          (state) => {
            // Éviter les doublons
            const exists = state.stocks.some((s) => s.ticker === stock.ticker);
            if (exists) {
              // Mettre à jour le stock existant
              return {
                stocks: state.stocks.map((s) =>
                  s.ticker === stock.ticker ? stock : s
                ),
              };
            }
            return { stocks: [...state.stocks, stock] };
          },
          false,
          'addStock'
        );
      },

      addStocks: (stocks: StockAnalysis[]) => {
        set(
          (state) => {
            const existingTickers = new Set(state.stocks.map((s) => s.ticker));
            const newStocks = stocks.filter((s) => !existingTickers.has(s.ticker));
            const updatedStocks = state.stocks.map((existing) => {
              const update = stocks.find((s) => s.ticker === existing.ticker);
              return update || existing;
            });
            return { stocks: [...updatedStocks, ...newStocks] };
          },
          false,
          'addStocks'
        );
      },

      removeStock: (ticker: string) => {
        set(
          (state) => ({
            stocks: state.stocks.filter((s) => s.ticker !== ticker),
            selectedTicker:
              state.selectedTicker === ticker ? null : state.selectedTicker,
          }),
          false,
          'removeStock'
        );
      },

      clearStocks: () => {
        set({ stocks: [], selectedTicker: null }, false, 'clearStocks');
      },

      // =========================================================================
      // ACTIONS SÉLECTION
      // =========================================================================

      selectStock: (ticker: string | null) => {
        set({ selectedTicker: ticker }, false, 'selectStock');
      },

      // =========================================================================
      // ACTIONS FILTRES
      // =========================================================================

      setFilters: (newFilters: Partial<StockFilters>) => {
        set(
          (state) => ({
            filters: { ...state.filters, ...newFilters },
          }),
          false,
          'setFilters'
        );
      },

      resetFilters: () => {
        set({ filters: DEFAULT_FILTERS }, false, 'resetFilters');
      },

      // =========================================================================
      // ACTIONS MARCHÉS
      // =========================================================================

      setMarkets: (markets: MarketPreset[]) => {
        set({ markets }, false, 'setMarkets');
      },

      updateMarketLoadState: (
        marketId: string,
        update: Partial<MarketLoadState[string]>
      ) => {
        set(
          (state) => ({
            marketLoadState: {
              ...state.marketLoadState,
              [marketId]: {
                loadedCount: state.marketLoadState[marketId]?.loadedCount ?? 0,
                isLoading: state.marketLoadState[marketId]?.isLoading ?? false,
                ...update,
              },
            },
          }),
          false,
          'updateMarketLoadState'
        );
      },

      // =========================================================================
      // ACTIONS CHARGEMENT
      // =========================================================================

      setLoading: (isLoading: boolean) => {
        set({ isLoading }, false, 'setLoading');
      },

      setLoadingTicker: (ticker: string, isLoading: boolean) => {
        set(
          (state) => {
            const loadingTickers = new Set(state.loadingTickers);
            if (isLoading) {
              loadingTickers.add(ticker);
            } else {
              loadingTickers.delete(ticker);
            }
            return { loadingTickers };
          },
          false,
          'setLoadingTicker'
        );
      },

      setError: (error: string | null) => {
        set({ error }, false, 'setError');
      },

      // =========================================================================
      // SÉLECTEURS
      // =========================================================================

      getFilteredStocks: () => {
        const { stocks, filters } = get();

        return stocks.filter((stock) => {
          // Filtre résilience
          if (filters.resilientOnly && !stock.is_resilient) {
            return false;
          }

          // Filtre volatilité
          if (
            stock.volatility !== null &&
            stock.volatility > filters.maxVolatility
          ) {
            return false;
          }

          // Filtre recherche
          if (filters.searchQuery) {
            const query = filters.searchQuery.toLowerCase();
            const matchesTicker = stock.ticker.toLowerCase().includes(query);
            const matchesName = stock.info.name.toLowerCase().includes(query);
            if (!matchesTicker && !matchesName) {
              return false;
            }
          }

          // Filtre type d'actif
          if (
            filters.assetTypes.length > 0 &&
            !filters.assetTypes.includes(stock.info.asset_type)
          ) {
            return false;
          }

          return true;
        });
      },

      getStockByTicker: (ticker: string) => {
        return get().stocks.find((s) => s.ticker === ticker);
      },
    }),
    {
      name: 'stock-store',
    }
  )
);

// =============================================================================
// SÉLECTEURS EXPORTÉS
// =============================================================================

/**
 * Sélectionne les stocks filtrés.
 */
export const selectFilteredStocks = (state: StockStore) =>
  state.getFilteredStocks();

/**
 * Sélectionne le stock actuellement sélectionné.
 */
export const selectSelectedStock = (state: StockStore) =>
  state.selectedTicker
    ? state.stocks.find((s) => s.ticker === state.selectedTicker)
    : null;

/**
 * Sélectionne le nombre de stocks résilients.
 */
export const selectResilientCount = (state: StockStore) =>
  state.stocks.filter((s) => s.is_resilient).length;

/**
 * Sélectionne si un ticker est en cours de chargement.
 */
export const selectIsTickerLoading = (ticker: string) => (state: StockStore) =>
  state.loadingTickers.has(ticker);
