/**
 * Store Zustand pour la gestion de l'authentification broker et du portefeuille.
 *
 * Gère:
 * - État d'authentification (Saxo, futurs brokers)
 * - Données du portefeuille
 * - Ordres en cours
 * - Instruments recherchés
 *
 * ARCHITECTURE:
 * - Séparé du stockStore pour respecter Single Responsibility
 * - Actions async pour les appels API
 * - Gestion d'erreur centralisée
 *
 * UTILISATION:
 *   import { useBrokerStore } from '@/stores/useBrokerStore';
 *
 *   const isAuthenticated = useBrokerStore((state) => state.isAuthenticated);
 *   const portfolio = useBrokerStore((state) => state.portfolio);
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

import type {
  Portfolio,
  Position,
  Order,
  Instrument,
  Account,
  BrokerName,
  PortfolioSummary,
} from '@/types/portfolio.types';

// =============================================================================
// TYPES
// =============================================================================

/**
 * État de l'authentification.
 */
interface AuthState {
  /** Broker actuellement connecté */
  broker: BrokerName | null;

  /** L'utilisateur est-il authentifié? */
  isAuthenticated: boolean;

  /** Chargement de l'authentification en cours */
  isAuthenticating: boolean;

  /** Erreur d'authentification */
  authError: string | null;

  /** Comptes disponibles */
  accounts: Account[];

  /** Compte sélectionné */
  selectedAccountKey: string | null;
}

/**
 * État du portefeuille.
 */
interface PortfolioState {
  /** Positions du portefeuille */
  positions: Position[];

  /** Résumé du portefeuille */
  summary: PortfolioSummary | null;

  /** Chargement en cours */
  isLoadingPortfolio: boolean;

  /** Dernière mise à jour */
  lastUpdated: string | null;

  /** Erreur de chargement */
  portfolioError: string | null;
}

/**
 * État des ordres.
 */
interface OrdersState {
  /** Ordres actifs */
  orders: Order[];

  /** Chargement en cours */
  isLoadingOrders: boolean;

  /** Ordre en cours de création */
  isPlacingOrder: boolean;

  /** Erreur */
  ordersError: string | null;
}

/**
 * État de recherche d'instruments.
 */
interface InstrumentSearchState {
  /** Résultats de recherche */
  searchResults: Instrument[];

  /** Recherche en cours */
  isSearching: boolean;

  /** Dernière requête */
  lastQuery: string;
}

/**
 * État complet du store broker.
 */
interface BrokerState
  extends AuthState,
    PortfolioState,
    OrdersState,
    InstrumentSearchState {}

/**
 * Actions du store.
 */
interface BrokerActions {
  // Authentification
  setAuthenticated: (broker: BrokerName, accounts: Account[]) => void;
  setAuthenticating: (isAuthenticating: boolean) => void;
  setAuthError: (error: string | null) => void;
  logout: () => void;
  selectAccount: (accountKey: string) => void;

  // Portefeuille
  setPortfolio: (portfolio: Portfolio) => void;
  setLoadingPortfolio: (isLoading: boolean) => void;
  setPortfolioError: (error: string | null) => void;
  updatePosition: (symbol: string, updates: Partial<Position>) => void;
  clearPortfolio: () => void;

  // Ordres
  setOrders: (orders: Order[]) => void;
  addOrder: (order: Order) => void;
  updateOrder: (orderId: string, updates: Partial<Order>) => void;
  removeOrder: (orderId: string) => void;
  setLoadingOrders: (isLoading: boolean) => void;
  setPlacingOrder: (isPlacing: boolean) => void;
  setOrdersError: (error: string | null) => void;

  // Recherche instruments
  setSearchResults: (results: Instrument[]) => void;
  setSearching: (isSearching: boolean) => void;
  setLastQuery: (query: string) => void;
  clearSearchResults: () => void;

  // Utilitaires
  getPositionBySymbol: (symbol: string) => Position | undefined;
  getOrderById: (orderId: string) => Order | undefined;
  reset: () => void;
}

