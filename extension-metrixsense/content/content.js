// ========================================
// ========================================

const CONFIG = {
  BACKEND_URL: 'http://localhost:8000',
  WIDGET_ID: 'metrix-sense-widget',
  DEBUG: true
};

function log(...args) {
  if (CONFIG.DEBUG) {
    console.log('[MetrixSense]', ...args);
  }
}

function detectPage() {
  const url = window.location.href;
  if (url.includes('/product/')) return 'product';
  if (url.includes('/my/')) return 'dashboard';
  if (url.includes('/cart')) return 'cart';
  return 'unknown';
}

function parseProductPage() {
  log('Парсинг карточки товара...');
  
  const data = {
    url: window.location.href,
    name: null,
    price: null,
    oldPrice: null,
    rating: null,
    reviews: null,
    seller: null,
    characteristics: {},
    images: [],
    category: null
  };

  const titleEl = document.querySelector('[data-widget="webProductHeading"] h1, h1[data-qa="product-name"]');
  if (titleEl) data.name = titleEl.textContent.trim();

  const priceEl = document.querySelector('[data-widget="webPrice"] .jqF, ._1vC3e, [data-qa="product-price"]');
  if (priceEl) {
    const priceText = priceEl.textContent.replace(/\s/g, '').replace(/[^\d]/g, '');
    data.price = parseInt(priceText) || null;
  }

  const oldPriceEl = document.querySelector('[data-widget="webPrice"] .c3gF, ._1_hie, [data-qa="product-old-price"]');
  if (oldPriceEl) {
    const priceText = oldPriceEl.textContent.replace(/\s/g, '').replace(/[^\d]/g, '');
    data.oldPrice = parseInt(priceText) || null;
  }

  const ratingEl = document.querySelector('[data-widget="webRating"] ._8wBf, [data-qa="product-rating"]');
  if (ratingEl) data.rating = parseFloat(ratingEl.textContent.replace(',', '.')) || null;

  const reviewsEl = document.querySelector('[data-widget="webRating"] + span, [data-qa="product-reviews-count"]');
  if (reviewsEl) {
    const text = reviewsEl.textContent.replace(/\s/g, '').replace(/[^\d]/g, '');
    data.reviews = parseInt(text) || null;
  }

  const sellerEl = document.querySelector('[data-widget="webSeller"] a, [data-qa="seller-name"]');
  if (sellerEl) data.seller = sellerEl.textContent.trim();

  document.querySelectorAll('[data-widget="webCharacteristics"] .tsBodyL, ._1kU3c').forEach(el => {
    const keyEl = el.querySelector('.tsBodyL:first-child, ._1JXhu:first-child');
    const valEl = el.querySelector('.tsBodyL:last-child, ._1JXhu:last-child');
    if (keyEl && valEl) {
      const key = keyEl.textContent.trim().replace(/:$/, '');
      const value = valEl.textContent.trim();
      data.characteristics[key] = value;
    }
  });

  document.querySelectorAll('[data-widget="webGallery"] img, ._1G3Sg img').forEach(img => {
    if (img.src) data.images.push(img.src);
  });

  log('Данные товара:', data);
  return data;
}

function getUserSettings() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['taxSystem', 'adBudget', 'logisticsCost', 'fbo'], (result) => {
      resolve({
        taxSystem: result.taxSystem || 'usn_6',
        adBudget: parseFloat(result.adBudget) || 0,
        logisticsCost: parseFloat(result.logisticsCost) || 0,
        isFBO: result.fbo === 'true'
      });
    });
  });
}

// Проверка доступности бэкенда — через background service worker:
// у content script origin — страница Ozon, и прямой fetch к localhost:8000
// блокируется CORS. Background уже опрашивает /health каждые 30 секунд.
async function checkBackendHealth() {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ type: 'getStatus' }, (response) => {
      resolve(Boolean(response && response.status === 'online'));
    });
  });
}

// Запрос аналитики — через background service worker (host_permissions на
// localhost:8000, без ограничений CORS). Эндпоинт /api/analytics/product
// пока в планах бэкенда (см. README, Roadmap) — виджет корректно покажет
// ошибку, пока эндпоинт не реализован.
async function fetchAnalytics(productData) {
  const isHealthy = await checkBackendHealth();
  if (!isHealthy) {
    throw new Error('Бэкенд MetrixSense не отвечает. Проверьте, запущен ли сервер.');
  }

  const userSettings = await getUserSettings();

  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(
      {
        type: 'analyzeProduct',
        payload: {
          product: {
            url: productData.url,
            name: productData.name,
            price: productData.price,
            old_price: productData.oldPrice,
            rating: productData.rating,
            reviews: productData.reviews,
            category: productData.category,
            characteristics: productData.characteristics
          },
          settings: userSettings
        }
      },
      (response) => {
        if (chrome.runtime.lastError) {
          log('Ошибка обмена с background:', chrome.runtime.lastError.message);
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        if (!response || !response.ok) {
          const message = (response && response.error) || 'Ошибка расчета аналитики';
          log('Ошибка получения аналитики:', message);
          reject(new Error(message));
          return;
        }
        resolve(response.data);
      }
    );
  });
}

