"""
Service de configuration des alertes techniques et du monitoring.

Gere les parametres:
- Activation/desactivation des alertes techniques
- Frequence de scan du portfolio
- Seuils des indicateurs (RSI, MACD, Bollinger)
- Historique des signaux detectes

UTILISATION:
    from src.application.services.alert_config_service import get_alert_config_service

    config = get_alert_config_service()
    config.set_enabled(True)
    config.set_scan_interval(300)  # 5 minutes
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict, field
from filelock import FileLock

from src.config.settings import settings

logger = logging.getLogger(__name__)

# Chemin du fichier de configuration
CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "data"
CONFIG_FILE = CONFIG_DIR / "alert_config.json"
SIGNAL_HISTORY_FILE = CONFIG_DIR / "signal_history.json"


@dataclass
class TechnicalAlertConfig:
    """Configuration des alertes techniques."""

    # Activation globale
    enabled: bool = True

    # Frequence de scan en secondes (defaut: 60s)
    scan_interval: int = 60

    # Seuils RSI
    rsi_enabled: bool = True
    rsi_overbought: int = 70
    rsi_oversold: int = 30

    # MACD
    macd_enabled: bool = True
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # Bollinger Bands
    bollinger_enabled: bool = True
    bollinger_period: int = 20
    bollinger_std: float = 2.0

    # Support/Resistance
    support_resistance_enabled: bool = False

    # Notifications
    notify_telegram: bool = True
    notify_only_high_severity: bool = False

    # Cooldown entre alertes pour le meme ticker (en minutes)
    cooldown_minutes: int = 60

    # Heures de trading (optionnel)
    trading_hours_only: bool = False
    trading_start_hour: int = 9
    trading_end_hour: int = 17

    # Metadata
    updated_at: str = ""

    def __post_init__(self):
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TechnicalAlertConfig":
        # Filtrer les cles inconnues
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


@dataclass
class SignalHistoryEntry:
    """Entree dans l'historique des signaux."""
    timestamp: str
    ticker: str
    signal_type: str
    indicator_value: float
    price: float
    severity: str
    notified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Presets de configuration
PRESETS = {
    "conservative": TechnicalAlertConfig(
        enabled=True,
        scan_interval=300,  # 5 min
        rsi_overbought=75,
        rsi_oversold=25,
        notify_only_high_severity=True,
        cooldown_minutes=120,
    ),
    "moderate": TechnicalAlertConfig(
        enabled=True,
        scan_interval=60,  # 1 min
        rsi_overbought=70,
        rsi_oversold=30,
        notify_only_high_severity=False,
        cooldown_minutes=60,
    ),
    "aggressive": TechnicalAlertConfig(
        enabled=True,
        scan_interval=30,  # 30s
        rsi_overbought=65,
        rsi_oversold=35,
        notify_only_high_severity=False,
        cooldown_minutes=30,
    ),
    "disabled": TechnicalAlertConfig(
        enabled=False,
        scan_interval=60,
    ),
}


