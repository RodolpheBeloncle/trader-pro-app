const API_BASE = '/api';

// Helper to extract error message from FastAPI response
function extractErrorMessage(error, fallback) {
  if (!error) return fallback;
  if (typeof error === 'string') return error;
  if (error.detail) {
    if (typeof error.detail === 'string') return error.detail;
    if (Array.isArray(error.detail)) {
      return error.detail.map(e => e.msg || e.message || JSON.stringify(e)).join(', ');
    }
    if (typeof error.detail === 'object') return error.detail.message || JSON.stringify(error.detail);
  }
  if (error.error) return error.error;
  if (error.message) return error.message;
  return fallback;
}

export async function analyzeTicker(ticker) {
  try {
    // Backend uses GET with query parameter
    const response = await fetch(`${API_BASE}/stocks/analyze?ticker=${encodeURIComponent(ticker)}`);

    if (!response.ok) {
      // Try to get error details from response
      const errorData = await response.json().catch(() => ({}));
      const errorMessage = extractErrorMessage(errorData, `HTTP ${response.status}`);
      throw new Error(`Failed to analyze ${ticker}: ${errorMessage}`);
    }

    return response.json();
  } catch (error) {
    // Network error or backend not running
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      throw new Error(`Cannot connect to server. Make sure the backend is running on port 8000.`);
    }
    throw error;
  }
}

// Recherche de tickers par nom ou symbole
export async function searchTickers(query, assetType = 'stocks') {
  try {
    const response = await fetch(`${API_BASE}/stocks/search?query=${encodeURIComponent(query)}&asset_type=${assetType}`);
    if (!response.ok) {
      return { results: [] };
    }
    return response.json();
  } catch (error) {
    console.error('Search error:', error);
    return { results: [] };
  }
}

export async function analyzeBatch(tickers) {
  try {
    const response = await fetch(`${API_BASE}/stocks/analyze/batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tickers })
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(`Failed to analyze batch: ${errorData.detail || 'Unknown error'}`);
    }

    return response.json();
  } catch (error) {
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      throw new Error(`Cannot connect to server. Make sure the backend is running.`);
    }
    throw error;
  }
}

export async function getMarkets() {
  const response = await fetch(`${API_BASE}/markets`);
  if (!response.ok) throw new Error('Failed to fetch markets');
  return response.json();
}

export async function getMarketTickers(market, limit = 10, offset = 0) {
  const response = await fetch(`${API_BASE}/markets/${market}?limit=${limit}&offset=${offset}`);
  if (!response.ok) throw new Error(`Failed to fetch market ${market}`);
  return response.json();
}

// =============================================================================
// SAXO API - Simplified (SaxoPortfolio component handles most calls directly)
// =============================================================================

export async function getSaxoStatus() {
  const response = await fetch(`${API_BASE}/saxo/status`);
  return response.json();
}

// =============================================================================
// DATA SOURCES API
// =============================================================================

export async function getDataSources() {
  const response = await fetch(`${API_BASE}/sources`);
  if (!response.ok) throw new Error('Failed to get data sources');
  return response.json();
}

export async function getSourcesHealth() {
  const response = await fetch(`${API_BASE}/sources/status`);
  if (!response.ok) throw new Error('Failed to get sources health');
  return response.json();
}

export async function switchDataSource(source) {
  const response = await fetch(`${API_BASE}/sources/switch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source })
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to switch source');
  }
  return response.json();
}

export async function getStreamerStats() {
  const response = await fetch(`${API_BASE}/sources/stats`);
  if (!response.ok) throw new Error('Failed to get streamer stats');
  return response.json();
}

// =============================================================================
// CONFIGURATION API
// =============================================================================

export async function getConfigStatus() {
  const response = await fetch(`${API_BASE}/config/status`);
  if (!response.ok) throw new Error('Failed to get config status');
  return response.json();
}

export async function requestOTP(action) {
  const response = await fetch(`${API_BASE}/config/otp/request`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action })
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to request OTP');
  }
  return response.json();
}

export async function setupTelegramInitial(botToken, chatId) {
  const response = await fetch(
    `${API_BASE}/config/telegram/setup?bot_token=${encodeURIComponent(botToken)}&chat_id=${encodeURIComponent(chatId)}`,
    { method: 'POST' }
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to setup Telegram');
  }
  return response.json();
}

export async function setupSaxoInitial(appKey, appSecret, environment = 'SIM', redirectUri = 'http://localhost:5173') {
  const params = new URLSearchParams({
    app_key: appKey,
    app_secret: appSecret,
    environment,
    redirect_uri: redirectUri
  });
  const response = await fetch(`${API_BASE}/config/saxo/setup?${params}`, {
    method: 'POST'
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to setup Saxo'));
  }
  return response.json();
}

export async function updateSaxoConfig(otpCode, config) {
  const response = await fetch(`${API_BASE}/config/saxo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ otp_code: otpCode, ...config })
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to update Saxo config'));
  }
  return response.json();
}

export async function updateTelegramConfig(otpCode, config) {
  const response = await fetch(`${API_BASE}/config/telegram`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ otp_code: otpCode, ...config })
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to update Telegram config'));
  }
  return response.json();
}

export async function switchSaxoEnvironment(otpCode, environment) {
  const response = await fetch(`${API_BASE}/config/environment`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ otp_code: otpCode, environment })
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to switch environment'));
  }
  return response.json();
}

export async function deleteCredentials(otpCode, service) {
  const response = await fetch(`${API_BASE}/config/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ otp_code: otpCode, service })
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to delete credentials'));
  }
  return response.json();
}

export async function cancelOTP(action) {
  const response = await fetch(`${API_BASE}/config/otp/cancel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action })
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error, 'Failed to cancel OTP'));
  }
  return response.json();
}

// =============================================================================
// CSV EXPORT
// =============================================================================

// Client-side CSV export - uses already loaded data
export function exportCSVFromData(stocks) {
  if (!stocks || stocks.length === 0) return;

  const headers = [
    'ticker', 'name', 'currency', 'current_price',
    'perf_3m', 'perf_6m', 'perf_1y', 'perf_3y', 'perf_5y',
    'volatility', 'dividend_yield', 'is_resilient', 'sector', 'market_cap'
  ];

  const rows = stocks.map(stock => [
    stock.ticker || '',
    `"${stock.name || ''}"`,
    stock.currency || '',
    stock.current_price || '',
    stock.perf_3m || '',
    stock.perf_6m || '',
    stock.perf_1y || '',
    stock.perf_3y || '',
    stock.perf_5y || '',
    stock.volatility || '',
    stock.dividend_yield || '',
    stock.is_resilient || '',
    `"${stock.sector || ''}"`,
    stock.market_cap || ''
  ].join(';'));

  const csv = [headers.join(';'), ...rows].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'stock_analysis.csv';
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  a.remove();
}
