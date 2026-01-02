"""
Service OTP (One-Time Password) via Telegram.

Permet de sécuriser les opérations sensibles avec un code de vérification
envoyé par Telegram. Le code expire après 5 minutes.

FLOW:
1. L'utilisateur demande un OTP pour une action (ex: modifier credentials)
2. Le système génère un code 6 digits et l'envoie via Telegram
3. L'utilisateur soumet le code avec sa modification
4. Le système vérifie le code avant d'appliquer les changements
"""

import secrets
import hashlib
import time
import logging
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class OTPAction(str, Enum):
    """Actions nécessitant une vérification OTP."""
    UPDATE_SAXO = "update_saxo"
    UPDATE_TELEGRAM = "update_telegram"
    DELETE_CREDENTIALS = "delete_credentials"
    SWITCH_ENVIRONMENT = "switch_environment"


@dataclass
class OTPRequest:
    """Représente une demande OTP en attente."""
    code_hash: str  # Hash SHA256 du code (jamais stocké en clair)
    action: OTPAction
    created_at: float
    expires_at: float
    attempts: int = 0
    max_attempts: int = 3
    metadata: Optional[dict] = None


class OTPService:
    """
    Service de gestion des codes OTP.

    Génère des codes temporaires envoyés via Telegram pour
    authentifier les opérations sensibles de configuration.

    Sécurité:
    - Les codes sont hashés (jamais stockés en clair)
    - Expiration après 5 minutes
    - Maximum 3 tentatives par code
    - Rate limiting intégré
    """

    # Durée de validité d'un OTP (5 minutes)
    OTP_VALIDITY_SECONDS = 300

    # Délai minimum entre deux demandes OTP (30 secondes)
    MIN_REQUEST_INTERVAL = 30

    def __init__(self):
        """Initialise le service OTP."""
        # Stockage en mémoire des OTPs actifs (par action)
        self._active_otps: Dict[OTPAction, OTPRequest] = {}
        self._last_request_time: float = 0

    def generate_code(self) -> str:
        """
        Génère un code OTP aléatoire de 6 chiffres.

        Returns:
            Code OTP en format string (ex: "482935")
        """
        # Utilise secrets pour la génération cryptographique
        return f"{secrets.randbelow(1000000):06d}"

    def _hash_code(self, code: str) -> str:
        """
        Hash le code OTP avec SHA256.

        Args:
            code: Code OTP en clair

        Returns:
            Hash hexadécimal du code
        """
        return hashlib.sha256(code.encode()).hexdigest()

    def request_otp(
        self,
        action: OTPAction,
        metadata: Optional[dict] = None
    ) -> Tuple[str, str]:
        """
        Génère un nouveau code OTP pour une action.

        Args:
            action: Type d'action à autoriser
            metadata: Données supplémentaires à associer

        Returns:
            Tuple (code_clair, message_telegram)

        Raises:
            ValueError: Si rate limit atteint
        """
        now = time.time()

        # Rate limiting
        if now - self._last_request_time < self.MIN_REQUEST_INTERVAL:
            remaining = int(self.MIN_REQUEST_INTERVAL - (now - self._last_request_time))
            raise ValueError(
                f"Veuillez attendre {remaining} secondes avant de demander un nouveau code"
            )

        # Générer le code
        code = self.generate_code()
        code_hash = self._hash_code(code)

        # Créer la requête OTP
        expires_at = now + self.OTP_VALIDITY_SECONDS
        otp_request = OTPRequest(
            code_hash=code_hash,
            action=action,
            created_at=now,
            expires_at=expires_at,
            metadata=metadata
        )

        # Stocker (remplace l'ancien OTP pour cette action)
        self._active_otps[action] = otp_request
        self._last_request_time = now

        # Construire le message Telegram
        action_labels = {
            OTPAction.UPDATE_SAXO: "🔐 Modification credentials Saxo Bank",
            OTPAction.UPDATE_TELEGRAM: "📱 Modification configuration Telegram",
            OTPAction.DELETE_CREDENTIALS: "🗑️ Suppression de credentials",
            OTPAction.SWITCH_ENVIRONMENT: "🔄 Changement d'environnement Saxo",
        }

        action_label = action_labels.get(action, str(action))
        expire_time = datetime.fromtimestamp(expires_at).strftime("%H:%M:%S")

        message = (
            f"🔒 <b>CODE DE VÉRIFICATION</b>\n\n"
            f"Action: {action_label}\n\n"
            f"<code>{code}</code>\n\n"
            f"⏱️ Expire à: {expire_time}\n"
            f"⚠️ Ne partagez jamais ce code!\n\n"
            f"<i>Stock Analyzer - Sécurité</i>"
        )

        logger.info(f"OTP généré pour action: {action}")

        return code, message

    def verify_otp(self, action: OTPAction, code: str) -> Tuple[bool, str]:
        """
        Vérifie un code OTP pour une action.

        Args:
            action: Action pour laquelle le code a été généré
            code: Code OTP fourni par l'utilisateur

        Returns:
            Tuple (succès, message)
        """
        # Vérifier si un OTP existe pour cette action
        otp_request = self._active_otps.get(action)

        if not otp_request:
            return False, "Aucun code en attente. Veuillez demander un nouveau code."

        # Vérifier l'expiration
        if time.time() > otp_request.expires_at:
            del self._active_otps[action]
            return False, "Le code a expiré. Veuillez demander un nouveau code."

        # Vérifier le nombre de tentatives
        if otp_request.attempts >= otp_request.max_attempts:
            del self._active_otps[action]
            return False, "Trop de tentatives. Veuillez demander un nouveau code."

        # Incrémenter le compteur de tentatives
        otp_request.attempts += 1

        # Vérifier le code (comparaison de hashes)
        if self._hash_code(code) != otp_request.code_hash:
            remaining = otp_request.max_attempts - otp_request.attempts
            return False, f"Code incorrect. {remaining} tentative(s) restante(s)."

        # Succès - supprimer l'OTP utilisé
        del self._active_otps[action]
        logger.info(f"OTP vérifié avec succès pour action: {action}")

        return True, "Code vérifié avec succès!"

    def get_otp_metadata(self, action: OTPAction) -> Optional[dict]:
        """
        Récupère les métadonnées associées à un OTP.

        Args:
            action: Action concernée

        Returns:
            Métadonnées ou None
        """
        otp_request = self._active_otps.get(action)
        if otp_request:
            return otp_request.metadata
        return None

    def cancel_otp(self, action: OTPAction) -> bool:
        """
        Annule un OTP en cours.

        Args:
            action: Action à annuler

        Returns:
            True si un OTP a été annulé
        """
        if action in self._active_otps:
            del self._active_otps[action]
            logger.info(f"OTP annulé pour action: {action}")
            return True
        return False

    def cleanup_expired(self) -> int:
        """
        Nettoie les OTPs expirés.

        Returns:
            Nombre d'OTPs supprimés
        """
        now = time.time()
        expired = [
            action for action, otp in self._active_otps.items()
            if now > otp.expires_at
        ]

        for action in expired:
            del self._active_otps[action]

        if expired:
            logger.debug(f"Nettoyage de {len(expired)} OTPs expirés")

        return len(expired)


# Singleton
_otp_service: Optional[OTPService] = None


def get_otp_service() -> OTPService:
    """
    Retourne l'instance singleton du service OTP.

    Returns:
        OTPService initialisé
    """
    global _otp_service
    if _otp_service is None:
        _otp_service = OTPService()
    return _otp_service
