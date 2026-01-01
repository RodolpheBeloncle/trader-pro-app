/**
 * Service WebSocket pour les prix en temps reel.
 *
 * Gere la connexion WebSocket, les subscriptions aux tickers,
 * et la reception des mises a jour de prix.
 *
 * UTILISATION:
 *   const ws = new WebSocketService();
 *   ws.onPriceUpdate((update) => console.log(update));
 *   await ws.connect();
 *   ws.subscribe("AAPL");
 */

// Types des messages
export interface PriceUpdate {
  type: "price_update";
  ticker: string;
  price: number;
  change: number | null;
  change_percent: number | null;
  timestamp: string;
}

export interface WebSocketMessage {
  type: string;
  [key: string]: unknown;
}

export interface ConnectionState {
  connected: boolean;
  clientId: string | null;
  reconnecting: boolean;
  error: string | null;
}

// Types de callbacks
type PriceUpdateCallback = (update: PriceUpdate) => void;
type ConnectionCallback = (state: ConnectionState) => void;
type ErrorCallback = (error: string) => void;

// Configuration
const WS_BASE_URL =
  import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws/prices";
const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECT_ATTEMPTS = 10;

/**
 * Service WebSocket avec reconnexion automatique.
 */
export class WebSocketService {
  private socket: WebSocket | null = null;
  private clientId: string | null = null;
  private subscriptions: Set<string> = new Set();
  private reconnectAttempts = 0;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

  // Callbacks
  private priceUpdateCallbacks: PriceUpdateCallback[] = [];
  private connectionCallbacks: ConnectionCallback[] = [];
  private errorCallbacks: ErrorCallback[] = [];

  // State
  private _connected = false;
  private _reconnecting = false;

  /**
   * Indique si le WebSocket est connecte.
   */
  get connected(): boolean {
    return this._connected;
  }

  /**
   * Indique si une reconnexion est en cours.
   */
  get reconnecting(): boolean {
    return this._reconnecting;
  }

  /**
   * Retourne l'ensemble des tickers abonnes.
   */
  get subscribedTickers(): Set<string> {
    return new Set(this.subscriptions);
  }

  /**
   * Connecte au serveur WebSocket.
   */
  async connect(): Promise<void> {
    if (this.socket?.readyState === WebSocket.OPEN) {
      console.log("WebSocket already connected");
      return;
    }

    return new Promise((resolve, reject) => {
      try {
        console.log(`Connecting to WebSocket: ${WS_BASE_URL}`);
        this.socket = new WebSocket(WS_BASE_URL);

        this.socket.onopen = () => {
          console.log("WebSocket connected");
          this._connected = true;
          this._reconnecting = false;
          this.reconnectAttempts = 0;
          this._notifyConnectionChange();

          // Re-subscribe aux tickers precedents
          this._resubscribe();

          resolve();
        };

        this.socket.onclose = (event) => {
          console.log(`WebSocket closed: ${event.code} ${event.reason}`);
          this._connected = false;
          this.clientId = null;
          this._notifyConnectionChange();

          // Reconnexion automatique si fermeture inattendue
          if (!event.wasClean && this.reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
            this._scheduleReconnect();
          }
        };

        this.socket.onerror = (error) => {
          console.error("WebSocket error:", error);
          this._notifyError("WebSocket connection error");
          reject(new Error("WebSocket connection failed"));
        };

        this.socket.onmessage = (event) => {
          this._handleMessage(event.data);
        };
      } catch (error) {
        console.error("Failed to create WebSocket:", error);
        reject(error);
      }
    });
  }

  /**
   * Deconnecte du serveur WebSocket.
   */
  disconnect(): void {
    this._clearReconnectTimeout();

    if (this.socket) {
      this.socket.close(1000, "Client disconnect");
      this.socket = null;
    }

    this._connected = false;
    this._reconnecting = false;
    this.clientId = null;
    this._notifyConnectionChange();
  }

  /**
   * S'abonne aux mises a jour d'un ticker.
   */
  subscribe(ticker: string): void {
    ticker = ticker.toUpperCase();
    this.subscriptions.add(ticker);

    if (this._connected) {
      this._send({ type: "subscribe", ticker });
    }
  }

  /**
   * Se desabonne d'un ticker.
   */
  unsubscribe(ticker: string): void {
    ticker = ticker.toUpperCase();
    this.subscriptions.delete(ticker);

    if (this._connected) {
      this._send({ type: "unsubscribe", ticker });
    }
  }

