"""
Service de chiffrement pour les données sensibles.

Utilise Fernet (AES-128-CBC) pour chiffrer/déchiffrer les tokens.
La clé doit être stockée dans la variable d'environnement ENCRYPTION_KEY.

ARCHITECTURE:
- Couche INFRASTRUCTURE
- Utilisé par TokenStore pour chiffrer les tokens avant stockage
- Génération de clé incluse pour faciliter le setup

SÉCURITÉ:
- La clé doit rester secrète (jamais dans le code ou git)
- En cas de compromission de la clé, tous les tokens doivent être révoqués
- La clé est générée une fois et stockée dans .env

UTILISATION:
    from src.infrastructure.persistence.encryption import EncryptionService

    service = EncryptionService()

    # Chiffrer
    encrypted = service.encrypt("mon_secret")

    # Déchiffrer
    decrypted = service.decrypt(encrypted)
"""

import base64
import logging
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken

from src.config.settings import settings

logger = logging.getLogger(__name__)


class EncryptionError(Exception):
    """Exception levée lors d'erreurs de chiffrement/déchiffrement."""
    pass


class EncryptionService:
    """
    Service de chiffrement/déchiffrement basé sur Fernet.

    Fernet garantit que les données chiffrées ne peuvent pas être
    manipulées sans détection (HMAC intégré).

    Attributs:
        _fernet: Instance Fernet initialisée avec la clé
    """

    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialise le service avec une clé de chiffrement.

        Args:
            encryption_key: Clé Fernet base64 (32 bytes encodés).
                          Si None, utilise settings.ENCRYPTION_KEY.
                          Si toujours None, génère une nouvelle clé.

        Note:
            En production, la clé devrait TOUJOURS être fournie via
            la variable d'environnement ENCRYPTION_KEY.
        """
        key = encryption_key or settings.ENCRYPTION_KEY

        if key is None:
            # Générer une nouvelle clé (développement uniquement)
            logger.warning(
                "ENCRYPTION_KEY non définie. Génération d'une clé temporaire. "
                "Les tokens ne survivront pas au redémarrage!"
            )
            key = self.generate_key()

        try:
            # Fernet attend une clé bytes encodée en base64
            if isinstance(key, str):
                key = key.encode()
            self._fernet = Fernet(key)
        except Exception as e:
            raise EncryptionError(
                f"Clé de chiffrement invalide. "
                f"Générez-en une avec: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            ) from e

    def encrypt(self, data: str) -> str:
        """
        Chiffre une chaîne de caractères.

        Args:
            data: Données à chiffrer

        Returns:
            Données chiffrées encodées en base64 (ASCII safe)

        Raises:
            EncryptionError: Si le chiffrement échoue
        """
        if not data:
            return ""

        try:
            encrypted_bytes = self._fernet.encrypt(data.encode("utf-8"))
            return encrypted_bytes.decode("utf-8")
        except Exception as e:
            logger.error(f"Erreur de chiffrement: {e}")
            raise EncryptionError("Échec du chiffrement") from e

    def decrypt(self, encrypted_data: str) -> str:
        """
        Déchiffre des données précédemment chiffrées.

        Args:
            encrypted_data: Données chiffrées (base64)

        Returns:
            Données déchiffrées

        Raises:
            EncryptionError: Si le déchiffrement échoue (clé incorrecte, données corrompues)
        """
        if not encrypted_data:
            return ""

        try:
            decrypted_bytes = self._fernet.decrypt(encrypted_data.encode("utf-8"))
            return decrypted_bytes.decode("utf-8")
        except InvalidToken:
            logger.error("Token de déchiffrement invalide - clé incorrecte ou données corrompues")
            raise EncryptionError(
                "Déchiffrement impossible. La clé a peut-être changé."
            )
        except Exception as e:
            logger.error(f"Erreur de déchiffrement: {e}")
            raise EncryptionError("Échec du déchiffrement") from e

    def encrypt_dict(self, data: dict) -> str:
        """
        Chiffre un dictionnaire (converti en JSON).

        Args:
            data: Dictionnaire à chiffrer

        Returns:
            JSON chiffré encodé en base64
        """
        import json
        json_str = json.dumps(data, ensure_ascii=False, default=str)
        return self.encrypt(json_str)

    def decrypt_dict(self, encrypted_data: str) -> dict:
        """
        Déchiffre et parse un dictionnaire JSON.

        Args:
            encrypted_data: JSON chiffré

        Returns:
            Dictionnaire déchiffré
        """
        import json
        json_str = self.decrypt(encrypted_data)
        if not json_str:
            return {}
        return json.loads(json_str)

    @staticmethod
    def generate_key() -> str:
        """
        Génère une nouvelle clé de chiffrement Fernet.

        Cette méthode est utile pour :
        - Le setup initial (copier la clé dans .env)
        - La rotation de clés

        Returns:
            Clé Fernet encodée en base64 (string)

        Usage en ligne de commande:
            python -c "from src.infrastructure.persistence.encryption import EncryptionService; print(EncryptionService.generate_key())"
        """
        return Fernet.generate_key().decode("utf-8")

    def verify_key(self) -> bool:
        """
        Vérifie que la clé fonctionne correctement.

        Effectue un cycle chiffrement/déchiffrement avec des données de test.

        Returns:
            True si la clé est valide
        """
        test_data = "test_verification_string_12345"
        try:
            encrypted = self.encrypt(test_data)
            decrypted = self.decrypt(encrypted)
            return decrypted == test_data
        except EncryptionError:
            return False


# Instance globale (singleton)
# Attention: ne pas utiliser avant que settings soit chargé
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """
    Retourne l'instance singleton du service de chiffrement.

    Returns:
        EncryptionService initialisé
    """
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service
