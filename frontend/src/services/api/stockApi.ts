/**
 * Service API pour les stocks.
 *
 * Fournit des fonctions typees pour les appels API relatifs aux stocks.
 */

import { apiClient } from "./client";
import type {
  StockResult,
  MarketPreset,
} from "@/types/stock.types";

// =============================================================================
// TYPES
// =============================================================================

export interface AnalyzeRequest {
  ticker: string;
}

export interface AnalyzeBatchRequest {
  tickers: string[];
}

export interface AnalyzeBatchResponse {
  results: StockResult[];
  total: number;
  resilient_count: number;
}

export interface MarketsResponse {
  markets: MarketPreset[];
}

export interface MarketTickersResponse {
  market: string;
  tickers: string[];
  total: number;
}

export interface ExportRequest {
  tickers: string[];
}

// =============================================================================
// FONCTIONS API
// =============================================================================

/**
 * Analyse un ticker unique.
 */
export async function analyzeStock(ticker: string): Promise<StockResult> {
  const response = await apiClient.post<StockResult>("/api/stocks/analyze", {
    ticker: ticker.toUpperCase(),
  });
  return response.data;
}

/**
 * Analyse plusieurs tickers en batch.
 */
export async function analyzeBatch(
  tickers: string[]
): Promise<AnalyzeBatchResponse> {
  const response = await apiClient.post<AnalyzeBatchResponse>(
    "/api/stocks/analyze/batch",
    {
      tickers: tickers.map((t) => t.toUpperCase()),
    }
  );
  return response.data;
}

/**
 * Recupere la liste des marches disponibles.
 */
export async function getMarkets(): Promise<MarketPreset[]> {
  const response = await apiClient.get<MarketsResponse>("/api/markets");
  return response.data.markets;
}

/**
 * Recupere les tickers d'un marche.
 */
export async function getMarketTickers(
  marketId: string
): Promise<MarketTickersResponse> {
  const response = await apiClient.get<MarketTickersResponse>(
    `/api/markets/${marketId}/tickers`
  );
  return response.data;
}

/**
 * Exporte les analyses en CSV.
 */
export async function exportToCsv(tickers: string[]): Promise<Blob> {
  const response = await apiClient.post(
    "/api/stocks/export",
    { tickers },
    {
      responseType: "blob",
    }
  );
  return response.data;
}

/**
 * Telecharge un fichier CSV.
 */
export function downloadCsv(blob: Blob, filename: string = "stocks.csv"): void {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}
