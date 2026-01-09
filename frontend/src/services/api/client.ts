/**
 * Client HTTP centralisé avec Axios.
 *
 * Fournit une instance Axios configurée avec :
 * - Base URL vers le backend
 * - Intercepteurs pour les erreurs
 * - Timeout configurable
 * - Types TypeScript
 *
 * ARCHITECTURE:
 * - Tous les appels API passent par ce client
 * - Les intercepteurs gèrent les erreurs de manière centralisée
 * - Les services spécifiques (stockApi, brokerApi) utilisent ce client
 *
 * UTILISATION:
 *   import { apiClient } from '@/services/api/client';
 *
 *   const response = await apiClient.get<StockAnalysis>('/analyze', { params: { ticker } });
 */

import axios, {
  type AxiosInstance,
  type AxiosError,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios';

// =============================================================================
// CONFIGURATION
// =============================================================================

/**
 * Configuration du client API.
 */
interface ApiConfig {
  /** URL de base de l'API */
  baseURL: string;

  /** Timeout en millisecondes */
  timeout: number;

  /** Headers par défaut */
  headers: Record<string, string>;
}

/**
 * Configuration par défaut.
 * En développement, le proxy Vite redirige /api vers le backend.
 */
const DEFAULT_CONFIG: ApiConfig = {
  baseURL: '/api',
  timeout: 30000, // 30 secondes
  headers: {
    'Content-Type': 'application/json',
  },
};

// =============================================================================
// TYPES D'ERREUR
// =============================================================================

/**
 * Structure d'erreur API.
 */
export interface ApiError {
  /** Code d'erreur */
  code: string;

  /** Message d'erreur */
  message: string;

  /** Détails additionnels */
  details?: Record<string, unknown>;

  /** Code HTTP */
  status: number;
}

// =============================================================================
// INTERCEPTEURS
// =============================================================================

/**
 * Intercepteur de requête.
 * Ajoute les headers nécessaires.
 */
function requestInterceptor(
  config: InternalAxiosRequestConfig
): InternalAxiosRequestConfig {
  // Ajouter un timestamp pour éviter le cache
  if (config.params) {
    config.params._t = Date.now();
  }

  // Log en développement
  if (import.meta.env.DEV) {
    console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`);
  }

  return config;
}

/**
 * Intercepteur d'erreur de requête.
 */
function requestErrorInterceptor(error: AxiosError): Promise<never> {
  console.error('[API] Erreur de requête:', error.message);
  return Promise.reject(error);
}

/**
 * Intercepteur de réponse (succès).
 */
function responseInterceptor(response: AxiosResponse): AxiosResponse {
  return response;
}

/**
 * Intercepteur d'erreur de réponse.
 * Transforme les erreurs en format standardisé.
 */
function responseErrorInterceptor(error: AxiosError<ApiError>): Promise<never> {
  // Erreur réseau (pas de réponse)
  if (!error.response) {
    const networkError: ApiError = {
      code: 'NETWORK_ERROR',
      message: 'Impossible de se connecter au serveur. Vérifiez votre connexion.',
      status: 0,
    };
    console.error('[API] Erreur réseau:', error.message);
    return Promise.reject(networkError);
  }

  const { status, data } = error.response;

  // Construire une erreur standardisée
  const apiError: ApiError = {
    code: data?.code || `HTTP_${status}`,
    message: data?.message || getDefaultErrorMessage(status),
    details: data?.details,
    status,
  };

  // Log de l'erreur
  console.error(`[API] Erreur ${status}:`, apiError.message);

  // Actions spéciales selon le code
  switch (status) {
    case 401:
      // Token expiré - on pourrait déclencher un refresh ici
      console.warn('[API] Session expirée');
      break;
    case 429:
      console.warn('[API] Rate limit atteint');
      break;
  }

  return Promise.reject(apiError);
}

/**
 * Message d'erreur par défaut selon le code HTTP.
 */
function getDefaultErrorMessage(status: number): string {
  const messages: Record<number, string> = {
    400: 'Requête invalide',
    401: 'Authentification requise',
    403: 'Accès refusé',
    404: 'Ressource non trouvée',
    408: 'Délai d\'attente dépassé',
    429: 'Trop de requêtes, veuillez réessayer plus tard',
    500: 'Erreur serveur interne',
    502: 'Service temporairement indisponible',
    503: 'Service en maintenance',
  };

  return messages[status] || `Erreur HTTP ${status}`;
}

// =============================================================================
// CRÉATION DU CLIENT
// =============================================================================

/**
 * Crée une instance Axios configurée.
 */
function createApiClient(config: Partial<ApiConfig> = {}): AxiosInstance {
  const mergedConfig = { ...DEFAULT_CONFIG, ...config };

  const client = axios.create({
    baseURL: mergedConfig.baseURL,
    timeout: mergedConfig.timeout,
    headers: mergedConfig.headers,
  });

  // Ajouter les intercepteurs
  client.interceptors.request.use(requestInterceptor, requestErrorInterceptor);
  client.interceptors.response.use(responseInterceptor, responseErrorInterceptor);

  return client;
}

// =============================================================================
// EXPORTS
// =============================================================================

/**
 * Instance principale du client API.
 *
 * Utiliser cette instance pour tous les appels API.
 */
export const apiClient = createApiClient();

/**
 * Crée un nouveau client avec une configuration personnalisée.
 *
 * Utile pour les tests ou les configurations spéciales.
 */
export { createApiClient };

/**
 * Réexporte les types Axios utiles.
 */
export type { AxiosResponse, AxiosError };

// =============================================================================
// HELPERS
// =============================================================================

/**
 * Helper pour les requêtes GET typées.
 */
export async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const response = await apiClient.get<T>(url, { params });
  return response.data;
}

/**
 * Helper pour les requêtes POST typées.
 */
export async function post<T, D = unknown>(url: string, data?: D): Promise<T> {
  const response = await apiClient.post<T>(url, data);
  return response.data;
}

/**
 * Helper pour les requêtes DELETE typées.
 */
export async function del<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const response = await apiClient.delete<T>(url, { params });
  return response.data;
}

/**
 * Vérifie si une erreur est une ApiError.
 */
export function isApiError(error: unknown): error is ApiError {
  return (
    typeof error === 'object' &&
    error !== null &&
    'code' in error &&
    'message' in error &&
    'status' in error
  );
}
