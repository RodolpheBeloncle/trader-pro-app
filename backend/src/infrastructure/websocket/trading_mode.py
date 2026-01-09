"""
Configuration des modes de trading.

Definit les differents modes de trading avec leurs parametres
de rafraichissement et sources de donnees.

MODES:
- LONG_TERM: Polling 60s, Yahoo Finance (economique, peu de requetes)
- SWING: Polling 10s, Yahoo/Finnhub (trading journalier)
- SCALPING: WebSocket temps reel, Finnhub/Saxo (intraday actif)
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, List


class TradingMode(str, Enum):
    """Modes de trading disponibles."""
    LONG_TERM = "long_term"   # Investissement long terme
    SWING = "swing"           # Swing trading (jours/semaines)
    SCALPING = "scalping"     # Day trading / scalping


@dataclass
class TradingModeConfig:
    """Configuration d'un mode de trading."""
    mode: TradingMode
    display_name: str
    description: str
    poll_interval: float           # Intervalle de polling en secondes (0 = temps reel)
    priority_interval: float       # Intervalle pour tickers prioritaires
    use_websocket: bool            # Utiliser WebSocket temps reel
    preferred_sources: List[str]   # Sources preferees (ordre de priorite)
    alert_check_interval: float    # Intervalle de verification des alertes


# Configurations predefinies
TRADING_MODE_CONFIGS = {
    TradingMode.LONG_TERM: TradingModeConfig(
        mode=TradingMode.LONG_TERM,
        display_name="Long Terme",
        description="Investissement long terme. Rafraichissement toutes les 60s. Economique en API.",
        poll_interval=60.0,
        priority_interval=30.0,
        use_websocket=False,
        preferred_sources=["yahoo"],
        alert_check_interval=60.0,
    ),
    TradingMode.SWING: TradingModeConfig(
        mode=TradingMode.SWING,
        display_name="Swing Trading",
        description="Trading sur plusieurs jours. Rafraichissement toutes les 10s.",
        poll_interval=10.0,
        priority_interval=5.0,
        use_websocket=False,
        preferred_sources=["finnhub", "yahoo"],
        alert_check_interval=30.0,
    ),
    TradingMode.SCALPING: TradingModeConfig(
        mode=TradingMode.SCALPING,
        display_name="Scalping",
        description="Day trading actif. Prix en temps reel via WebSocket.",
        poll_interval=0.0,  # Pas de polling, temps reel
        priority_interval=0.0,
        use_websocket=True,
        preferred_sources=["saxo", "finnhub", "yahoo"],
        alert_check_interval=5.0,
    ),
}


def get_mode_config(mode: TradingMode) -> TradingModeConfig:
    """
    Retourne la configuration pour un mode de trading.

    Args:
        mode: Mode de trading

    Returns:
        TradingModeConfig correspondant
    """
    return TRADING_MODE_CONFIGS.get(mode, TRADING_MODE_CONFIGS[TradingMode.LONG_TERM])


def get_all_modes() -> List[dict]:
    """
    Retourne tous les modes disponibles pour le frontend.

    Returns:
        Liste des modes avec leurs configurations
    """
    return [
        {
            "id": config.mode.value,
            "name": config.display_name,
            "description": config.description,
            "poll_interval": config.poll_interval,
            "use_websocket": config.use_websocket,
            "sources": config.preferred_sources,
        }
        for config in TRADING_MODE_CONFIGS.values()
    ]


# Mode actuel (singleton)
_current_mode: TradingMode = TradingMode.LONG_TERM


def get_current_mode() -> TradingMode:
    """Retourne le mode de trading actuel."""
    return _current_mode


def set_current_mode(mode: TradingMode) -> TradingModeConfig:
    """
    Change le mode de trading actuel.

    Args:
        mode: Nouveau mode

    Returns:
        Configuration du nouveau mode
    """
    global _current_mode
    _current_mode = mode
    return get_mode_config(mode)


def get_current_config() -> TradingModeConfig:
    """Retourne la configuration du mode actuel."""
    return get_mode_config(_current_mode)