class AlertConfigService:
    """
    Service de gestion de la configuration des alertes.

    Persiste la configuration dans un fichier JSON.
    Thread-safe avec FileLock.
    """

    def __init__(self):
        self._config: Optional[TechnicalAlertConfig] = None
        self._signal_history: List[SignalHistoryEntry] = []
        self._lock_path = CONFIG_FILE.with_suffix(".lock")

        # Creer le repertoire si necessaire
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # Charger la configuration
        self._load_config()
        self._load_history()

    def _load_config(self) -> None:
        """Charge la configuration depuis le fichier."""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                self._config = TechnicalAlertConfig.from_dict(data)
                logger.info("Alert config loaded from file")
            else:
                self._config = TechnicalAlertConfig()
                self._save_config()
                logger.info("Created default alert config")
        except Exception as e:
            logger.error(f"Error loading alert config: {e}")
            self._config = TechnicalAlertConfig()

    def _save_config(self) -> None:
        """Sauvegarde la configuration dans le fichier."""
        try:
            self._config.updated_at = datetime.now().isoformat()
            with FileLock(self._lock_path):
                with open(CONFIG_FILE, "w") as f:
                    json.dump(self._config.to_dict(), f, indent=2)
            logger.debug("Alert config saved")
        except Exception as e:
            logger.error(f"Error saving alert config: {e}")

    def _load_history(self) -> None:
        """Charge l'historique des signaux."""
        try:
            if SIGNAL_HISTORY_FILE.exists():
                with open(SIGNAL_HISTORY_FILE, "r") as f:
                    data = json.load(f)
                self._signal_history = [
                    SignalHistoryEntry(**entry) for entry in data
                ]
        except Exception as e:
            logger.error(f"Error loading signal history: {e}")
            self._signal_history = []

    def _save_history(self) -> None:
        """Sauvegarde l'historique des signaux."""
        try:
            # Garder seulement les 500 derniers signaux
            recent = self._signal_history[-500:]
            with open(SIGNAL_HISTORY_FILE, "w") as f:
                json.dump([s.to_dict() for s in recent], f, indent=2)
        except Exception as e:
            logger.error(f"Error saving signal history: {e}")

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    @property
    def config(self) -> TechnicalAlertConfig:
        """Retourne la configuration actuelle."""
        return self._config

    def get_config(self) -> Dict[str, Any]:
        """Retourne la configuration en dict."""
        return self._config.to_dict()

    def update_config(self, updates: Dict[str, Any]) -> TechnicalAlertConfig:
        """
        Met a jour la configuration.

        Args:
            updates: Dict avec les champs a mettre a jour

        Returns:
            Configuration mise a jour
        """
        current = self._config.to_dict()
        current.update(updates)
        self._config = TechnicalAlertConfig.from_dict(current)
        self._save_config()

        logger.info(f"Alert config updated: {list(updates.keys())}")
        return self._config

    def apply_preset(self, preset_name: str) -> TechnicalAlertConfig:
        """
        Applique un preset de configuration.

        Args:
            preset_name: Nom du preset (conservative, moderate, aggressive, disabled)

        Returns:
            Configuration mise a jour
        """
        if preset_name not in PRESETS:
            raise ValueError(f"Unknown preset: {preset_name}")

        self._config = TechnicalAlertConfig(**asdict(PRESETS[preset_name]))
        self._save_config()

        logger.info(f"Applied preset: {preset_name}")
        return self._config

    def set_enabled(self, enabled: bool) -> None:
        """Active ou desactive les alertes techniques."""
        self._config.enabled = enabled
        self._save_config()
        logger.info(f"Technical alerts {'enabled' if enabled else 'disabled'}")

    def set_scan_interval(self, seconds: int) -> None:
        """
        Definit l'intervalle de scan.

        Args:
            seconds: Intervalle en secondes (min: 10, max: 86400)
        """
        seconds = max(10, min(86400, seconds))
        self._config.scan_interval = seconds
        self._save_config()
        logger.info(f"Scan interval set to {seconds}s")

    def is_enabled(self) -> bool:
        """Verifie si les alertes techniques sont activees."""
        return self._config.enabled

    def get_scan_interval(self) -> int:
        """Retourne l'intervalle de scan en secondes."""
        return self._config.scan_interval

    def should_scan_now(self) -> bool:
        """
        Verifie si un scan doit etre effectue maintenant.

        Prend en compte:
        - L'activation globale
        - Les heures de trading (si active)
        """
        if not self._config.enabled:
            return False

        if self._config.trading_hours_only:
            now = datetime.now()
            if not (self._config.trading_start_hour <= now.hour < self._config.trading_end_hour):
                return False

        return True

    def is_in_cooldown(self, ticker: str, signal_type: str) -> bool:
        """
        Verifie si un ticker est en cooldown pour un type de signal.

        Args:
            ticker: Symbole du ticker
            signal_type: Type de signal

        Returns:
            True si en cooldown
        """
        cooldown = timedelta(minutes=self._config.cooldown_minutes)
        cutoff = datetime.now() - cooldown

        for entry in reversed(self._signal_history):
            if entry.ticker == ticker and entry.signal_type == signal_type:
                entry_time = datetime.fromisoformat(entry.timestamp)
                if entry_time > cutoff:
                    return True
                break

        return False

    # =========================================================================
    # HISTORY
    # =========================================================================

    def add_signal(
        self,
        ticker: str,
        signal_type: str,
        indicator_value: float,
        price: float,
        severity: str,
        notified: bool = False
    ) -> None:
        """Ajoute un signal a l'historique."""
        entry = SignalHistoryEntry(
            timestamp=datetime.now().isoformat(),
            ticker=ticker,
            signal_type=signal_type,
            indicator_value=indicator_value,
            price=price,
            severity=severity,
            notified=notified,
        )
        self._signal_history.append(entry)
        self._save_history()

    def get_history(
        self,
        limit: int = 50,
        ticker: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retourne l'historique des signaux.

        Args:
            limit: Nombre max de signaux
            ticker: Filtrer par ticker (optionnel)
        """
        history = self._signal_history

        if ticker:
            history = [s for s in history if s.ticker == ticker]

        # Les plus recents en premier
        history = list(reversed(history[-limit:]))

        return [s.to_dict() for s in history]

    def clear_history(self) -> None:
        """Efface l'historique des signaux."""
        self._signal_history = []
        self._save_history()
        logger.info("Signal history cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Retourne des statistiques sur les signaux."""
        now = datetime.now()
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)

        signals_24h = 0
        signals_7d = 0
        by_type = {}
        by_ticker = {}

        for entry in self._signal_history:
            entry_time = datetime.fromisoformat(entry.timestamp)

            if entry_time > day_ago:
                signals_24h += 1
            if entry_time > week_ago:
                signals_7d += 1

            by_type[entry.signal_type] = by_type.get(entry.signal_type, 0) + 1
            by_ticker[entry.ticker] = by_ticker.get(entry.ticker, 0) + 1

        return {
            "total_signals": len(self._signal_history),
            "signals_24h": signals_24h,
            "signals_7d": signals_7d,
            "by_type": by_type,
            "by_ticker": by_ticker,
            "top_tickers": sorted(by_ticker.items(), key=lambda x: x[1], reverse=True)[:5],
        }

    @staticmethod
    def get_presets() -> Dict[str, Dict[str, Any]]:
        """Retourne les presets disponibles."""
        return {
            name: {
                "name": name.replace("_", " ").title(),
                "description": _get_preset_description(name),
                "config": preset.to_dict()
            }
            for name, preset in PRESETS.items()
        }


def _get_preset_description(name: str) -> str:
    """Retourne la description d'un preset."""
    descriptions = {
        "conservative": "Alertes prudentes. Scan toutes les 5 min, seuils larges, notifications high severity uniquement.",
        "moderate": "Equilibre entre reactivite et bruit. Scan toutes les minutes, seuils standards.",
        "aggressive": "Alertes frequentes. Scan toutes les 30s, seuils serres. Pour trading actif.",
        "disabled": "Alertes techniques desactivees. Aucun scan automatique.",
    }
    return descriptions.get(name, "")


# Singleton
_alert_config_service: Optional[AlertConfigService] = None


def get_alert_config_service() -> AlertConfigService:
    """Retourne l'instance singleton du service."""
    global _alert_config_service
    if _alert_config_service is None:
        _alert_config_service = AlertConfigService()
    return _alert_config_service
