import { useState, useEffect, useCallback } from 'react';
import {
  getConfigStatus,
  requestOTP,
  setupTelegramInitial,
  setupSaxoInitial,
  updateSaxoConfig,
  updateTelegramConfig,
  switchSaxoEnvironment,
  deleteCredentials,
} from '../api';

// =============================================================================
// STYLES
// =============================================================================

const styles = {
  container: {
    padding: '24px',
    maxWidth: '900px',
    margin: '0 auto',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    marginBottom: '24px',
    paddingBottom: '16px',
    borderBottom: '1px solid #333'
  },
  title: {
    fontSize: '24px',
    fontWeight: '600',
    color: '#fff',
    margin: 0
  },
  subtitle: {
    fontSize: '14px',
    color: '#888',
    marginTop: '4px'
  },
  section: {
    backgroundColor: '#1a1a2e',
    borderRadius: '12px',
    padding: '20px',
    marginBottom: '20px',
    border: '1px solid #333'
  },
  sectionHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '16px'
  },
  sectionTitle: {
    fontSize: '18px',
    fontWeight: '500',
    color: '#fff',
    display: 'flex',
    alignItems: 'center',
    gap: '8px'
  },
  badge: {
    fontSize: '12px',
    padding: '4px 8px',
    borderRadius: '4px',
    fontWeight: '500'
  },
  badgeSuccess: {
    backgroundColor: 'rgba(76, 175, 80, 0.2)',
    color: '#4CAF50'
  },
  badgeWarning: {
    backgroundColor: 'rgba(255, 193, 7, 0.2)',
    color: '#FFC107'
  },
  badgeDanger: {
    backgroundColor: 'rgba(244, 67, 54, 0.2)',
    color: '#f44336'
  },
  infoRow: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '12px 0',
    borderBottom: '1px solid #333'
  },
  label: {
    color: '#888',
    fontSize: '14px'
  },
  value: {
    color: '#fff',
    fontSize: '14px',
    fontFamily: 'monospace'
  },
  buttonGroup: {
    display: 'flex',
    gap: '8px',
    marginTop: '16px',
    flexWrap: 'wrap'
  },
  button: {
    padding: '10px 16px',
    borderRadius: '6px',
    border: 'none',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '500',
    transition: 'all 0.2s'
  },
  buttonPrimary: {
    backgroundColor: '#4CAF50',
    color: '#fff'
  },
  buttonSecondary: {
    backgroundColor: '#333',
    color: '#fff',
    border: '1px solid #555'
  },
  buttonDanger: {
    backgroundColor: 'rgba(244, 67, 54, 0.2)',
    color: '#f44336',
    border: '1px solid #f44336'
  },
  buttonDisabled: {
    opacity: 0.5,
    cursor: 'not-allowed'
  },
  modal: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000
  },
  modalContent: {
    backgroundColor: '#1a1a2e',
    borderRadius: '12px',
    padding: '24px',
    maxWidth: '500px',
    width: '90%',
    border: '1px solid #333'
  },
  modalTitle: {
    fontSize: '20px',
    fontWeight: '600',
    color: '#fff',
    marginBottom: '16px'
  },
  input: {
    width: '100%',
    padding: '12px',
    borderRadius: '6px',
    border: '1px solid #444',
    backgroundColor: '#0d0d1a',
    color: '#fff',
    fontSize: '14px',
    marginBottom: '12px',
    boxSizing: 'border-box'
  },
  otpInput: {
    width: '100%',
    padding: '16px',
    borderRadius: '8px',
    border: '2px solid #4CAF50',
    backgroundColor: '#0d0d1a',
    color: '#fff',
    fontSize: '24px',
    textAlign: 'center',
    letterSpacing: '8px',
    fontFamily: 'monospace',
    marginBottom: '16px',
    boxSizing: 'border-box'
  },
  errorMessage: {
    backgroundColor: 'rgba(244, 67, 54, 0.1)',
    color: '#f44336',
    padding: '12px',
    borderRadius: '6px',
    marginBottom: '12px',
    fontSize: '14px'
  },
  successMessage: {
    backgroundColor: 'rgba(76, 175, 80, 0.1)',
    color: '#4CAF50',
    padding: '12px',
    borderRadius: '6px',
    marginBottom: '12px',
    fontSize: '14px'
  },
  infoBox: {
    backgroundColor: 'rgba(33, 150, 243, 0.1)',
    color: '#2196F3',
    padding: '12px',
    borderRadius: '6px',
    marginBottom: '16px',
    fontSize: '13px',
    lineHeight: '1.5'
  },
  toggle: {
    display: 'flex',
    gap: '8px',
    backgroundColor: '#0d0d1a',
    borderRadius: '8px',
    padding: '4px'
  },
  toggleOption: {
    padding: '10px 20px',
    borderRadius: '6px',
    border: 'none',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '500',
    backgroundColor: 'transparent',
    color: '#888',
    transition: 'all 0.2s'
  },
  toggleOptionActive: {
    backgroundColor: '#333',
    color: '#fff'
  }
};