/**
 * Type complet du store.
 */
type BrokerStore = BrokerState & BrokerActions;

// =============================================================================
// ÉTAT INITIAL
// =============================================================================

const initialAuthState: AuthState = {
  broker: null,
  isAuthenticated: false,
  isAuthenticating: false,
  authError: null,
  accounts: [],
  selectedAccountKey: null,
};

const initialPortfolioState: PortfolioState = {
  positions: [],
  summary: null,
  isLoadingPortfolio: false,
  lastUpdated: null,
  portfolioError: null,
};

const initialOrdersState: OrdersState = {
  orders: [],
  isLoadingOrders: false,
  isPlacingOrder: false,
  ordersError: null,
};

const initialSearchState: InstrumentSearchState = {
  searchResults: [],
  isSearching: false,
  lastQuery: '',
};

const initialState: BrokerState = {
  ...initialAuthState,
  ...initialPortfolioState,
  ...initialOrdersState,
  ...initialSearchState,
};

// =============================================================================
// STORE
// =============================================================================

/**
 * Store Zustand pour le broker.
 *
 * Utilise le middleware devtools pour le debugging Redux DevTools.
 */
export const useBrokerStore = create<BrokerStore>()(
  devtools(
    (set, get) => ({
      // État initial
      ...initialState,

      // =========================================================================
      // ACTIONS AUTHENTIFICATION
      // =========================================================================

      setAuthenticated: (broker: BrokerName, accounts: Account[]) => {
        set(
          {
            broker,
            isAuthenticated: true,
            isAuthenticating: false,
            authError: null,
            accounts,
            selectedAccountKey: accounts[0]?.account_key || null,
          },
          false,
          'setAuthenticated'
        );
      },

      setAuthenticating: (isAuthenticating: boolean) => {
        set({ isAuthenticating }, false, 'setAuthenticating');
      },

      setAuthError: (authError: string | null) => {
        set({ authError, isAuthenticating: false }, false, 'setAuthError');
      },

      logout: () => {
        set(
          {
            ...initialAuthState,
            ...initialPortfolioState,
            ...initialOrdersState,
          },
          false,
          'logout'
        );
      },

      selectAccount: (accountKey: string) => {
        set({ selectedAccountKey: accountKey }, false, 'selectAccount');
      },

      // =========================================================================
      // ACTIONS PORTEFEUILLE
      // =========================================================================

      setPortfolio: (portfolio: Portfolio) => {
        set(
          {
            positions: portfolio.positions,
            summary: portfolio.summary,
            lastUpdated: portfolio.updated_at,
            isLoadingPortfolio: false,
            portfolioError: null,
          },
          false,
          'setPortfolio'
        );
      },

      setLoadingPortfolio: (isLoadingPortfolio: boolean) => {
        set({ isLoadingPortfolio }, false, 'setLoadingPortfolio');
      },

      setPortfolioError: (portfolioError: string | null) => {
        set(
          { portfolioError, isLoadingPortfolio: false },
          false,
          'setPortfolioError'
        );
      },

      updatePosition: (symbol: string, updates: Partial<Position>) => {
        set(
          (state) => ({
            positions: state.positions.map((pos) =>
              pos.symbol === symbol ? { ...pos, ...updates } : pos
            ),
          }),
          false,
          'updatePosition'
        );
      },

      clearPortfolio: () => {
        set(initialPortfolioState, false, 'clearPortfolio');
      },

      // =========================================================================
      // ACTIONS ORDRES
      // =========================================================================

      setOrders: (orders: Order[]) => {
        set(
          { orders, isLoadingOrders: false, ordersError: null },
          false,
          'setOrders'
        );
      },

      addOrder: (order: Order) => {
        set(
          (state) => ({
            orders: [order, ...state.orders],
            isPlacingOrder: false,
          }),
          false,
          'addOrder'
        );
      },

      updateOrder: (orderId: string, updates: Partial<Order>) => {
        set(
          (state) => ({
            orders: state.orders.map((order) =>
              order.order_id === orderId ? { ...order, ...updates } : order
            ),
          }),
          false,
          'updateOrder'
        );
      },

      removeOrder: (orderId: string) => {
        set(
          (state) => ({
            orders: state.orders.filter((order) => order.order_id !== orderId),
          }),
          false,
          'removeOrder'
        );
      },

      setLoadingOrders: (isLoadingOrders: boolean) => {
        set({ isLoadingOrders }, false, 'setLoadingOrders');
      },

      setPlacingOrder: (isPlacingOrder: boolean) => {
        set({ isPlacingOrder }, false, 'setPlacingOrder');
      },

      setOrdersError: (ordersError: string | null) => {
        set(
          { ordersError, isLoadingOrders: false, isPlacingOrder: false },
          false,
          'setOrdersError'
        );
      },

      // =========================================================================
      // ACTIONS RECHERCHE INSTRUMENTS
      // =========================================================================

      setSearchResults: (searchResults: Instrument[]) => {
        set(
          { searchResults, isSearching: false },
          false,
          'setSearchResults'
        );
      },

      setSearching: (isSearching: boolean) => {
        set({ isSearching }, false, 'setSearching');
      },

      setLastQuery: (lastQuery: string) => {
        set({ lastQuery }, false, 'setLastQuery');
      },

      clearSearchResults: () => {
        set(
          { searchResults: [], lastQuery: '' },
          false,
          'clearSearchResults'
        );
      },

      // =========================================================================
      // SÉLECTEURS
      // =========================================================================

      getPositionBySymbol: (symbol: string) => {
        return get().positions.find((pos) => pos.symbol === symbol);
      },

      getOrderById: (orderId: string) => {
        return get().orders.find((order) => order.order_id === orderId);
      },

      reset: () => {
        set(initialState, false, 'reset');
      },
    }),
    {
      name: 'broker-store',
    }
  )
);

