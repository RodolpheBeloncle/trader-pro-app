"""
Service de verification des alertes techniques.

Ce service detecte les signaux techniques pour les positions:
- RSI overbought/oversold
- MACD crossovers
- Support/Resistance breaks
- Bollinger Bands breakouts

UTILISATION:
    from src.application.services.technical_alert_service import TechnicalAlertService

    service = TechnicalAlertService()
    alerts = await service.check_portfolio_signals()
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from src.infrastructure.brokers.saxo.saxo_auth import get_saxo_auth
from src.infrastructure.brokers.saxo.saxo_api_client import SaxoApiClient
from src.config.settings import get_settings
from src.infrastructure.notifications.telegram_service import get_telegram_service
from src.infrastructure.providers.yahoo_finance_provider import YahooFinanceProvider
from src.domain.value_objects.ticker import Ticker

logger = logging.getLogger(__name__)


@dataclass
class TechnicalSignal:
    """Signal technique detecte."""
    ticker: str
    signal_type: str  # rsi_overbought, rsi_oversold, macd_bullish_crossover, etc.
    current_price: float
    indicator_value: float
    message: str
    severity: str  # low, medium, high


class TechnicalAlertService:
    """
    Service de detection des signaux techniques.

    Analyse les positions du portefeuille pour detecter
    des conditions techniques notables.
    """

    # Seuils par defaut
    RSI_OVERBOUGHT = 70
    RSI_OVERSOLD = 30
    BOLLINGER_THRESHOLD = 2.0

    def __init__(
        self,
        price_provider: Optional[YahooFinanceProvider] = None,
    ):
        """
        Initialise le service.

        Args:
            price_provider: Provider de prix. Par defaut: Yahoo Finance.
        """
        self._price_provider = price_provider or YahooFinanceProvider()
        self._telegram = get_telegram_service()
        self._last_signals: Dict[str, str] = {}  # Cache pour eviter doublons

    async def check_portfolio_signals(
        self,
        rsi_enabled: bool = True,
        rsi_overbought: int = 70,
        rsi_oversold: int = 30,
        macd_enabled: bool = True,
        bollinger_enabled: bool = True,
    ) -> List[TechnicalSignal]:
        """
        Verifie les signaux techniques pour le portefeuille Saxo.

        Args:
            rsi_enabled: Activer detection RSI
            rsi_overbought: Seuil RSI surachat
            rsi_oversold: Seuil RSI survente
            macd_enabled: Activer detection MACD
            bollinger_enabled: Activer detection Bollinger

        Returns:
            Liste des signaux detectes
        """
        # Stocker les parametres pour _analyze_position
        self._rsi_enabled = rsi_enabled
        self._rsi_overbought = rsi_overbought
        self._rsi_oversold = rsi_oversold
        self._macd_enabled = macd_enabled
        self._bollinger_enabled = bollinger_enabled

        signals = []

        try:
            # Utiliser le systeme d'auth Saxo existant
            auth = get_saxo_auth()
            token = auth.get_valid_token()

            # Verifier si authentifie
            if not token:
                logger.debug("Technical alerts: not authenticated, skipping")
                return signals

            # Creer le client API
            settings = get_settings()
            client = SaxoApiClient(settings)

            # Recuperer le client key
            client_info = client.get_client_info(token.access_token)
            client_key = client_info.get("ClientKey")

            if not client_key:
                logger.debug("Technical alerts: no client key")
                return signals

            # Recuperer les positions
            positions = client.get_positions(token.access_token, client_key)

            if not positions:
                logger.debug("Technical alerts: no positions")
                return signals

            # Analyser chaque position
            for position in positions:
                display = position.get("DisplayAndFormat", {})
                ticker = display.get("Symbol")

                if not ticker:
                    continue

                try:
                    position_signals = await self._analyze_position(ticker)
                    signals.extend(position_signals)
                except Exception as e:
                    logger.warning(f"Error analyzing {ticker}: {e}")

        except Exception as e:
            logger.exception(f"Error in technical alert check: {e}")

        return signals

    async def check_ticker_signals(self, ticker: str) -> List[TechnicalSignal]:
        """
        Verifie les signaux techniques pour un ticker specifique.

        Args:
            ticker: Symbole du ticker

        Returns:
            Liste des signaux detectes
        """
        return await self._analyze_position(ticker)

    async def _analyze_position(self, ticker_str: str) -> List[TechnicalSignal]:
        """
        Analyse une position pour detecter des signaux techniques.

        Args:
            ticker_str: Symbole du ticker (string)

        Returns:
            Liste des signaux pour cette position
        """
        signals = []

        try:
            # Convertir en objet Ticker
            ticker = Ticker(ticker_str)

            # Recuperer donnees historiques (30 jours)
            history = await self._price_provider.get_historical_data(
                ticker,
                days=30,
                interval="1d"
            )

            if history is None or len(history) < 14:
                logger.debug(f"Not enough data for {ticker_str}")
                return signals

            # Extraire les prix de cloture depuis List[HistoricalDataPoint]
            close_prices = [point.close for point in history]

            # Prix actuel (dernier prix de cloture)
            current_price = close_prices[-1]

            # Calculer RSI (si active)
            rsi_enabled = getattr(self, '_rsi_enabled', True)
            if rsi_enabled:
                rsi = self._calculate_rsi(close_prices)
                if rsi is not None:
                    rsi_signal = self._check_rsi_signal(ticker_str, current_price, rsi)
                    if rsi_signal:
                        signals.append(rsi_signal)

            # Calculer MACD (si active)
            macd_enabled = getattr(self, '_macd_enabled', True)
            if macd_enabled:
                macd_signal = self._check_macd_signal(ticker_str, current_price, close_prices)
                if macd_signal:
                    signals.append(macd_signal)

            # Calculer Bollinger Bands (si active)
            bollinger_enabled = getattr(self, '_bollinger_enabled', True)
            if bollinger_enabled:
                bb_signal = self._check_bollinger_signal(ticker_str, current_price, close_prices)
                if bb_signal:
                    signals.append(bb_signal)

        except Exception as e:
            logger.error(f"Error analyzing {ticker_str}: {e}")

        return signals

    def _calculate_rsi(self, prices, period: int = 14) -> Optional[float]:
        """
        Calcule le RSI.

        Args:
            prices: Array de prix
            period: Periode RSI

        Returns:
            Valeur RSI ou None
        """
        if len(prices) < period + 1:
            return None

        # Calculer les variations
        deltas = []
        for i in range(1, len(prices)):
            deltas.append(prices[i] - prices[i - 1])

        # Separer gains et pertes
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        # Moyenne mobile exponentielle
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _check_rsi_signal(
        self,
        ticker: str,
        current_price: float,
        rsi: float
    ) -> Optional[TechnicalSignal]:
        """
        Verifie les signaux RSI.

        Args:
            ticker: Symbole
            current_price: Prix actuel
            rsi: Valeur RSI

        Returns:
            Signal technique ou None
        """
        signal_key = f"{ticker}_rsi"

        # Utiliser les seuils configurables ou les valeurs par defaut
        rsi_overbought = getattr(self, '_rsi_overbought', self.RSI_OVERBOUGHT)
        rsi_oversold = getattr(self, '_rsi_oversold', self.RSI_OVERSOLD)

        if rsi >= rsi_overbought:
            signal_type = "rsi_overbought"
            message = f"RSI a {rsi:.1f} - Zone de surachat. Considerez prendre des profits."
            severity = "high" if rsi >= 80 else "medium"

            # Eviter doublons
            if self._last_signals.get(signal_key) == signal_type:
                return None
            self._last_signals[signal_key] = signal_type

            return TechnicalSignal(
                ticker=ticker,
                signal_type=signal_type,
                current_price=current_price,
                indicator_value=rsi,
                message=message,
                severity=severity,
            )

        elif rsi <= rsi_oversold:
            signal_type = "rsi_oversold"
            message = f"RSI a {rsi:.1f} - Zone de survente. Opportunite d'achat potentielle."
            severity = "high" if rsi <= 20 else "medium"

            if self._last_signals.get(signal_key) == signal_type:
                return None
            self._last_signals[signal_key] = signal_type

            return TechnicalSignal(
                ticker=ticker,
                signal_type=signal_type,
                current_price=current_price,
                indicator_value=rsi,
                message=message,
                severity=severity,
            )

        else:
            # Reset le cache si RSI revient a la normale
            self._last_signals.pop(signal_key, None)

        return None

    def _check_macd_signal(
        self,
        ticker: str,
        current_price: float,
        prices
    ) -> Optional[TechnicalSignal]:
        """
        Verifie les signaux MACD (crossovers).

        Args:
            ticker: Symbole
            current_price: Prix actuel
            prices: Array de prix

        Returns:
            Signal technique ou None
        """
        if len(prices) < 26:
            return None

        # Calculer EMA
        def ema(data, period):
            multiplier = 2 / (period + 1)
            ema_values = [data[0]]
            for i in range(1, len(data)):
                ema_values.append((data[i] * multiplier) + (ema_values[-1] * (1 - multiplier)))
            return ema_values

        ema12 = ema(prices, 12)
        ema26 = ema(prices, 26)

        # MACD line
        macd_line = [ema12[i] - ema26[i] for i in range(len(ema26))]

        # Signal line (EMA 9 du MACD)
        signal_line = ema(macd_line, 9)

        # Detecter crossover
        signal_key = f"{ticker}_macd"

        # Crossover haussier: MACD croise au-dessus de la signal line
        if len(macd_line) >= 2 and len(signal_line) >= 2:
            prev_diff = macd_line[-2] - signal_line[-2]
            curr_diff = macd_line[-1] - signal_line[-1]

            if prev_diff < 0 and curr_diff > 0:
                signal_type = "macd_bullish_crossover"
                message = "MACD crossover haussier. Signal d'achat potentiel."

                if self._last_signals.get(signal_key) == signal_type:
                    return None
                self._last_signals[signal_key] = signal_type

                return TechnicalSignal(
                    ticker=ticker,
                    signal_type=signal_type,
                    current_price=current_price,
                    indicator_value=macd_line[-1],
                    message=message,
                    severity="medium",
                )

            elif prev_diff > 0 and curr_diff < 0:
                signal_type = "macd_bearish_crossover"
                message = "MACD crossover baissier. Signal de vente potentiel."

                if self._last_signals.get(signal_key) == signal_type:
                    return None
                self._last_signals[signal_key] = signal_type

                return TechnicalSignal(
                    ticker=ticker,
                    signal_type=signal_type,
                    current_price=current_price,
                    indicator_value=macd_line[-1],
                    message=message,
                    severity="medium",
                )

        return None

    def _check_bollinger_signal(
        self,
        ticker: str,
        current_price: float,
        prices,
        period: int = 20
    ) -> Optional[TechnicalSignal]:
        """
        Verifie les signaux Bollinger Bands.

        Args:
            ticker: Symbole
            current_price: Prix actuel
            prices: Array de prix
            period: Periode Bollinger

        Returns:
            Signal technique ou None
        """
        if len(prices) < period:
            return None

        # Calculer SMA et ecart-type
        recent_prices = prices[-period:]
        sma = sum(recent_prices) / period
        variance = sum((p - sma) ** 2 for p in recent_prices) / period
        std = variance ** 0.5

        upper_band = sma + (self.BOLLINGER_THRESHOLD * std)
        lower_band = sma - (self.BOLLINGER_THRESHOLD * std)

        signal_key = f"{ticker}_bollinger"

        if current_price >= upper_band:
            signal_type = "bollinger_upper_break"
            message = f"Prix au-dessus de la bande superieure ({upper_band:.2f}). Surachat potentiel."

            if self._last_signals.get(signal_key) == signal_type:
                return None
            self._last_signals[signal_key] = signal_type

            return TechnicalSignal(
                ticker=ticker,
                signal_type=signal_type,
                current_price=current_price,
                indicator_value=upper_band,
                message=message,
                severity="medium",
            )

        elif current_price <= lower_band:
            signal_type = "bollinger_lower_break"
            message = f"Prix sous la bande inferieure ({lower_band:.2f}). Survente potentielle."

            if self._last_signals.get(signal_key) == signal_type:
                return None
            self._last_signals[signal_key] = signal_type

            return TechnicalSignal(
                ticker=ticker,
                signal_type=signal_type,
                current_price=current_price,
                indicator_value=lower_band,
                message=message,
                severity="medium",
            )

        else:
            self._last_signals.pop(signal_key, None)

        return None

    async def notify_signals(self, signals: List[TechnicalSignal]) -> int:
        """
        Envoie des notifications Telegram pour les signaux.

        Args:
            signals: Liste des signaux a notifier

        Returns:
            Nombre de notifications envoyees
        """
        if not self._telegram.is_configured:
            logger.debug("Telegram not configured, skipping notifications")
            return 0

        sent_count = 0

        for signal in signals:
            try:
                success = await self._telegram.send_technical_alert(
                    ticker=signal.ticker,
                    alert_type=signal.signal_type,
                    current_price=signal.current_price,
                    indicator_value=signal.indicator_value,
                    message_detail=signal.message,
                )
                if success:
                    sent_count += 1
                    logger.info(f"Technical alert sent: {signal.ticker} - {signal.signal_type}")
            except Exception as e:
                logger.error(f"Error sending technical alert: {e}")

        return sent_count

    def reset_signal_cache(self) -> None:
        """Reset le cache des signaux (utile pour les tests)."""
        self._last_signals.clear()
        logger.info("Technical signal cache cleared")


# Singleton
_technical_alert_service: Optional[TechnicalAlertService] = None


def get_technical_alert_service() -> TechnicalAlertService:
    """
    Retourne l'instance singleton du service.

    Returns:
        TechnicalAlertService initialise
    """
    global _technical_alert_service
    if _technical_alert_service is None:
        _technical_alert_service = TechnicalAlertService()
    return _technical_alert_service