// =============================================================================
// COMPOSANTS
// =============================================================================

function StatusBadge({ configured }) {
  return (
    <span style={{
      ...styles.badge,
      ...(configured ? styles.badgeSuccess : styles.badgeWarning)
    }}>
      {configured ? 'Configure' : 'Non configure'}
    </span>
  );
}

function EnvironmentBadge({ environment }) {
  const isLive = environment === 'LIVE';
  return (
    <span style={{
      ...styles.badge,
      ...(isLive ? styles.badgeDanger : styles.badgeSuccess)
    }}>
      {isLive ? 'PRODUCTION' : 'DEMO'}
    </span>
  );
}

// =============================================================================
// MODALE TELEGRAM (Setup initial ou Modification)
// =============================================================================

function TelegramModal({ isOpen, onClose, onSubmit, loading, error, isUpdate, otpCode, setOtpCode, otpSent, onRequestOTP, otpLoading }) {
  const [botToken, setBotToken] = useState('');
  const [chatId, setChatId] = useState('');

  const handleSubmit = () => {
    if (botToken && chatId) {
      if (isUpdate) {
        onSubmit(otpCode, { bot_token: botToken, chat_id: chatId });
      } else {
        onSubmit(botToken, chatId);
      }
    }
  };

  const resetForm = () => {
    setBotToken('');
    setChatId('');
  };

  if (!isOpen) return null;

  return (
    <div style={styles.modal} onClick={() => { onClose(); resetForm(); }}>
      <div style={styles.modalContent} onClick={e => e.stopPropagation()}>
        <h3 style={styles.modalTitle}>
          {isUpdate ? 'Modifier Telegram' : 'Configuration Telegram'}
        </h3>

        <div style={styles.infoBox}>
          <strong>Comment obtenir ces informations :</strong><br/>
          1. Creez un bot via @BotFather sur Telegram<br/>
          2. Copiez le token fourni<br/>
          3. Envoyez un message au bot, puis utilisez @userinfobot pour obtenir votre Chat ID
        </div>

        {error && <div style={styles.errorMessage}>{error}</div>}

        {/* Si modification, d'abord demander OTP */}
        {isUpdate && !otpSent && (
          <>
            <div style={{ ...styles.infoBox, backgroundColor: 'rgba(255, 193, 7, 0.1)', color: '#FFC107' }}>
              Pour modifier vos credentials Telegram, vous devez d'abord recevoir un code OTP sur votre configuration actuelle.
            </div>
            <button
              style={{ ...styles.button, ...styles.buttonPrimary, width: '100%' }}
              onClick={onRequestOTP}
              disabled={otpLoading}
            >
              {otpLoading ? 'Envoi en cours...' : 'Recevoir le code OTP'}
            </button>
          </>
        )}

        {/* Si OTP envoye ou setup initial, afficher le formulaire */}
        {(!isUpdate || otpSent) && (
          <>
            {isUpdate && (
              <input
                type="text"
                style={styles.otpInput}
                placeholder="000000"
                value={otpCode}
                onChange={e => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                maxLength={6}
                autoFocus
              />
            )}

            <input
              type="text"
              style={styles.input}
              placeholder="Bot Token (ex: 123456789:ABCdefGHI...)"
              value={botToken}
              onChange={e => setBotToken(e.target.value)}
            />

            <input
              type="text"
              style={styles.input}
              placeholder="Chat ID (ex: 123456789)"
              value={chatId}
              onChange={e => setChatId(e.target.value)}
            />

            <div style={styles.buttonGroup}>
              <button
                style={{ ...styles.button, ...styles.buttonSecondary }}
                onClick={() => { onClose(); resetForm(); }}
              >
                Annuler
              </button>
              <button
                style={{
                  ...styles.button,
                  ...styles.buttonPrimary,
                  ...(!botToken || !chatId || (isUpdate && otpCode.length !== 6) || loading ? styles.buttonDisabled : {})
                }}
                onClick={handleSubmit}
                disabled={!botToken || !chatId || (isUpdate && otpCode.length !== 6) || loading}
              >
                {loading ? 'En cours...' : (isUpdate ? 'Mettre a jour' : 'Configurer')}
              </button>
            </div>
          </>
        )}

        {isUpdate && !otpSent && (
          <div style={styles.buttonGroup}>
            <button
              style={{ ...styles.button, ...styles.buttonSecondary, width: '100%' }}
              onClick={() => { onClose(); resetForm(); }}
            >
              Annuler
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// MODALE SAXO
// =============================================================================

function SaxoModal({ isOpen, onClose, onSetup, onUpdate, loading, error, currentEnv, otpCode, setOtpCode, otpSent, onRequestOTP, otpLoading, isConfigured }) {
  const [appKey, setAppKey] = useState('');
  const [appSecret, setAppSecret] = useState('');
  const [environment, setEnvironment] = useState(currentEnv || 'SIM');

  const handleSubmit = () => {
    if (appKey && appSecret) {
      const config = { app_key: appKey, app_secret: appSecret, environment };
      if (isConfigured) {
        // Update avec OTP
        onUpdate(otpCode, config);
      } else {
        // Setup initial sans OTP
        onSetup(config);
      }
    }
  };

  const resetForm = () => {
    setAppKey('');
    setAppSecret('');
    setEnvironment(currentEnv || 'SIM');
  };

  if (!isOpen) return null;

  const needsOTP = isConfigured; // Si deja configure, besoin OTP

  return (
    <div style={styles.modal} onClick={() => { onClose(); resetForm(); }}>
      <div style={styles.modalContent} onClick={e => e.stopPropagation()}>
        <h3 style={styles.modalTitle}>
          {isConfigured ? 'Modifier Saxo Bank' : 'Configuration Saxo Bank'}
        </h3>

        <div style={styles.infoBox}>
          Obtenez vos credentials depuis le portail developpeur Saxo Bank:<br/>
          <a href="https://developer.saxo" target="_blank" rel="noreferrer" style={{ color: '#4CAF50' }}>
            developer.saxo
          </a>
        </div>

        {error && <div style={styles.errorMessage}>{error}</div>}

        {/* Si modification, d'abord demander OTP */}
        {needsOTP && !otpSent && (
          <>
            <div style={{ ...styles.infoBox, backgroundColor: 'rgba(255, 193, 7, 0.1)', color: '#FFC107' }}>
              Un code OTP sera envoye sur Telegram pour securiser cette modification.
            </div>
            <button
              style={{ ...styles.button, ...styles.buttonPrimary, width: '100%' }}
              onClick={onRequestOTP}
              disabled={otpLoading}
            >
              {otpLoading ? 'Envoi en cours...' : 'Recevoir le code OTP'}
            </button>
            <div style={styles.buttonGroup}>
              <button
                style={{ ...styles.button, ...styles.buttonSecondary, width: '100%' }}
                onClick={() => { onClose(); resetForm(); }}
              >
                Annuler
              </button>
            </div>
          </>
        )}

        {/* Afficher le formulaire si pas besoin OTP ou si OTP envoye */}
        {(!needsOTP || otpSent) && (
          <>
            {needsOTP && (
              <>
                <div style={{ marginBottom: '8px', color: '#888', fontSize: '12px' }}>Code OTP recu sur Telegram:</div>
                <input
                  type="text"
                  style={styles.otpInput}
                  placeholder="000000"
                  value={otpCode}
                  onChange={e => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  maxLength={6}
                  autoFocus
                />
              </>
            )}

            <input
              type="text"
              style={styles.input}
              placeholder="App Key"
              value={appKey}
              onChange={e => setAppKey(e.target.value)}
            />

            <input
              type="password"
              style={styles.input}
              placeholder="App Secret"
              value={appSecret}
              onChange={e => setAppSecret(e.target.value)}
            />

            <div style={{ marginBottom: '16px' }}>
              <div style={{ ...styles.label, marginBottom: '8px' }}>Environnement</div>
              <div style={styles.toggle}>
                <button
                  type="button"
                  style={{
                    ...styles.toggleOption,
                    ...(environment === 'SIM' ? styles.toggleOptionActive : {})
                  }}
                  onClick={() => setEnvironment('SIM')}
                >
                  DEMO (SIM)
                </button>
                <button
                  type="button"
                  style={{
                    ...styles.toggleOption,
                    ...(environment === 'LIVE' ? { ...styles.toggleOptionActive, backgroundColor: '#d32f2f' } : {})
                  }}
                  onClick={() => setEnvironment('LIVE')}
                >
                  PRODUCTION (LIVE)
                </button>
              </div>
              {environment === 'LIVE' && (
                <div style={{ ...styles.errorMessage, marginTop: '8px' }}>
                  Attention: En mode LIVE, les trades sont reels!
                </div>
              )}
            </div>

            <div style={styles.buttonGroup}>
              <button
                style={{ ...styles.button, ...styles.buttonSecondary }}
                onClick={() => { onClose(); resetForm(); }}
              >
                Annuler
              </button>
              <button
                style={{
                  ...styles.button,
                  ...styles.buttonPrimary,
                  ...(!appKey || !appSecret || (needsOTP && otpCode.length !== 6) || loading ? styles.buttonDisabled : {})
                }}
                onClick={handleSubmit}
                disabled={!appKey || !appSecret || (needsOTP && otpCode.length !== 6) || loading}
              >
                {loading ? 'En cours...' : (isConfigured ? 'Mettre a jour' : 'Configurer')}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// MODALE SWITCH ENVIRONNEMENT
// =============================================================================

function SwitchEnvModal({ isOpen, onClose, onSubmit, loading, error, currentEnv, otpCode, setOtpCode, otpSent, onRequestOTP, otpLoading }) {
  const newEnv = currentEnv === 'SIM' ? 'LIVE' : 'SIM';
  const newEnvLabel = newEnv === 'LIVE' ? 'PRODUCTION (LIVE)' : 'DEMO (SIM)';

  if (!isOpen) return null;

  return (
    <div style={styles.modal} onClick={onClose}>
      <div style={styles.modalContent} onClick={e => e.stopPropagation()}>
        <h3 style={styles.modalTitle}>Changer d'environnement</h3>

        {newEnv === 'LIVE' ? (
          <div style={styles.errorMessage}>
            <strong>Attention!</strong> Vous allez passer en mode PRODUCTION.<br/>
            Les trades seront reels et affecteront votre compte.
          </div>
        ) : (
          <div style={styles.infoBox}>
            Vous allez passer en mode DEMO (simulation).<br/>
            Les trades seront virtuels.
          </div>
        )}

        {error && <div style={styles.errorMessage}>{error}</div>}

        {!otpSent ? (
          <>
            <button
              style={{ ...styles.button, ...styles.buttonPrimary, width: '100%', marginBottom: '12px' }}
              onClick={onRequestOTP}
              disabled={otpLoading}
            >
              {otpLoading ? 'Envoi en cours...' : 'Recevoir le code OTP'}
            </button>
            <button
              style={{ ...styles.button, ...styles.buttonSecondary, width: '100%' }}
              onClick={onClose}
            >
              Annuler
            </button>
          </>
        ) : (
          <>
            <div style={{ marginBottom: '8px', color: '#888', fontSize: '12px' }}>Code OTP recu sur Telegram:</div>
            <input
              type="text"
              style={styles.otpInput}
              placeholder="000000"
              value={otpCode}
              onChange={e => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              maxLength={6}
              autoFocus
            />
            <div style={styles.buttonGroup}>
              <button
                style={{ ...styles.button, ...styles.buttonSecondary }}
                onClick={onClose}
              >
                Annuler
              </button>
              <button
                style={{
                  ...styles.button,
                  ...(newEnv === 'LIVE' ? styles.buttonDanger : styles.buttonPrimary),
                  ...(otpCode.length !== 6 || loading ? styles.buttonDisabled : {})
                }}
                onClick={() => onSubmit(otpCode, newEnv)}
                disabled={otpCode.length !== 6 || loading}
              >
                {loading ? 'En cours...' : `Passer en ${newEnvLabel}`}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// MODALE DELETE
// =============================================================================

function DeleteModal({ isOpen, onClose, onSubmit, loading, error, service, otpCode, setOtpCode, otpSent, onRequestOTP, otpLoading }) {
  const serviceName = service === 'saxo' ? 'Saxo Bank' : 'Telegram';

  if (!isOpen) return null;

  return (
    <div style={styles.modal} onClick={onClose}>
      <div style={styles.modalContent} onClick={e => e.stopPropagation()}>
        <h3 style={styles.modalTitle}>Supprimer {serviceName}</h3>

        <div style={styles.errorMessage}>
          <strong>Attention!</strong> Cette action est irreversible.<br/>
          Tous les credentials {serviceName} seront supprimes.
        </div>

        {error && <div style={styles.errorMessage}>{error}</div>}

        {!otpSent ? (
          <>
            <button
              style={{ ...styles.button, ...styles.buttonDanger, width: '100%', marginBottom: '12px' }}
              onClick={onRequestOTP}
              disabled={otpLoading}
            >
              {otpLoading ? 'Envoi en cours...' : 'Recevoir le code OTP pour confirmer'}
            </button>
            <button
              style={{ ...styles.button, ...styles.buttonSecondary, width: '100%' }}
              onClick={onClose}
            >
              Annuler
            </button>
          </>
        ) : (
          <>
            <div style={{ marginBottom: '8px', color: '#888', fontSize: '12px' }}>Code OTP recu sur Telegram:</div>
            <input
              type="text"
              style={styles.otpInput}
              placeholder="000000"
              value={otpCode}
              onChange={e => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              maxLength={6}
              autoFocus
            />
            <div style={styles.buttonGroup}>
              <button
                style={{ ...styles.button, ...styles.buttonSecondary }}
                onClick={onClose}
              >
                Annuler
              </button>
              <button
                style={{
                  ...styles.button,
                  ...styles.buttonDanger,
                  ...(otpCode.length !== 6 || loading ? styles.buttonDisabled : {})
                }}
                onClick={() => onSubmit(otpCode, service)}
                disabled={otpCode.length !== 6 || loading}
              >
                {loading ? 'Suppression...' : 'Supprimer definitivement'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// COMPOSANT PRINCIPAL
// =============================================================================

export default function ProfileConfig({ onClose }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Modales
  const [showTelegramModal, setShowTelegramModal] = useState(false);
  const [showSaxoModal, setShowSaxoModal] = useState(false);
  const [showSwitchEnvModal, setShowSwitchEnvModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(null); // 'saxo' ou 'telegram'

  // OTP state
  const [otpCode, setOtpCode] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [otpLoading, setOtpLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [modalError, setModalError] = useState(null);

  // Mode update pour Telegram
  const [telegramUpdateMode, setTelegramUpdateMode] = useState(false);

  // Charger le statut
  const loadStatus = useCallback(async () => {
    try {
      const data = await getConfigStatus();
      setStatus(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  // Reset OTP state
  const resetOtpState = () => {
    setOtpCode('');
    setOtpSent(false);
    setModalError(null);
  };

  // Fermer toutes les modales
  const closeAllModals = () => {
    setShowTelegramModal(false);
    setShowSaxoModal(false);
    setShowSwitchEnvModal(false);
    setShowDeleteModal(null);
    setTelegramUpdateMode(false);
    resetOtpState();
  };

  // Demander OTP
  const handleRequestOTP = async (action) => {
    setOtpLoading(true);
    setModalError(null);

    try {
      await requestOTP(action);
      setOtpSent(true);
    } catch (err) {
      setModalError(err.message);
    } finally {
      setOtpLoading(false);
    }
  };

  // === TELEGRAM ===

  // Setup initial (sans OTP)
  const handleTelegramSetup = async (botToken, chatId) => {
    setActionLoading(true);
    setModalError(null);
    try {
      await setupTelegramInitial(botToken, chatId);
      closeAllModals();
      setSuccess('Telegram configure avec succes!');
      setTimeout(() => setSuccess(null), 3000);
      await loadStatus();
    } catch (err) {
      setModalError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  // Update (avec OTP)
  const handleTelegramUpdate = async (code, config) => {
    setActionLoading(true);
    setModalError(null);
    try {
      await updateTelegramConfig(code, config);
      closeAllModals();
      setSuccess('Telegram mis a jour avec succes!');
      setTimeout(() => setSuccess(null), 3000);
      await loadStatus();
    } catch (err) {
      setModalError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  // === SAXO ===

  // Setup initial (sans OTP)
  const handleSaxoSetup = async (config) => {
    setActionLoading(true);
    setModalError(null);
    try {
      await setupSaxoInitial(
        config.app_key,
        config.app_secret,
        config.environment || 'SIM',
        config.redirect_uri || 'http://localhost:5173'
      );
      closeAllModals();
      setSuccess('Saxo Bank configure avec succes!');
      setTimeout(() => setSuccess(null), 3000);
      await loadStatus();
    } catch (err) {
      setModalError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  // Update (avec OTP)
  const handleSaxoUpdate = async (code, config) => {
    setActionLoading(true);
    setModalError(null);
    try {
      await updateSaxoConfig(code, config);
      closeAllModals();
      setSuccess('Saxo Bank mis a jour avec succes!');
      setTimeout(() => setSuccess(null), 3000);
      await loadStatus();
    } catch (err) {
      setModalError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  // === SWITCH ENV ===

  const handleSwitchEnv = async (code, newEnv) => {
    setActionLoading(true);
    setModalError(null);
    try {
      await switchSaxoEnvironment(code, newEnv);
      closeAllModals();
      setSuccess(`Environnement change vers ${newEnv === 'LIVE' ? 'PRODUCTION' : 'DEMO'}!`);
      setTimeout(() => setSuccess(null), 3000);
      await loadStatus();
    } catch (err) {
      setModalError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  // === DELETE ===

  const handleDelete = async (code, service) => {
    setActionLoading(true);
    setModalError(null);
    try {
      await deleteCredentials(code, service);
      closeAllModals();
      setSuccess(`${service === 'saxo' ? 'Saxo Bank' : 'Telegram'} supprime!`);
      setTimeout(() => setSuccess(null), 3000);
      await loadStatus();
    } catch (err) {
      setModalError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={{ textAlign: 'center', color: '#888', padding: '40px' }}>
          Chargement de la configuration...
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Configuration</h1>
          <p style={styles.subtitle}>Gerez vos credentials et parametres</p>
        </div>
        {onClose && (
          <button
            style={{ ...styles.button, ...styles.buttonSecondary, marginLeft: 'auto' }}
            onClick={onClose}
          >
            Fermer
          </button>
        )}
      </div>

      {/* Messages */}
      {error && <div style={styles.errorMessage}>{error}</div>}
      {success && <div style={styles.successMessage}>{success}</div>}

      {/* Section Telegram */}
      <div style={styles.section}>
        <div style={styles.sectionHeader}>
          <span style={styles.sectionTitle}>Telegram Bot</span>
          <StatusBadge configured={status?.telegram?.configured} />
        </div>

        {status?.telegram?.configured ? (
          <>
            <div style={styles.infoRow}>
              <span style={styles.label}>Bot Token</span>
              <span style={styles.value}>{status.telegram.bot_token_preview}</span>
            </div>
            <div style={styles.infoRow}>
              <span style={styles.label}>Chat ID</span>
              <span style={styles.value}>{status.telegram.chat_id_preview}</span>
            </div>
            <div style={styles.infoRow}>
              <span style={styles.label}>Derniere mise a jour</span>
              <span style={styles.value}>
                {status.telegram.updated_at ? new Date(status.telegram.updated_at).toLocaleString() : '-'}
              </span>
            </div>

            <div style={styles.buttonGroup}>
              <button
                style={{ ...styles.button, ...styles.buttonSecondary }}
                onClick={() => {
                  setTelegramUpdateMode(true);
                  setShowTelegramModal(true);
                }}
              >
                Modifier
              </button>
              <button
                style={{ ...styles.button, ...styles.buttonDanger }}
                onClick={() => setShowDeleteModal('telegram')}
              >
                Supprimer
              </button>
            </div>
          </>
        ) : (
          <>
            <div style={styles.infoBox}>
              Configurez Telegram pour recevoir les notifications et codes OTP.
              Ceci est necessaire pour securiser les modifications de configuration.
            </div>
            <button
              style={{ ...styles.button, ...styles.buttonPrimary }}
              onClick={() => {
                setTelegramUpdateMode(false);
                setShowTelegramModal(true);
              }}
            >
              Configurer Telegram
            </button>
          </>
        )}
      </div>

      {/* Section Saxo Bank */}
      <div style={styles.section}>
        <div style={styles.sectionHeader}>
          <span style={styles.sectionTitle}>Saxo Bank</span>
          <div style={{ display: 'flex', gap: '8px' }}>
            {status?.saxo?.configured && <EnvironmentBadge environment={status.saxo.environment} />}
            <StatusBadge configured={status?.saxo?.configured} />
          </div>
        </div>

        {status?.saxo?.configured ? (
          <>
            <div style={styles.infoRow}>
              <span style={styles.label}>App Key</span>
              <span style={styles.value}>{status.saxo.app_key_preview}</span>
            </div>
            <div style={styles.infoRow}>
              <span style={styles.label}>Environnement</span>
              <span style={styles.value}>
                {status.saxo.environment === 'LIVE' ? 'PRODUCTION (LIVE)' : 'DEMO (SIM)'}
              </span>
            </div>
            <div style={styles.infoRow}>
              <span style={styles.label}>Derniere mise a jour</span>
              <span style={styles.value}>
                {status.saxo.updated_at ? new Date(status.saxo.updated_at).toLocaleString() : '-'}
              </span>
            </div>

            <div style={styles.buttonGroup}>
              <button
                style={{
                  ...styles.button,
                  ...(status.saxo.environment === 'SIM' ? styles.buttonDanger : styles.buttonPrimary)
                }}
                onClick={() => setShowSwitchEnvModal(true)}
                disabled={!status.telegram?.configured}
              >
                {status.saxo.environment === 'SIM' ? 'Passer en PRODUCTION' : 'Passer en DEMO'}
              </button>
              <button
                style={{ ...styles.button, ...styles.buttonSecondary }}
                onClick={() => setShowSaxoModal(true)}
                disabled={!status.telegram?.configured}
              >
                Modifier credentials
              </button>
              <button
                style={{ ...styles.button, ...styles.buttonDanger }}
                onClick={() => setShowDeleteModal('saxo')}
                disabled={!status.telegram?.configured}
              >
                Supprimer
              </button>
            </div>

            {!status.telegram?.configured && (
              <div style={{ ...styles.infoBox, marginTop: '12px' }}>
                Configurez Telegram pour pouvoir modifier les parametres Saxo Bank.
              </div>
            )}
          </>
        ) : (
          <>
            <div style={styles.infoBox}>
              Connectez votre compte Saxo Bank pour acceder aux fonctionnalites de trading.
            </div>
            <button
              style={{
                ...styles.button,
                ...styles.buttonPrimary,
                ...(!status.telegram?.configured ? styles.buttonDisabled : {})
              }}
              onClick={() => setShowSaxoModal(true)}
              disabled={!status.telegram?.configured}
            >
              Configurer Saxo Bank
            </button>
            {!status.telegram?.configured && (
              <div style={{ ...styles.infoBox, marginTop: '12px' }}>
                Configurez d'abord Telegram pour securiser la configuration Saxo.
              </div>
            )}
          </>
        )}
      </div>

      {/* Section Securite */}
      <div style={styles.section}>
        <div style={styles.sectionHeader}>
          <span style={styles.sectionTitle}>Securite</span>
        </div>
        <div style={{ color: '#888', fontSize: '14px', lineHeight: '1.6' }}>
          <p><strong>Protection OTP via Telegram:</strong></p>
          <ul style={{ marginTop: '8px', paddingLeft: '20px' }}>
            <li>Toute modification necessite un code OTP</li>
            <li>Les codes expirent apres 5 minutes</li>
            <li>Maximum 3 tentatives par code</li>
          </ul>
        </div>
      </div>

      {/* === MODALES === */}

      <TelegramModal
        isOpen={showTelegramModal}
        onClose={closeAllModals}
        onSubmit={telegramUpdateMode ? handleTelegramUpdate : handleTelegramSetup}
        loading={actionLoading}
        error={modalError}
        isUpdate={telegramUpdateMode}
        otpCode={otpCode}
        setOtpCode={setOtpCode}
        otpSent={otpSent}
        onRequestOTP={() => handleRequestOTP('update_telegram')}
        otpLoading={otpLoading}
      />

      <SaxoModal
        isOpen={showSaxoModal}
        onClose={closeAllModals}
        onSetup={handleSaxoSetup}
        onUpdate={handleSaxoUpdate}
        loading={actionLoading}
        error={modalError}
        currentEnv={status?.saxo?.environment}
        otpCode={otpCode}
        setOtpCode={setOtpCode}
        otpSent={otpSent}
        onRequestOTP={() => handleRequestOTP('update_saxo')}
        otpLoading={otpLoading}
        isConfigured={status?.saxo?.configured}
      />

      <SwitchEnvModal
        isOpen={showSwitchEnvModal}
        onClose={closeAllModals}
        onSubmit={handleSwitchEnv}
        loading={actionLoading}
        error={modalError}
        currentEnv={status?.saxo?.environment}
        otpCode={otpCode}
        setOtpCode={setOtpCode}
        otpSent={otpSent}
        onRequestOTP={() => handleRequestOTP('switch_environment')}
        otpLoading={otpLoading}
      />

      <DeleteModal
        isOpen={!!showDeleteModal}
        onClose={closeAllModals}
        onSubmit={handleDelete}
        loading={actionLoading}
        error={modalError}
        service={showDeleteModal}
        otpCode={otpCode}
        setOtpCode={setOtpCode}
        otpSent={otpSent}
        onRequestOTP={() => handleRequestOTP('delete_credentials')}
        otpLoading={otpLoading}
      />
    </div>
  );
}