// =============================================================================
// SÉLECTEURS EXPORTÉS
// =============================================================================

/**
 * Sélectionne si l'utilisateur est authentifié auprès d'un broker.
 */
export const selectIsAuthenticated = (state: BrokerStore) =>
  state.isAuthenticated;

/**
 * Sélectionne le broker actuel.
 */
export const selectBroker = (state: BrokerStore) => state.broker;

/**
 * Sélectionne les positions du portefeuille.
 */
export const selectPositions = (state: BrokerStore) => state.positions;

/**
 * Sélectionne le résumé du portefeuille.
 */
export const selectPortfolioSummary = (state: BrokerStore) => state.summary;

/**
 * Sélectionne les positions profitables.
 */
export const selectProfitablePositions = (state: BrokerStore) =>
  state.positions.filter((pos) => pos.pnl > 0);

/**
 * Sélectionne les positions en perte.
 */
export const selectLosingPositions = (state: BrokerStore) =>
  state.positions.filter((pos) => pos.pnl < 0);

/**
 * Sélectionne les ordres actifs (non exécutés/annulés).
 */
export const selectActiveOrders = (state: BrokerStore) =>
  state.orders.filter(
    (order) =>
      order.status === 'pending' ||
      order.status === 'working' ||
      order.status === 'partially_filled'
  );

/**
 * Sélectionne le compte actuellement sélectionné.
 */
export const selectSelectedAccount = (state: BrokerStore) =>
  state.accounts.find(
    (account) => account.account_key === state.selectedAccountKey
  );

/**
 * Calcule le total investi dans le portefeuille.
 */
export const selectTotalInvested = (state: BrokerStore) =>
  state.positions.reduce(
    (total, pos) => total + pos.average_price * pos.quantity,
    0
  );

/**
 * Calcule le PnL total en pourcentage.
 */
export const selectTotalPnLPercent = (state: BrokerStore) => {
  const totalInvested = state.positions.reduce(
    (total, pos) => total + pos.average_price * pos.quantity,
    0
  );
  if (totalInvested === 0) return 0;
  const totalPnL = state.positions.reduce((total, pos) => total + pos.pnl, 0);
  return (totalPnL / totalInvested) * 100;
};
