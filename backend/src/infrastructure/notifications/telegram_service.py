"""
Service d'envoi de notifications via Telegram Bot API.

Ce module gère l'envoi de messages via un bot Telegram.
Utilisé principalement pour les alertes de prix.

CONFIGURATION:
    TELEGRAM_BOT_TOKEN: Token du bot (obtenu via @BotFather)
    TELEGRAM_CHAT_ID: ID du chat pour recevoir les messages

UTILISATION:
    from src.infrastructure.notifications.telegram_service import get_telegram_service

    telegram = get_telegram_service()
    await telegram.send_message("Hello World!")
"""

import logging
from typing import Optional
import httpx

from src.config.settings import settings

logger = logging.getLogger(__name__)


class TelegramService:
    """
    Service d'envoi de messages Telegram.

    Utilise l'API Bot Telegram pour envoyer des messages.
    Supporte le formatage HTML et les boutons inline.
    """

    BASE_URL = "https://api.telegram.org/bot{token}"

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        timeout: float = 30.0
    ):
        """
        Initialise le service Telegram.

        Args:
            bot_token: Token du bot. Par défaut depuis settings.
            chat_id: ID du chat. Par défaut depuis settings.
            timeout: Timeout des requêtes HTTP.
        """
        self._bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN
        self._chat_id = chat_id or settings.TELEGRAM_CHAT_ID
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_configured(self) -> bool:
        """Vérifie si le service est configuré."""
        return bool(self._bot_token and self._chat_id)

    @property
    def api_url(self) -> str:
        """Retourne l'URL de base de l'API."""
        return self.BASE_URL.format(token=self._bot_token)

    async def _get_client(self) -> httpx.AsyncClient:
        """Retourne le client HTTP (singleton)."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        """Ferme le client HTTP."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def send_message(
        self,
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "HTML",
        disable_notification: bool = False,
        disable_web_page_preview: bool = True,
    ) -> bool:
        """
        Envoie un message texte.

        Args:
            text: Contenu du message (peut contenir du HTML)
            chat_id: ID du chat. Par défaut depuis config.
            parse_mode: Mode de parsing (HTML, Markdown, MarkdownV2)
            disable_notification: Envoyer sans notification
            disable_web_page_preview: Désactiver les aperçus de liens

        Returns:
            True si le message a été envoyé avec succès
        """
        if not self.is_configured:
            logger.warning("Telegram not configured, skipping message")
            return False

        target_chat = chat_id or self._chat_id

        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.api_url}/sendMessage",
                json={
                    "chat_id": target_chat,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_notification": disable_notification,
                    "disable_web_page_preview": disable_web_page_preview,
                }
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    logger.debug(f"Telegram message sent to {target_chat}")
                    return True
                else:
                    logger.error(f"Telegram API error: {data.get('description')}")
                    return False
            else:
                logger.error(f"Telegram HTTP error: {response.status_code}")
                return False

        except httpx.TimeoutException:
            logger.error("Telegram request timeout")
            return False
        except httpx.RequestError as e:
            logger.error(f"Telegram request error: {e}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error sending Telegram message: {e}")
            return False

    async def send_alert(
        self,
        ticker: str,
        alert_type: str,
        current_price: float,
        target_value: float,
        notes: Optional[str] = None,
    ) -> bool:
        """
        Envoie une alerte de prix formatée.

        Args:
            ticker: Symbole du ticker
            alert_type: Type d'alerte (price_above, price_below, percent_change)
            current_price: Prix actuel
            target_value: Valeur cible
            notes: Notes supplémentaires

        Returns:
            True si l'alerte a été envoyée
        """
        # Emoji selon le type
        if alert_type == "price_above":
            emoji = "📈"
            condition = f"au-dessus de <b>{target_value:.2f}</b>"
        elif alert_type == "price_below":
            emoji = "📉"
            condition = f"en-dessous de <b>{target_value:.2f}</b>"
        else:
            emoji = "📊"
            condition = f"variation de <b>{target_value:.1f}%</b> atteinte"

        message = (
            f"{emoji} <b>ALERTE: {ticker}</b>\n\n"
            f"💰 Prix actuel: <code>{current_price:.2f}</code>\n"
            f"🎯 Condition: {condition}\n"
        )

        if notes:
            message += f"\n📝 <i>{notes}</i>"

        message += "\n\n⏰ <i>Stock Analyzer</i>"

        return await self.send_message(message)

    async def send_trade_opened(
        self,
        ticker: str,
        direction: str,
        entry_price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        position_size: Optional[int] = None,
    ) -> bool:
        """
        Envoie une notification d'ouverture de trade.

        Args:
            ticker: Symbole du ticker
            direction: Direction (long/short)
            entry_price: Prix d'entrée
            stop_loss: Stop loss
            take_profit: Take profit
            position_size: Taille de position

        Returns:
            True si la notification a été envoyée
        """
        emoji = "🟢" if direction == "long" else "🔴"
        direction_text = "LONG" if direction == "long" else "SHORT"

        message = (
            f"{emoji} <b>TRADE OUVERT: {ticker}</b>\n\n"
            f"📊 Direction: <b>{direction_text}</b>\n"
            f"💰 Entrée: <code>{entry_price:.2f}</code>\n"
        )

        if stop_loss:
            message += f"🛑 Stop Loss: <code>{stop_loss:.2f}</code>\n"
        if take_profit:
            message += f"🎯 Take Profit: <code>{take_profit:.2f}</code>\n"
        if position_size:
            message += f"📦 Position: <code>{position_size}</code>\n"

        message += "\n⏰ <i>Stock Analyzer</i>"

        return await self.send_message(message)

    async def send_trade_closed(
        self,
        ticker: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_percent: float,
    ) -> bool:
        """
        Envoie une notification de clôture de trade.

        Args:
            ticker: Symbole du ticker
            direction: Direction (long/short)
            entry_price: Prix d'entrée
            exit_price: Prix de sortie
            pnl: P&L en valeur
            pnl_percent: P&L en pourcentage

        Returns:
            True si la notification a été envoyée
        """
        is_win = pnl > 0
        emoji = "✅" if is_win else "❌"
        result = "GAIN" if is_win else "PERTE"
        pnl_emoji = "💚" if is_win else "💔"

        message = (
            f"{emoji} <b>TRADE FERMÉ: {ticker}</b>\n\n"
            f"📊 Direction: <b>{direction.upper()}</b>\n"
            f"📥 Entrée: <code>{entry_price:.2f}</code>\n"
            f"📤 Sortie: <code>{exit_price:.2f}</code>\n\n"
            f"{pnl_emoji} <b>Résultat: {result}</b>\n"
            f"💰 P&L: <code>{pnl:+.2f}</code> ({pnl_percent:+.2f}%)\n"
        )

        message += "\n⏰ <i>Stock Analyzer</i>"

        return await self.send_message(message)

    async def send_daily_summary(
        self,
        total_trades: int,
        winning_trades: int,
        total_pnl: float,
        best_trade: Optional[str] = None,
        worst_trade: Optional[str] = None,
    ) -> bool:
        """
        Envoie un résumé journalier.

        Args:
            total_trades: Nombre de trades
            winning_trades: Nombre de trades gagnants
            total_pnl: P&L total
            best_trade: Meilleur trade du jour
            worst_trade: Pire trade du jour

        Returns:
            True si le résumé a été envoyé
        """
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        pnl_emoji = "📈" if total_pnl >= 0 else "📉"

        message = (
            f"📊 <b>RÉSUMÉ JOURNALIER</b>\n\n"
            f"🔢 Trades: <b>{total_trades}</b>\n"
            f"✅ Gagnants: <b>{winning_trades}</b> ({win_rate:.1f}%)\n"
            f"{pnl_emoji} P&L Total: <code>{total_pnl:+.2f}</code>\n"
        )

        if best_trade:
            message += f"\n🏆 Meilleur: {best_trade}"
        if worst_trade:
            message += f"\n😢 Pire: {worst_trade}"

        message += "\n\n⏰ <i>Stock Analyzer</i>"

        return await self.send_message(message)

    async def test_connection(self) -> bool:
        """
        Teste la connexion au bot Telegram.

        Returns:
            True si la connexion fonctionne
        """
        if not self.is_configured:
            return False

        try:
            client = await self._get_client()
            response = await client.get(f"{self.api_url}/getMe")

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    bot_name = data.get("result", {}).get("username", "Unknown")
                    logger.info(f"Telegram bot connected: @{bot_name}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Telegram connection test failed: {e}")
            return False

    # =========================================================================
    # NOUVELLES METHODES AVANCEES
    # =========================================================================

    async def send_stop_loss_alert(
        self,
        ticker: str,
        current_price: float,
        stop_loss_price: float,
        entry_price: float,
        pnl_percent: float,
    ) -> bool:
        """
        Envoie une alerte stop loss atteint.

        Args:
            ticker: Symbole du ticker
            current_price: Prix actuel
            stop_loss_price: Niveau du stop loss
            entry_price: Prix d'entree
            pnl_percent: P&L en pourcentage

        Returns:
            True si l'alerte a ete envoyee
        """
        emoji = "🛑" if pnl_percent < 0 else "⚠️"

        message = (
            f"{emoji} <b>STOP LOSS ATTEINT: {ticker}</b>\n\n"
            f"💰 Prix actuel: <code>{current_price:.2f}</code>\n"
            f"🛑 Stop Loss: <code>{stop_loss_price:.2f}</code>\n"
            f"📥 Prix d'entree: <code>{entry_price:.2f}</code>\n"
            f"📉 P&L: <code>{pnl_percent:+.2f}%</code>\n\n"
            f"⚡ <b>ACTION RECOMMANDEE: VENDRE</b>\n"
            f"Coupez vos pertes pour preserver votre capital.\n\n"
            f"⏰ <i>Stock Analyzer</i>"
        )

        return await self.send_message(message)

    async def send_take_profit_alert(
        self,
        ticker: str,
        current_price: float,
        take_profit_price: float,
        entry_price: float,
        pnl_percent: float,
    ) -> bool:
        """
        Envoie une alerte take profit atteint.

        Args:
            ticker: Symbole du ticker
            current_price: Prix actuel
            take_profit_price: Niveau du take profit
            entry_price: Prix d'entree
            pnl_percent: P&L en pourcentage

        Returns:
            True si l'alerte a ete envoyee
        """
        message = (
            f"🎯 <b>TAKE PROFIT ATTEINT: {ticker}</b>\n\n"
            f"💰 Prix actuel: <code>{current_price:.2f}</code>\n"
            f"🎯 Take Profit: <code>{take_profit_price:.2f}</code>\n"
            f"📥 Prix d'entree: <code>{entry_price:.2f}</code>\n"
            f"📈 P&L: <code>{pnl_percent:+.2f}%</code>\n\n"
            f"⚡ <b>ACTION RECOMMANDEE: PRENDRE PROFITS</b>\n"
            f"Considerez de vendre ou de remonter votre stop.\n\n"
            f"⏰ <i>Stock Analyzer</i>"
        )

        return await self.send_message(message)

    async def send_buy_signal(
        self,
        ticker: str,
        current_price: float,
        signal_reason: str,
        suggested_entry: float,
        suggested_stop: float,
        suggested_target: float,
        confidence: float,
    ) -> bool:
        """
        Envoie un signal d'achat.

        Args:
            ticker: Symbole du ticker
            current_price: Prix actuel
            signal_reason: Raison du signal
            suggested_entry: Prix d'entree suggere
            suggested_stop: Stop loss suggere
            suggested_target: Target suggere
            confidence: Niveau de confiance (0-100)

        Returns:
            True si le signal a ete envoye
        """
        confidence_emoji = "🟢" if confidence > 70 else "🟡" if confidence > 50 else "🟠"

        message = (
            f"📈 <b>SIGNAL D'ACHAT: {ticker}</b>\n\n"
            f"{confidence_emoji} Confiance: <code>{confidence:.0f}%</code>\n"
            f"📊 Raison: {signal_reason}\n\n"
            f"💰 Prix actuel: <code>{current_price:.2f}</code>\n"
            f"📥 Entree suggeree: <code>{suggested_entry:.2f}</code>\n"
            f"🛑 Stop Loss: <code>{suggested_stop:.2f}</code>\n"
            f"🎯 Target: <code>{suggested_target:.2f}</code>\n\n"
            f"⚠️ <i>Faites toujours votre propre analyse</i>\n\n"
            f"⏰ <i>Stock Analyzer</i>"
        )

        return await self.send_message(message)

    async def send_portfolio_daily_summary(
        self,
        total_value: float,
        daily_pnl: float,
        daily_pnl_percent: float,
        positions_count: int,
        alerts_triggered: int,
        top_gainers: list = None,
        top_losers: list = None,
    ) -> bool:
        """
        Envoie le resume journalier du portefeuille.

        Args:
            total_value: Valeur totale du portefeuille
            daily_pnl: P&L du jour en valeur
            daily_pnl_percent: P&L du jour en pourcentage
            positions_count: Nombre de positions
            alerts_triggered: Nombre d'alertes declenchees
            top_gainers: Top gagnants [(symbol, pct), ...]
            top_losers: Top perdants [(symbol, pct), ...]

        Returns:
            True si le resume a ete envoye
        """
        pnl_emoji = "📈" if daily_pnl >= 0 else "📉"

        message = (
            f"📊 <b>RESUME PORTEFEUILLE JOURNALIER</b>\n\n"
            f"💼 Valeur totale: <code>{total_value:,.2f}€</code>\n"
            f"{pnl_emoji} P&L du jour: <code>{daily_pnl:+,.2f}€</code> ({daily_pnl_percent:+.2f}%)\n"
            f"📦 Positions: <code>{positions_count}</code>\n"
            f"🔔 Alertes declenchees: <code>{alerts_triggered}</code>\n\n"
        )

        if top_gainers:
            message += "<b>🏆 Top Gagnants:</b>\n"
            for symbol, pct in top_gainers[:3]:
                message += f"  • {symbol}: <code>{pct:+.2f}%</code>\n"
            message += "\n"

        if top_losers:
            message += "<b>😢 Top Perdants:</b>\n"
            for symbol, pct in top_losers[:3]:
                message += f"  • {symbol}: <code>{pct:+.2f}%</code>\n"
            message += "\n"

        message += "⏰ <i>Stock Analyzer</i>"

        return await self.send_message(message)

    async def send_position_recommendation(
        self,
        ticker: str,
        action: str,
        current_price: float,
        confidence: float,
        reasons: list,
        entry_price: float = None,
        stop_loss: float = None,
        target: float = None,
    ) -> bool:
        """
        Envoie une recommandation sur une position.

        Args:
            ticker: Symbole du ticker
            action: Action recommandee (BUY, SELL, HOLD, ADD, REDUCE)
            current_price: Prix actuel
            confidence: Niveau de confiance (0-100)
            reasons: Liste des raisons
            entry_price: Prix d'entree suggere
            stop_loss: Stop loss suggere
            target: Target suggere

        Returns:
            True si la recommandation a ete envoyee
        """
        action_emoji = {
            "BUY": "🟢",
            "SELL": "🔴",
            "HOLD": "🟡",
            "ADD": "💚",
            "REDUCE": "💔",
        }.get(action, "📊")

        message = (
            f"{action_emoji} <b>RECOMMANDATION: {action} {ticker}</b>\n\n"
            f"💰 Prix actuel: <code>{current_price:.2f}</code>\n"
            f"📊 Confiance: <code>{confidence:.0f}%</code>\n\n"
            f"<b>Raisons:</b>\n"
        )

        for reason in reasons[:5]:
            message += f"  • {reason}\n"

        if action in ("BUY", "ADD") and entry_price and stop_loss and target:
            message += (
                f"\n<b>Setup suggere:</b>\n"
                f"📥 Entree: <code>{entry_price:.2f}</code>\n"
                f"🛑 Stop: <code>{stop_loss:.2f}</code>\n"
                f"🎯 Target: <code>{target:.2f}</code>\n"
            )

        message += "\n⏰ <i>Stock Analyzer</i>"

        return await self.send_message(message)

    async def send_technical_alert(
        self,
        ticker: str,
        alert_type: str,
        current_price: float,
        indicator_value: float,
        message_detail: str,
    ) -> bool:
        """
        Envoie une alerte technique (RSI, MACD, etc.).

        Args:
            ticker: Symbole du ticker
            alert_type: Type d'alerte (rsi_overbought, macd_crossover, etc.)
            current_price: Prix actuel
            indicator_value: Valeur de l'indicateur
            message_detail: Detail du message

        Returns:
            True si l'alerte a ete envoyee
        """
        emoji_map = {
            "rsi_overbought": "🔥",
            "rsi_oversold": "❄️",
            "macd_bullish_crossover": "📈",
            "macd_bearish_crossover": "📉",
            "support_break": "⬇️",
            "resistance_break": "⬆️",
        }
        emoji = emoji_map.get(alert_type, "📊")

        alert_name = alert_type.replace("_", " ").upper()

        message = (
            f"{emoji} <b>ALERTE TECHNIQUE: {ticker}</b>\n\n"
            f"📌 Type: <b>{alert_name}</b>\n"
            f"💰 Prix: <code>{current_price:.2f}</code>\n"
            f"📊 Indicateur: <code>{indicator_value:.2f}</code>\n\n"
            f"📝 {message_detail}\n\n"
            f"⏰ <i>Stock Analyzer</i>"
        )

        return await self.send_message(message)


# Singleton
_telegram_service: Optional[TelegramService] = None


def get_telegram_service() -> TelegramService:
    """
    Retourne l'instance singleton du service Telegram.

    Returns:
        TelegramService initialisé
    """
    global _telegram_service
    if _telegram_service is None:
        _telegram_service = TelegramService()
    return _telegram_service
