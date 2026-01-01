const API_BASE = '/api';

export async function analyzeTicker(ticker) {
  try {
    const response = await fetch(`${API_BASE}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticker })
    });

    if (!response.ok) {
      // Try to get error details from response
      const errorData = await response.json().catch(() => ({}));
      const errorMessage = errorData.detail || errorData.error || `HTTP ${response.status}`;
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

export async function analyzeBatch(tickers) {
  try {
    const response = await fetch(`${API_BASE}/analyze-batch`, {
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
// SAXO API
// =============================================================================

export async function getSaxoStatus() {
  const response = await fetch(`${API_BASE}/saxo/status`);
  return response.json();
}

export async function getSaxoAuthUrl() {
  const response = await fetch(`${API_BASE}/saxo/auth/url`);
  if (!response.ok) throw new Error('Failed to get Saxo auth URL');
  return response.json();
}

export async function exchangeSaxoCode(code) {
  const response = await fetch(`${API_BASE}/saxo/auth/callback?code=${code}`);
  if (!response.ok) throw new Error('Failed to exchange Saxo code');
  return response.json();
}

export async function getSaxoPortfolio(accessToken, analyze = true) {
  const response = await fetch(
    `${API_BASE}/saxo/portfolio?access_token=${accessToken}&analyze=${analyze}`
  );
  if (!response.ok) throw new Error('Failed to get Saxo portfolio');
  return response.json();
}

export async function getSaxoOrders(accessToken, status = 'All') {
  const response = await fetch(
    `${API_BASE}/saxo/orders?access_token=${accessToken}&status=${status}`
  );
  if (!response.ok) throw new Error('Failed to get Saxo orders');
  return response.json();
}

export async function getSaxoHistory(accessToken, days = 30) {
  const response = await fetch(
    `${API_BASE}/saxo/history?access_token=${accessToken}&days=${days}`
  );
  if (!response.ok) throw new Error('Failed to get Saxo history');
  return response.json();
}

export async function placeSaxoOrder(accessToken, orderData) {
  const response = await fetch(`${API_BASE}/saxo/orders?access_token=${accessToken}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(orderData)
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    // Handle validation errors from FastAPI
    let errorMessage = 'Failed to place order';
    if (error.detail) {
      if (typeof error.detail === 'string') {
        errorMessage = error.detail;
      } else if (Array.isArray(error.detail)) {
        errorMessage = error.detail.map(e => e.msg || e.message || JSON.stringify(e)).join(', ');
      } else {
        errorMessage = JSON.stringify(error.detail);
      }
    }
    throw new Error(errorMessage);
  }
  return response.json();
}

export async function searchSaxoInstrument(accessToken, query, assetTypes = 'Stock,Etf') {
  const response = await fetch(
    `${API_BASE}/saxo/search?access_token=${accessToken}&query=${encodeURIComponent(query)}&asset_types=${assetTypes}`
  );
  if (!response.ok) throw new Error('Failed to search instrument');
  return response.json();
}

export async function cancelSaxoOrder(accessToken, orderId, accountKey) {
  const response = await fetch(
    `${API_BASE}/saxo/orders/${orderId}?access_token=${accessToken}&account_key=${accountKey}`,
    { method: 'DELETE' }
  );
  if (!response.ok) throw new Error('Failed to cancel order');
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