// Рендеринг виджета
function renderWidget(analytics, container) {
  const { current_price, commission, logistics, profit, margin, roi, recommendations } = analytics;

  container.innerHTML = `
    <!-- Сетка метрик -->
    <div class="metrix-grid">
      <div class="metrix-card blue">
        <div class="metrix-card-label">Цена на Ozon</div>
        <div class="metrix-card-value">${current_price.toLocaleString('ru-RU')} <span class="currency">₽</span></div>
      </div>
      <div class="metrix-card orange">
        <div class="metrix-card-label">Комиссия Ozon</div>
        <div class="metrix-card-value">${commission.toLocaleString('ru-RU')} <span class="currency">₽</span></div>
      </div>
      <div class="metrix-card purple">
        <div class="metrix-card-label">Логистика</div>
        <div class="metrix-card-value">${logistics.toLocaleString('ru-RU')} <span class="currency">₽</span></div>
      </div>
      <div class="metrix-card ${profit > 0 ? 'green' : 'red'}">
        <div class="metrix-card-label">Чистая прибыль</div>
        <div class="metrix-card-value">${profit.toLocaleString('ru-RU')} <span class="currency">₽</span></div>
      </div>
    </div>

    <!-- Дополнительная аналитика -->
    <div class="metrix-additional">
      <div class="metrix-row">
        <span class="metrix-row-label">Маржинальность</span>
        <span class="metrix-row-value ${margin > 20 ? 'positive' : 'negative'}">
          ${margin.toFixed(1)}%
        </span>
      </div>
      <div class="metrix-progress-bar">
        <div class="metrix-progress-fill" style="width: ${Math.min(margin, 100)}%;"></div>
      </div>
      <div class="metrix-row">
        <span class="metrix-row-label">ROI</span>
        <span class="metrix-row-value ${roi > 0 ? 'positive' : 'negative'}">
          ${roi > 0 ? '+' : ''}${roi.toFixed(1)}%
        </span>
      </div>
      ${recommendations ? `
      <div class="metrix-row" style="border-bottom: none; padding-top: 8px;">
        <span class="metrix-row-label" style="font-size: 11px; color: #8a9bb0;">💡 Рекомендация</span>
        <span class="metrix-row-value" style="font-size: 12px; font-weight: 400; color: #6b7a8f;">
          ${recommendations}
        </span>
      </div>
      ` : ''}
    </div>
  `;
}

async function createWidget() {
  if (document.getElementById(CONFIG.WIDGET_ID)) {
    const existing = document.getElementById(CONFIG.WIDGET_ID);
    if (existing.classList.contains('hidden')) {
      existing.classList.remove('hidden');
      existing.classList.add('visible');
    }
    return;
  }

  const productData = parseProductPage();
  if (!productData.price) {
    log('Не удалось получить цену товара');
    return;
  }

  const widget = document.createElement('div');
  widget.id = CONFIG.WIDGET_ID;
  widget.className = 'visible';
  widget.innerHTML = `
    <div class="metrix-widget-header">
      <div class="metrix-widget-title">
        📊 MetrixSense
        <span class="badge">BETA</span>
      </div>
      <button class="metrix-close-btn" id="metrix-close-widget">✕</button>
    </div>
    <div class="metrix-widget-body" id="metrix-widget-body">
      <div class="metrix-loader">
        <div class="metrix-spinner"></div>
        <span class="metrix-loader-text">Расчет юнит-экономики...</span>
      </div>
    </div>
    <div class="metrix-widget-footer">
      <span class="hint">
        <span class="metrix-status-dot online" id="metrix-status-dot"></span>
        <strong>Локально</strong> · Данные не передаются
      </span>
      <span class="hint">v1.0.0</span>
    </div>
  `;

  document.body.appendChild(widget);

  document.getElementById('metrix-close-widget').addEventListener('click', () => {
    widget.classList.remove('visible');
    widget.classList.add('hidden');
  });

  const body = document.getElementById('metrix-widget-body');
  try {
    const analytics = await fetchAnalytics(productData);
    renderWidget(analytics, body);
  } catch (error) {
    body.innerHTML = `
      <div class="metrix-error">
        <div class="metrix-error-icon">🔌</div>
        <div class="metrix-error-text">${error.message}</div>
        <div class="metrix-error-hint">Убедитесь, что бэкенд MetrixSense запущен</div>
        <button class="metrix-retry-btn" onclick="location.reload()">🔄 Обновить</button>
      </div>
    `;
    const dot = document.getElementById('metrix-status-dot');
    if (dot) {
      dot.className = 'metrix-status-dot offline';
    }
  }
}

function init() {
  const pageType = detectPage();
  log('Тип страницы:', pageType);

  if (pageType === 'product') {
    // Ждем загрузки контента
    setTimeout(createWidget, 1500);
  }
}

if (document.readyState === 'complete') {
  init();
} else {
  document.addEventListener('DOMContentLoaded', init);
}

// Отслеживание навигации в SPA
let lastUrl = location.href;
const observer = new MutationObserver(() => {
  const url = location.href;
  if (url !== lastUrl) {
    lastUrl = url;
    if (url.includes('/product/')) {
      const oldWidget = document.getElementById(CONFIG.WIDGET_ID);
      if (oldWidget) oldWidget.remove();
      setTimeout(createWidget, 1500);
    }
  }
});
observer.observe(document, { subtree: true, childList: true });
