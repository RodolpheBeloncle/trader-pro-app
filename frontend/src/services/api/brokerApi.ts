/**
 * Service API pour les brokers (Saxo Bank).
 *
 * Fournit des fonctions typees pour les appels API relatifs aux brokers.
 */

import { apiClient } from "./client";
import type { Portfolio, Position, Order } from "@/types/portfolio.types";

// =============================================================================
// TYPES
// =============================================================================

export interface AuthUrlResponse {
  auth_url: string;
  state: string;
}

export interface AuthCallbackRequest {
  code: string;
  state: string;
}

export interface AuthStatusResponse {
  authenticated: boolean;
  broker: string | null;
  account_id: string | null;
  expires_at: string | null;
}

export interface PlaceOrderRequest {
  ticker: string;
  side: "Buy" | "Sell";
  quantity: number;
  order_type: "Market" | "Limit";
  limit_price?: number;
}

export interface PlaceOrderResponse {
  order_id: string;
  status: string;
  message: string;
}

export interface InstrumentSearchResult {
  uic: number;
  symbol: string;
  description: string;
  asset_type: string;
  exchange: string;
}

export interface InstrumentSearchResponse {
  instruments: InstrumentSearchResult[];
}

// =============================================================================
// FONCTIONS API - AUTHENTIFICATION
// =============================================================================

/**
 * Obtient l'URL d'authentification Saxo.
 */
export async function getAuthUrl(): Promise<AuthUrlResponse> {
  const response = await apiClient.get<AuthUrlResponse>("/api/brokers/auth/url");
  return response.data;
}

/**
 * Complete le callback OAuth.
 */
export async function authCallback(
  code: string,
  state: string
): Promise<AuthStatusResponse> {
  const response = await apiClient.post<AuthStatusResponse>(
    "/api/brokers/auth/callback",
    { code, state }
  );
  return response.data;
}

/**
 * Verifie le statut d'authentification.
 */
export async function getAuthStatus(): Promise<AuthStatusResponse> {
  const response = await apiClient.get<AuthStatusResponse>(
    "/api/brokers/auth/status"
  );
  return response.data;
}

/**
 * Deconnexion du broker.
 */
export async function logout(): Promise<void> {
  await apiClient.post("/api/brokers/auth/logout");
}

// =============================================================================
// FONCTIONS API - PORTFOLIO
// =============================================================================

/**
 * Recupere le portefeuille du broker.
 */
export async function getPortfolio(): Promise<Portfolio> {
  const response = await apiClient.get<Portfolio>("/api/brokers/portfolio");
  return response.data;
}

/**
 * Recupere les positions ouvertes.
 */
export async function getPositions(): Promise<Position[]> {
  const response = await apiClient.get<{ positions: Position[] }>(
    "/api/brokers/positions"
  );
  return response.data.positions;
}

// =============================================================================
// FONCTIONS API - TRADING
// =============================================================================

/**
 * Place un ordre.
 */
export async function placeOrder(
  order: PlaceOrderRequest
): Promise<PlaceOrderResponse> {
  const response = await apiClient.post<PlaceOrderResponse>(
    "/api/brokers/orders",
    order
  );
  return response.data;
}

/**
 * Recupere les ordres en cours.
 */
export async function getOrders(): Promise<Order[]> {
  const response = await apiClient.get<{ orders: Order[] }>(
    "/api/brokers/orders"
  );
  return response.data.orders;
}

/**
 * Annule un ordre.
 */
export async function cancelOrder(orderId: string): Promise<void> {
  await apiClient.delete(`/api/brokers/orders/${orderId}`);
}

// =============================================================================
// FONCTIONS API - INSTRUMENTS
// =============================================================================

/**
 * Recherche un instrument par mot-cle.
 */
export async function searchInstruments(
  query: string,
  assetType?: string
): Promise<InstrumentSearchResult[]> {
  const params: Record<string, string> = { q: query };
  if (assetType) {
    params.asset_type = assetType;
  }

  const response = await apiClient.get<InstrumentSearchResponse>(
    "/api/brokers/instruments/search",
    { params }
  );
  return response.data.instruments;
}
