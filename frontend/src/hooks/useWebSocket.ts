/**
 * Hook React pour utiliser le service WebSocket.
 *
 * Gere automatiquement:
 * - La connexion/deconnexion
 * - Les subscriptions aux tickers
 * - L'etat de connexion
 * - Les mises a jour de prix
 *
 * UTILISATION:
 *   function MyComponent() {
 *     const { connected, prices, subscribe, unsubscribe } = useWebSocket();
 *
 *     useEffect(() => {
 *       subscribe("AAPL");
 *       return () => unsubscribe("AAPL");
 *     }, []);
 *
 *     return <div>AAPL: ${prices["AAPL"]?.price}</div>;
 *   }
 */

import { useState, useEffect, useCallback, useRef } from "react";
import {
  WebSocketService,
  getWebSocketService,
  PriceUpdate,
  ConnectionState,
} from "../services/api/websocketService";

// Types
export interface PriceData {
  ticker: string;
  price: number;
  change: number | null;
  changePercent: number | null;
  timestamp: Date;
}

export interface UseWebSocketReturn {
  /** Indique si le WebSocket est connecte */
  connected: boolean;
  /** Indique si une reconnexion est en cours */
  reconnecting: boolean;
  /** Dernier message d'erreur */
  error: string | null;
  /** Prix par ticker */
  prices: Record<string, PriceData>;
  /** Tickers actuellement abonnes */
  subscriptions: string[];
  /** S'abonne a un ticker */
  subscribe: (ticker: string) => void;
  /** Se desabonne d'un ticker */
  unsubscribe: (ticker: string) => void;
  /** Se connecte manuellement */
  connect: () => Promise<void>;
  /** Se deconnecte manuellement */
  disconnect: () => void;
}

export interface UseWebSocketOptions {
  /** Se connecter automatiquement au montage */
  autoConnect?: boolean;
  /** Tickers a abonner automatiquement */
  initialTickers?: string[];
}

/**
 * Hook pour utiliser le WebSocket de prix en temps reel.
 */
export function useWebSocket(
  options: UseWebSocketOptions = {}
): UseWebSocketReturn {
  const { autoConnect = true, initialTickers = [] } = options;

  // State
  const [connected, setConnected] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [prices, setPrices] = useState<Record<string, PriceData>>({});
  const [subscriptions, setSubscriptions] = useState<string[]>([]);

  // Ref pour le service WebSocket
  const wsRef = useRef<WebSocketService | null>(null);

  // Initialiser le service
  useEffect(() => {
    wsRef.current = getWebSocketService();

    // Callbacks
    const unsubscribeConnection = wsRef.current.onConnectionChange(
      (state: ConnectionState) => {
        setConnected(state.connected);
        setReconnecting(state.reconnecting);
        if (state.error) {
          setError(state.error);
        }
      }
    );

    const unsubscribePriceUpdate = wsRef.current.onPriceUpdate(
      (update: PriceUpdate) => {
        setPrices((prev) => ({
          ...prev,
          [update.ticker]: {
            ticker: update.ticker,
            price: update.price,
            change: update.change,
            changePercent: update.change_percent,
            timestamp: new Date(update.timestamp),
          },
        }));
      }
    );

    const unsubscribeError = wsRef.current.onError((err: string) => {
      setError(err);
    });

    // Connexion automatique
    if (autoConnect) {
      wsRef.current.connect().catch((err) => {
        console.error("Auto-connect failed:", err);
        setError("Failed to connect to WebSocket");
      });
    }

    // Subscriptions initiales
    if (initialTickers.length > 0) {
      for (const ticker of initialTickers) {
        wsRef.current.subscribe(ticker);
      }
      setSubscriptions([...initialTickers]);
    }

    // Cleanup
    return () => {
      unsubscribeConnection();
      unsubscribePriceUpdate();
      unsubscribeError();
    };
  }, [autoConnect, initialTickers]);

  // Fonction subscribe
  const subscribe = useCallback((ticker: string) => {
    if (wsRef.current) {
      wsRef.current.subscribe(ticker);
      setSubscriptions((prev) => {
        if (prev.includes(ticker.toUpperCase())) return prev;
        return [...prev, ticker.toUpperCase()];
      });
    }
  }, []);

  // Fonction unsubscribe
  const unsubscribe = useCallback((ticker: string) => {
    if (wsRef.current) {
      wsRef.current.unsubscribe(ticker);
      setSubscriptions((prev) =>
        prev.filter((t) => t !== ticker.toUpperCase())
      );
    }
  }, []);

  // Fonction connect
  const connect = useCallback(async () => {
    if (wsRef.current) {
      await wsRef.current.connect();
    }
  }, []);

  // Fonction disconnect
  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.disconnect();
    }
  }, []);

  return {
    connected,
    reconnecting,
    error,
    prices,
    subscriptions,
    subscribe,
    unsubscribe,
    connect,
    disconnect,
  };
}

/**
 * Hook simplifie pour suivre le prix d'un seul ticker.
 */
export function useTickerPrice(ticker: string): PriceData | null {
  const { prices, subscribe, unsubscribe } = useWebSocket({
    autoConnect: true,
  });

  useEffect(() => {
    if (!ticker) return;
    subscribe(ticker);
    return () => unsubscribe(ticker);
  }, [ticker, subscribe, unsubscribe]);

  return prices[ticker.toUpperCase()] || null;
}
