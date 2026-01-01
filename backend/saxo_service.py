"""
Saxo OpenAPI Service

Service pour interagir avec l'API Saxo Bank:
- Authentification OAuth2
- Récupération du portefeuille
- Gestion des ordres
- Historique des transactions

Documentation: https://www.developer.saxo/openapi/learn
"""

import requests
import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from urllib.parse import urlencode
import base64
import hashlib
import secrets

from saxo_config import (
    SAXO_APP_KEY, SAXO_APP_SECRET, SAXO_REDIRECT_URI, SAXO_SCOPES,
    get_auth_url, get_api_url, is_configured
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SaxoService:
    """
    Service pour l'API Saxo OpenAPI.

    Utilisation:
        service = SaxoService()
        auth_url = service.get_authorization_url()
        # User se connecte...
        tokens = service.exchange_code(authorization_code)
        portfolio = service.get_portfolio(tokens['access_token'])
    """

    def __init__(self):
        self.auth_url = get_auth_url()
        self.api_url = get_api_url()
        self.app_key = SAXO_APP_KEY
        self.app_secret = SAXO_APP_SECRET
        self.redirect_uri = SAXO_REDIRECT_URI
        self.scopes = SAXO_SCOPES

        # Token storage (en production, utiliser Redis/DB)
        self._tokens = {}

        # PKCE storage
        self._code_verifier = None

    # =========================================================================
    # AUTHENTICATION
    # =========================================================================

    def _generate_pkce(self):
        """Génère code_verifier et code_challenge pour PKCE."""
        # Générer un code_verifier aléatoire (43-128 caractères)
        self._code_verifier = secrets.token_urlsafe(32)

        # Créer le code_challenge (SHA256 hash, base64url encoded)
        code_challenge = hashlib.sha256(self._code_verifier.encode()).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).rstrip(b'=').decode()

        return code_challenge

    def get_authorization_url(self, state: str = "default") -> str:
        """
        Génère l'URL d'autorisation OAuth2 standard (sans PKCE).

        L'utilisateur doit être redirigé vers cette URL pour se connecter.

        Args:
            state: État pour la sécurité CSRF

        Returns:
            URL d'autorisation complète
        """
        if not is_configured():
            raise ValueError("Saxo API non configurée. Définissez SAXO_APP_KEY et SAXO_APP_SECRET.")

        params = {
            "response_type": "code",
            "client_id": self.app_key,
            "redirect_uri": self.redirect_uri,
            "state": state
        }

        logger.info(f"Auth URL generated (no PKCE)")
        return f"{self.auth_url}/authorize?{urlencode(params)}"

    def exchange_code(self, authorization_code: str) -> Dict:
        """
        Échange le code d'autorisation contre des tokens d'accès.

        Args:
            authorization_code: Code reçu après la connexion

        Returns:
            Dict avec access_token, refresh_token, expires_in
        """
        token_url = f"{self.auth_url}/token"

        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        # Standard Authorization Code flow avec client_secret dans body
        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.app_key,
            "client_secret": self.app_secret
        }

        logger.info(f"Exchanging code at {token_url}")
        logger.info(f"Redirect URI: {self.redirect_uri}")
        logger.info(f"Client ID: {self.app_key[:8]}...")

        response = requests.post(token_url, headers=headers, data=data)

        logger.info(f"Token response status: {response.status_code}")

        # Log response pour debug
        logger.info(f"Full response: {response.text}")

        if response.status_code != 200:
            # Check if JSON error
            try:
                error_json = response.json()
                logger.error(f"OAuth Error: {error_json}")
                raise Exception(f"Saxo OAuth Error: {error_json.get('error_description', error_json)}")
            except Exception as e:
                logger.error(f"Token exchange failed ({response.status_code}): {response.text}")
                raise Exception(f"Échec de l'authentification Saxo: {response.status_code}")

        tokens = response.json()
        self._tokens = {
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token"),
            "expires_at": datetime.now() + timedelta(seconds=tokens.get("expires_in", 3600))
        }

        logger.info("Saxo authentication successful")
        return self._tokens

    def refresh_token(self, refresh_token: str) -> Dict:
        """Rafraîchit le token d'accès."""
        token_url = f"{self.auth_url}/token"

        credentials = base64.b64encode(
            f"{self.app_key}:{self.app_secret}".encode()
        ).decode()

        headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }

        response = requests.post(token_url, headers=headers, data=data)

        if response.status_code != 200:
            raise Exception("Token refresh failed")

        tokens = response.json()
        self._tokens = {
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token", refresh_token),
            "expires_at": datetime.now() + timedelta(seconds=tokens.get("expires_in", 3600))
        }

        return self._tokens

    def _get_headers(self, access_token: str) -> Dict:
        """Retourne les headers pour les appels API."""
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

    # =========================================================================
    # ACCOUNT & CLIENT INFO
    # =========================================================================

    def get_client_info(self, access_token: str) -> Dict:
        """
        Récupère les informations du client.

        Returns:
            Infos client (ClientKey, Name, etc.)
        """
        url = f"{self.api_url}/port/v1/clients/me"

        response = requests.get(url, headers=self._get_headers(access_token))

        if response.status_code != 200:
            logger.error(f"Get client info failed: {response.text}")
            raise Exception("Impossible de récupérer les infos client")

        return response.json()

    def get_accounts(self, access_token: str) -> List[Dict]:
        """
        Récupère la liste des comptes.

        Returns:
            Liste des comptes avec leurs détails
        """
        # D'abord récupérer le ClientKey
        client = self.get_client_info(access_token)
        client_key = client.get("ClientKey")

        url = f"{self.api_url}/port/v1/accounts?ClientKey={client_key}"

        response = requests.get(url, headers=self._get_headers(access_token))

        if response.status_code != 200:
            raise Exception("Impossible de récupérer les comptes")

        return response.json().get("Data", [])

    # =========================================================================
    # PORTFOLIO & POSITIONS
    # =========================================================================

    def get_portfolio(self, access_token: str) -> Dict:
        """
        Récupère le portefeuille complet avec toutes les positions.

        Returns:
            Dict avec les positions, valeur totale, P&L, etc.
        """
        client = self.get_client_info(access_token)
        client_key = client.get("ClientKey")

        # Récupérer les positions nettes
        url = f"{self.api_url}/port/v1/netpositions?ClientKey={client_key}"

        response = requests.get(url, headers=self._get_headers(access_token))

        if response.status_code != 200:
            logger.error(f"Get portfolio failed: {response.text}")
            raise Exception("Impossible de récupérer le portefeuille")

        positions_data = response.json()

        # Récupérer le solde du compte
        balance_url = f"{self.api_url}/port/v1/balances?ClientKey={client_key}"
        balance_response = requests.get(balance_url, headers=self._get_headers(access_token))

        balance_data = {}
        if balance_response.status_code == 200:
            balance_data = balance_response.json()

        return {
            "positions": positions_data.get("Data", []),
            "count": positions_data.get("__count", 0),
            "balance": balance_data,
            "updated_at": datetime.now().isoformat()
        }

    def get_positions_with_details(self, access_token: str) -> List[Dict]:
        """
        Récupère les positions avec plus de détails pour l'analyse.

        Returns:
            Liste de positions enrichies avec:
            - Ticker symbol
            - Quantité
            - Prix d'achat
            - Prix actuel
            - P&L
            - % change
        """
        portfolio = self.get_portfolio(access_token)
        positions = []

        for pos in portfolio.get("positions", []):
            position_detail = {
                "ticker": pos.get("NetPositionBase", {}).get("AssetType", ""),
                "symbol": pos.get("DisplayAndFormat", {}).get("Symbol", ""),
                "description": pos.get("DisplayAndFormat", {}).get("Description", ""),
                "quantity": pos.get("NetPositionView", {}).get("PositionCount", 0),
                "current_price": pos.get("NetPositionView", {}).get("CurrentPrice", 0),
                "average_price": pos.get("NetPositionView", {}).get("AverageOpenPrice", 0),
                "market_value": pos.get("NetPositionView", {}).get("MarketValue", 0),
                "pnl": pos.get("NetPositionView", {}).get("ProfitLossOnTrade", 0),
                "pnl_percent": pos.get("NetPositionView", {}).get("ProfitLossOnTradeInPercentage", 0),
                "currency": pos.get("DisplayAndFormat", {}).get("Currency", "USD"),
                "asset_type": pos.get("NetPositionBase", {}).get("AssetType", ""),
                "uic": pos.get("NetPositionBase", {}).get("Uic"),  # Universal Instrument Code for trading
            }
            positions.append(position_detail)

        return positions

    # =========================================================================
    # ORDERS
    # =========================================================================

    def get_orders(self, access_token: str, status: str = "All") -> List[Dict]:
        """
        Récupère la liste des ordres.

        Args:
            status: "All", "Working", "Filled", "Cancelled"

        Returns:
            Liste des ordres
        """
        client = self.get_client_info(access_token)
        client_key = client.get("ClientKey")

        url = f"{self.api_url}/port/v1/orders?ClientKey={client_key}&Status={status}"

        response = requests.get(url, headers=self._get_headers(access_token))

        if response.status_code != 200:
            raise Exception("Impossible de récupérer les ordres")

        return response.json().get("Data", [])

    def place_order(
        self,
        access_token: str,
        account_key: str,
        symbol: str,
        asset_type: str,
        quantity: int,
        order_type: str = "Market",
        buy_sell: str = "Buy",
        price: float = None
    ) -> Dict:
        """
        Place un ordre d'achat ou de vente.

        Args:
            account_key: Clé du compte
            symbol: Symbole de l'instrument (ex: "AAPL:xnas")
            asset_type: Type d'actif ("Stock", "CfdOnStock", etc.)
            quantity: Quantité
            order_type: "Market", "Limit", "Stop"
            buy_sell: "Buy" ou "Sell"
            price: Prix limite (requis pour Limit orders)

        Returns:
            Confirmation de l'ordre
        """
        url = f"{self.api_url}/trade/v2/orders"

        order_data = {
            "AccountKey": account_key,
            "AssetType": asset_type,
            "BuySell": buy_sell,
            "Amount": quantity,
            "OrderType": order_type,
            "Uic": symbol,  # Universal Instrument Code
            "OrderDuration": {"DurationType": "DayOrder"},
            "ManualOrder": True  # Required by Saxo SIM/LIVE platform
        }

        if order_type == "Limit" and price:
            order_data["OrderPrice"] = price

        response = requests.post(
            url,
            headers=self._get_headers(access_token),
            json=order_data
        )

        if response.status_code not in [200, 201]:
            logger.error(f"Order placement failed: {response.text}")
            raise Exception(f"Échec de l'ordre: {response.text}")

        return response.json()

    def cancel_order(self, access_token: str, order_id: str, account_key: str) -> bool:
        """Annule un ordre en attente."""
        url = f"{self.api_url}/trade/v2/orders/{order_id}?AccountKey={account_key}"

        response = requests.delete(url, headers=self._get_headers(access_token))

        return response.status_code in [200, 204]

    # =========================================================================
    # HISTORY
    # =========================================================================

    def get_transactions_history(
        self,
        access_token: str,
        from_date: datetime = None,
        to_date: datetime = None
    ) -> List[Dict]:
        """
        Récupère l'historique des transactions.

        Args:
            from_date: Date de début (défaut: 30 jours)
            to_date: Date de fin (défaut: aujourd'hui)

        Returns:
            Liste des transactions
        """
        client = self.get_client_info(access_token)
        client_key = client.get("ClientKey")

        if not from_date:
            from_date = datetime.now() - timedelta(days=30)
        if not to_date:
            to_date = datetime.now()

        url = (
            f"{self.api_url}/cs/v1/reports/trades/{client_key}"
            f"?FromDate={from_date.strftime('%Y-%m-%d')}"
            f"&ToDate={to_date.strftime('%Y-%m-%d')}"
        )

        response = requests.get(url, headers=self._get_headers(access_token))

        if response.status_code != 200:
            logger.warning(f"Get history failed: {response.text}")
            return []

        return response.json().get("Data", [])

    # =========================================================================
    # INSTRUMENT SEARCH
    # =========================================================================

    def search_instrument(
        self,
        access_token: str,
        query: str,
        asset_types: List[str] = None
    ) -> List[Dict]:
        """
        Recherche un instrument par nom ou symbole.

        Args:
            query: Terme de recherche (ex: "AAPL", "Apple")
            asset_types: Types d'actifs à chercher

        Returns:
            Liste d'instruments correspondants
        """
        if not asset_types:
            asset_types = ["Stock", "CfdOnStock", "Etf", "CfdOnEtf"]

        url = (
            f"{self.api_url}/ref/v1/instruments"
            f"?Keywords={query}"
            f"&AssetTypes={','.join(asset_types)}"
        )

        response = requests.get(url, headers=self._get_headers(access_token))

        if response.status_code != 200:
            return []

        return response.json().get("Data", [])


# Instance globale du service
saxo_service = SaxoService()
