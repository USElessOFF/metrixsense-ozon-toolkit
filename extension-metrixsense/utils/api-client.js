// ========================================
// MetrixSense - API Client (утилита)
// Общение с локальным бэкендом MetrixSense.
//
// ВАЖНО: вызывать из расширения (popup / background service worker),
// а не из content script — у страниц Ozon другой origin, и запросы
// к localhost блокируются CORS.
//
// Реализованные эндпоинты бэкенда: /api/settings, /health.
// Эндпоинты /analytics/product, /products, /orders, /finance —
// планируются (см. README, Roadmap).
// ========================================

const BACKEND_ORIGIN = 'http://localhost:8000';
const API_BASE = `${BACKEND_ORIGIN}/api`;

class MetrixAPI {
  constructor(baseUrl = API_BASE) {
    this.baseUrl = baseUrl;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const defaultOptions = {
      headers: {
        'Content-Type': 'application/json',
        'X-Client-Name': 'MetrixSense-Extension',
        'X-Client-Version': '1.0.0'
      },
      credentials: 'include', // JWT в httpOnly cookie
      signal: AbortSignal.timeout(10000)
    };

    const mergedOptions = {
      ...defaultOptions,
      ...options,
      headers: {
        ...defaultOptions.headers,
        ...(options.headers || {})
      }
    };

    try {
      const response = await fetch(url, mergedOptions);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      if (error.name === 'AbortError') {
        throw new Error('Превышено время ожидания ответа от бэкенда');
      }
      throw error;
    }
  }

  // Проверка здоровья — корень бэкенда, не /api
  async health() {
    const response = await fetch(`${BACKEND_ORIGIN}/health`, {
      signal: AbortSignal.timeout(3000)
    });
    return response.ok;
  }

  // --- Реализованные эндпоинты бэкенда ---

  async getSettings() {
    return this.request('/settings');
  }

  async updateSettings(settings) {
    return this.request('/settings', {
      method: 'PUT',
      body: JSON.stringify(settings)
    });
  }

  // --- Планируемые эндпоинты (README, Roadmap) ---

  async analyzeProduct(productData, userSettings) {
    return this.request('/analytics/product', {
      method: 'POST',
      body: JSON.stringify({
        product: productData,
        settings: userSettings
      })
    });
  }

  async getProducts(limit = 50, offset = 0) {
    return this.request(`/products?limit=${limit}&offset=${offset}`);
  }

  async getOrders(dateFrom, dateTo, status = null) {
    let url = `/orders?date_from=${dateFrom}&date_to=${dateTo}`;
    if (status) url += `&status=${status}`;
    return this.request(url);
  }

  async getFinance(dateFrom, dateTo) {
    return this.request(`/finance?date_from=${dateFrom}&date_to=${dateTo}`);
  }
}

const api = new MetrixAPI();

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { MetrixAPI, api };
}