  /**
   * Enregistre un callback pour les mises a jour de prix.
   */
  onPriceUpdate(callback: PriceUpdateCallback): () => void {
    this.priceUpdateCallbacks.push(callback);
    return () => {
      const index = this.priceUpdateCallbacks.indexOf(callback);
      if (index > -1) {
        this.priceUpdateCallbacks.splice(index, 1);
      }
    };
  }

  /**
   * Enregistre un callback pour les changements de connexion.
   */
  onConnectionChange(callback: ConnectionCallback): () => void {
    this.connectionCallbacks.push(callback);
    return () => {
      const index = this.connectionCallbacks.indexOf(callback);
      if (index > -1) {
        this.connectionCallbacks.splice(index, 1);
      }
    };
  }

  /**
   * Enregistre un callback pour les erreurs.
   */
  onError(callback: ErrorCallback): () => void {
    this.errorCallbacks.push(callback);
    return () => {
      const index = this.errorCallbacks.indexOf(callback);
      if (index > -1) {
        this.errorCallbacks.splice(index, 1);
      }
    };
  }

  /**
   * Envoie un ping au serveur.
   */
  ping(): void {
    this._send({ type: "ping" });
  }

  // =========================================================================
  // Private methods
  // =========================================================================

  private _send(message: WebSocketMessage): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
    }
  }

  private _handleMessage(data: string): void {
    try {
      const message: WebSocketMessage = JSON.parse(data);

      switch (message.type) {
        case "connected":
          this.clientId = message.client_id as string;
          console.log(`WebSocket client ID: ${this.clientId}`);
          break;

        case "subscribed":
          console.log(`Subscribed to: ${message.ticker}`);
          break;

        case "unsubscribed":
          console.log(`Unsubscribed from: ${message.ticker}`);
          break;

        case "price_update":
          this._notifyPriceUpdate(message as unknown as PriceUpdate);
          break;

        case "pong":
          console.log("Pong received");
          break;

        case "error":
          console.error(`WebSocket error: ${message.message}`);
          this._notifyError(message.message as string);
          break;

        default:
          console.log(`Unknown message type: ${message.type}`);
      }
    } catch (error) {
      console.error("Failed to parse WebSocket message:", error);
    }
  }

  private _scheduleReconnect(): void {
    if (this._reconnecting) return;

    this._reconnecting = true;
    this.reconnectAttempts++;
    this._notifyConnectionChange();

    const delay = RECONNECT_DELAY_MS * Math.min(this.reconnectAttempts, 5);
    console.log(
      `Scheduling reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`
    );

    this.reconnectTimeout = setTimeout(() => {
      console.log("Attempting to reconnect...");
      this.connect().catch((error) => {
        console.error("Reconnect failed:", error);
        if (this.reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
          this._scheduleReconnect();
        } else {
          this._notifyError("Max reconnection attempts reached");
        }
      });
    }, delay);
  }

  private _clearReconnectTimeout(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
  }

  private _resubscribe(): void {
    for (const ticker of this.subscriptions) {
      this._send({ type: "subscribe", ticker });
    }
  }

  private _notifyPriceUpdate(update: PriceUpdate): void {
    for (const callback of this.priceUpdateCallbacks) {
      try {
        callback(update);
      } catch (error) {
        console.error("Error in price update callback:", error);
      }
    }
  }

  private _notifyConnectionChange(): void {
    const state: ConnectionState = {
      connected: this._connected,
      clientId: this.clientId,
      reconnecting: this._reconnecting,
      error: null,
    };

    for (const callback of this.connectionCallbacks) {
      try {
        callback(state);
      } catch (error) {
        console.error("Error in connection callback:", error);
      }
    }
  }

  private _notifyError(error: string): void {
    for (const callback of this.errorCallbacks) {
      try {
        callback(error);
      } catch (err) {
        console.error("Error in error callback:", err);
      }
    }
  }
}

// Instance singleton
let wsServiceInstance: WebSocketService | null = null;

/**
 * Retourne l'instance singleton du WebSocketService.
 */
export function getWebSocketService(): WebSocketService {
  if (!wsServiceInstance) {
    wsServiceInstance = new WebSocketService();
  }
  return wsServiceInstance;
}
