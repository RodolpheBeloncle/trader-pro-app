"""
Client HTTP pour l'API Saxo OpenAPI.

Encapsule tous les appels HTTP vers l'API Saxo.
Gère les headers d'authentification et les erreurs.

ARCHITECTURE:
- Responsabilité unique : communication HTTP avec Saxo
- Pas de logique métier, seulement transport
- Utilisé par SaxoBroker

DOCUMENTATION:
https://www.developer.saxo/openapi/learn
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
from requests.exceptions import RequestException

from src.config.settings import Settings
from src.config.constants import API_TIMEOUT_SECONDS
from src.domain.exceptions import (
    BrokerApiError,
    BrokerAuthenticationError,
    BrokerRateLimitError,
)

logger = logging.getLogger(__name__)


@dataclass
class SaxoApiResponse:
    """Réponse standardisée de l'API Saxo."""

    data: Any
    status_code: int
    headers: Dict[str, str]


class SaxoApiClient:
    """
    Client HTTP pour l'API Saxo OpenAPI.

    Gère:
    - Authentification Bearer
    - Gestion des erreurs HTTP
    - Rate limiting
    - Timeout

    Attributes:
        settings: Configuration de l'application
        api_url: URL de base de l'API
    """

    def __init__(self, settings: Settings):
        """
        Initialise le client API Saxo.

        Args:
            settings: Configuration de l'application
        """
        self.settings = settings
        self.api_url = settings.saxo_api_url

    # =========================================================================
    # PUBLIC METHODS
    # =========================================================================

    def get(
        self,
        access_token: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> SaxoApiResponse:
        """
        Effectue une requête GET.

        Args:
            access_token: Token d'accès Bearer
            endpoint: Endpoint API (ex: "/port/v1/clients/me")
            params: Paramètres de query string

        Returns:
            SaxoApiResponse avec les données

        Raises:
            BrokerApiError: En cas d'erreur API
            BrokerAuthenticationError: Si le token est invalide
            BrokerRateLimitError: Si rate limited
        """
        url = f"{self.api_url}{endpoint}"
        headers = self._get_headers(access_token)

        logger.debug(f"GET {endpoint}")

        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=API_TIMEOUT_SECONDS,
            )
            return self._handle_response(response, endpoint)

        except RequestException as e:
            logger.error(f"Network error on GET {endpoint}: {e}")
            raise BrokerApiError("saxo", f"Erreur réseau: {str(e)}")

    def post(
        self,
        access_token: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> SaxoApiResponse:
        """
        Effectue une requête POST.

        Args:
            access_token: Token d'accès Bearer
            endpoint: Endpoint API
            data: Données form-encoded
            json_data: Données JSON

        Returns:
            SaxoApiResponse avec les données

        Raises:
            BrokerApiError: En cas d'erreur API
        """
        url = f"{self.api_url}{endpoint}"
        headers = self._get_headers(access_token)

        logger.debug(f"POST {endpoint}")

        try:
            response = requests.post(
                url,
                headers=headers,
                data=data,
                json=json_data,
                timeout=API_TIMEOUT_SECONDS,
            )
            return self._handle_response(response, endpoint)

        except RequestException as e:
            logger.error(f"Network error on POST {endpoint}: {e}")
            raise BrokerApiError("saxo", f"Erreur réseau: {str(e)}")

    def delete(
        self,
        access_token: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> SaxoApiResponse:
        """
        Effectue une requête DELETE.

        Args:
            access_token: Token d'accès Bearer
            endpoint: Endpoint API
            params: Paramètres de query string

        Returns:
            SaxoApiResponse avec les données

        Raises:
            BrokerApiError: En cas d'erreur API
        """
        url = f"{self.api_url}{endpoint}"
        headers = self._get_headers(access_token)

        logger.debug(f"DELETE {endpoint}")

        try:
            response = requests.delete(
                url,
                headers=headers,
                params=params,
                timeout=API_TIMEOUT_SECONDS,
            )
            return self._handle_response(response, endpoint)

        except RequestException as e:
            logger.error(f"Network error on DELETE {endpoint}: {e}")
            raise BrokerApiError("saxo", f"Erreur réseau: {str(e)}")

    # =========================================================================
    # API ENDPOINTS - CLIENT
    # =========================================================================

    def get_client_info(self, access_token: str) -> Dict[str, Any]:
        """
        Récupère les informations du client.

        Args:
            access_token: Token d'accès

        Returns:
            Dict avec ClientKey, Name, etc.
        """
        response = self.get(access_token, "/port/v1/clients/me")
        return response.data

    def get_accounts(self, access_token: str, client_key: str) -> List[Dict[str, Any]]:
        """
        Récupère la liste des comptes.

        Args:
            access_token: Token d'accès
            client_key: Clé du client

        Returns:
            Liste des comptes
        """
        response = self.get(
            access_token,
            "/port/v1/accounts",
            params={"ClientKey": client_key},
        )
        return response.data.get("Data", [])

    # =========================================================================
    # API ENDPOINTS - PORTFOLIO
    # =========================================================================

    def get_positions(self, access_token: str, client_key: str) -> List[Dict[str, Any]]:
        """
        Récupère les positions avec tous les details (prix, P&L, symboles).

        Utilise /port/v1/positions/me qui retourne plus de details que /netpositions.

        Args:
            access_token: Token d'accès
            client_key: Clé du client

        Returns:
            Liste des positions avec prix, P&L, symboles, etc.
        """
        # FieldGroups pour /positions:
        # - PositionBase: Uic, Amount, AssetType, AccountId, OpenPrice
        # - PositionView: CurrentPrice, ProfitLossOnTrade, Exposure, MarketValue
        # - DisplayAndFormat: Symbol, Description, Currency
        response = self.get(
            access_token,
            "/port/v1/positions/me",
            params={
                "ClientKey": client_key,
                "FieldGroups": "PositionBase,PositionView,DisplayAndFormat",
            },
        )

        positions = response.data.get("Data", [])

        # Debug log
        if positions:
            logger.info(f"Saxo positions: {len(positions)} positions")
            logger.info(f"Sample position keys: {list(positions[0].keys())}")
            # Log complet pour debug
            import json
            logger.info(f"Sample position FULL: {json.dumps(positions[0], indent=2, default=str)}")
        else:
            logger.warning("Saxo positions: empty response")

        return positions

    def get_net_positions(self, access_token: str, client_key: str) -> List[Dict[str, Any]]:
        """
        Alias pour compatibilité - utilise get_positions().
        """
        return self.get_positions(access_token, client_key)

    def get_balances(self, access_token: str, client_key: str) -> Dict[str, Any]:
        """
        Récupère les soldes du compte.

        Args:
            access_token: Token d'accès
            client_key: Clé du client

        Returns:
            Dict avec les soldes
        """
        response = self.get(
            access_token,
            "/port/v1/balances",
            params={"ClientKey": client_key},
        )
        return response.data

    # =========================================================================
    # API ENDPOINTS - ORDERS
    # =========================================================================

    def get_orders(
        self,
        access_token: str,
        client_key: str,
        status: str = "All",
    ) -> List[Dict[str, Any]]:
        """
        Récupère les ordres.

        Args:
            access_token: Token d'accès
            client_key: Clé du client
            status: Filtre de statut (All, Working, Filled, Cancelled)

        Returns:
            Liste des ordres
        """
        response = self.get(
            access_token,
            "/port/v1/orders",
            params={"ClientKey": client_key, "Status": status},
        )
        return response.data.get("Data", [])

    def place_order(
        self,
        access_token: str,
        order_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Place un ordre.

        Args:
            access_token: Token d'accès
            order_data: Données de l'ordre

        Returns:
            Confirmation de l'ordre
        """
        response = self.post(
            access_token,
            "/trade/v2/orders",
            json_data=order_data,
        )
        return response.data

    def cancel_order(
        self,
        access_token: str,
        order_id: str,
        account_key: str,
    ) -> bool:
        """
        Annule un ordre.

        Args:
            access_token: Token d'accès
            order_id: ID de l'ordre
            account_key: Clé du compte

        Returns:
            True si succès
        """
        try:
            self.delete(
                access_token,
                f"/trade/v2/orders/{order_id}",
                params={"AccountKey": account_key},
            )
            return True
        except BrokerApiError:
            return False

    # =========================================================================
    # API ENDPOINTS - INSTRUMENTS
    # =========================================================================

    def search_instruments(
        self,
        access_token: str,
        keywords: str,
        asset_types: Optional[List[str]] = None,
        exchange_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Recherche des instruments.

        Supporte le format SYMBOL:EXCHANGE (ex: EVTG:xetr, VUSA:xmil).

        Args:
            access_token: Token d'accès
            keywords: Termes de recherche (peut contenir :exchange)
            asset_types: Types d'actifs à chercher
            exchange_id: ID de l'exchange (optionnel)

        Returns:
            Liste des instruments correspondants
        """
        if not asset_types:
            asset_types = ["Stock", "CfdOnStock", "Etf", "CfdOnEtf", "Fund", "CfdOnFund"]

        # Parser le format SYMBOL:EXCHANGE
        search_term = keywords
        detected_exchange = exchange_id

        if ":" in keywords:
            parts = keywords.split(":")
            search_term = parts[0].strip()
            exchange_hint = parts[1].strip().upper() if len(parts) > 1 else None

            # Mapper les suffixes courants aux ExchangeId Saxo
            exchange_mapping = {
                "XETR": "XETR",  # XETRA (Allemagne)
                "XMIL": "XMIL",  # Milan (Italie)
                "XPAR": "XPAR",  # Paris (France)
                "XLON": "XLON",  # London
                "XAMS": "XAMS",  # Amsterdam
                "XBRU": "XBRU",  # Brussels
                "XLIS": "XLIS",  # Lisbon
                "XMAD": "XMAD",  # Madrid
                "XSWX": "XSWX",  # Swiss
                "XNYS": "XNYS",  # NYSE
                "XNAS": "XNAS",  # NASDAQ
                "ARCX": "ARCX",  # NYSE Arca
                # Aliases courants
                "ETR": "XETR",
                "DE": "XETR",
                "MIL": "XMIL",
                "MI": "XMIL",
                "IT": "XMIL",
                "PA": "XPAR",
                "FR": "XPAR",
                "L": "XLON",
                "LON": "XLON",
                "AS": "XAMS",
                "SW": "XSWX",
                "US": "XNYS",
            }

            if exchange_hint and exchange_hint in exchange_mapping:
                detected_exchange = exchange_mapping[exchange_hint]
                logger.info(f"Detected exchange: {exchange_hint} -> {detected_exchange}")

        # Construire les parametres
        params = {
            "Keywords": search_term,
            "AssetTypes": ",".join(asset_types),
            "IncludeNonTradable": "false",
        }

        # Ajouter l'exchange si detecte
        if detected_exchange:
            params["ExchangeId"] = detected_exchange

        logger.info(f"Saxo search: keywords='{search_term}', exchange={detected_exchange}, types={asset_types}")

        response = self.get(
            access_token,
            "/ref/v1/instruments",
            params=params,
        )

        results = response.data.get("Data", [])

        # Si pas de resultats avec l'exchange specifique, essayer sans
        if not results and detected_exchange:
            logger.info(f"No results with exchange {detected_exchange}, trying without...")
            params.pop("ExchangeId", None)
            response = self.get(
                access_token,
                "/ref/v1/instruments",
                params=params,
            )
            results = response.data.get("Data", [])

        logger.info(f"Saxo search results: {len(results)} instruments found")
        return results

    def get_instrument_details(
        self,
        access_token: str,
        uic: int,
        asset_type: str = "Stock",
    ) -> Optional[Dict[str, Any]]:
        """
        Recupere les details d'un instrument par son UIC.

        Args:
            access_token: Token d'accès
            uic: Universal Instrument Code
            asset_type: Type d'actif

        Returns:
            Details de l'instrument ou None
        """
        try:
            response = self.get(
                access_token,
                f"/ref/v1/instruments/details/{uic}/{asset_type}",
            )
            return response.data
        except BrokerApiError:
            return None

    # =========================================================================
    # API ENDPOINTS - HISTORY
    # =========================================================================

    def get_trade_history(
        self,
        access_token: str,
        client_key: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Récupère l'historique des transactions.

        Args:
            access_token: Token d'accès
            client_key: Clé du client
            from_date: Date de début
            to_date: Date de fin

        Returns:
            Liste des transactions
        """
        if not from_date:
            from_date = datetime.now() - timedelta(days=30)
        if not to_date:
            to_date = datetime.now()

        try:
            response = self.get(
                access_token,
                f"/cs/v1/reports/trades/{client_key}",
                params={
                    "FromDate": from_date.strftime("%Y-%m-%d"),
                    "ToDate": to_date.strftime("%Y-%m-%d"),
                },
            )
            return response.data.get("Data", [])
        except BrokerApiError:
            logger.warning("Could not fetch trade history")
            return []

    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================

    def _get_headers(self, access_token: str) -> Dict[str, str]:
        """
        Construit les headers HTTP.

        Args:
            access_token: Token d'accès Bearer

        Returns:
            Dict des headers
        """
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def _handle_response(
        self,
        response: requests.Response,
        endpoint: str,
    ) -> SaxoApiResponse:
        """
        Traite une réponse HTTP.

        Args:
            response: Réponse HTTP
            endpoint: Endpoint appelé (pour logging)

        Returns:
            SaxoApiResponse

        Raises:
            BrokerAuthenticationError: Si 401
            BrokerRateLimitError: Si 429
            BrokerApiError: Pour autres erreurs
        """
        status = response.status_code

        # Succès
        if status in (200, 201, 204):
            data = response.json() if response.content else {}
            return SaxoApiResponse(
                data=data,
                status_code=status,
                headers=dict(response.headers),
            )

        # Authentification
        if status == 401:
            logger.error(f"Authentication failed on {endpoint}")
            raise BrokerAuthenticationError(
                "saxo",
                "Token d'accès invalide ou expiré"
            )

        # Rate limit
        if status == 429:
            retry_after = response.headers.get("Retry-After", "60")
            logger.warning(f"Rate limited on {endpoint}, retry after {retry_after}s")
            raise BrokerRateLimitError(
                "saxo",
                f"Trop de requêtes. Réessayez dans {retry_after} secondes."
            )

        # Conflit (ex: ordre invalide, paramètres manquants)
        if status == 409:
            error_msg = self._parse_error(response)
            logger.error(f"Conflict error on {endpoint}: {error_msg}")
            raise BrokerApiError("saxo", f"Ordre rejeté: {error_msg}")

        # Autres erreurs
        error_msg = self._parse_error(response)
        logger.error(f"API error on {endpoint}: {status} - {error_msg}")
        raise BrokerApiError("saxo", error_msg)

    def _parse_error(self, response: requests.Response) -> str:
        """
        Parse le message d'erreur d'une réponse.

        Args:
            response: Réponse HTTP avec erreur

        Returns:
            Message d'erreur lisible
        """
        try:
            data = response.json()
            if "Message" in data:
                return data["Message"]
            if "ErrorInfo" in data:
                return data["ErrorInfo"].get("Message", str(data))
            return str(data)
        except Exception:
            return f"HTTP {response.status_code}: {response.text[:200]}"


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_saxo_api_client(settings: Settings) -> SaxoApiClient:
    """
    Factory function pour créer un SaxoApiClient.

    Args:
        settings: Configuration de l'application

    Returns:
        Instance configurée de SaxoApiClient
    """
    return SaxoApiClient(settings)
