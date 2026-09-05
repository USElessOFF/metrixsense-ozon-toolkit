// ========================================
// ========================================

const CONFIG = {
  BACKEND_URL: 'http://localhost:8000',
  CHECK_INTERVAL: 30000 // 30 секунд
};

let backendStatus = 'checking';
let settingsCache = {};

async function checkBackendHealth() {
  try {
    const response = await fetch(`${CONFIG.BACKEND_URL}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(3000)
    });
    
    backendStatus = response.ok ? 'online' : 'offline';
  } catch (error) {
    console.error('[MetrixSense] Health check failed:', error);
    backendStatus = 'offline';
  }
  
  updateBadge();
  return backendStatus;
}

function updateBadge() {
  const text = backendStatus === 'online' ? '✓' : '✕';
  const color = backendStatus === 'online' ? '#0d9488' : '#dc2626';

  chrome.action.setBadgeText({ text });
  chrome.action.setBadgeBackgroundColor({ color });
  // Отдельных иконок "-off" в icons/ нет — информирует бейдж
}

function loadSettings() {
  chrome.storage.local.get(
    ['taxSystem', 'adBudget', 'logisticsCost', 'fbo'],
    (result) => {
      settingsCache = {
        taxSystem: result.taxSystem || 'usn_6',
        adBudget: parseFloat(result.adBudget) || 0,
        logisticsCost: parseFloat(result.logisticsCost) || 0,
        fbo: result.fbo === 'true'
      };
      console.log('[MetrixSense] Settings loaded:', settingsCache);
    }
  );
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'getSettings') {
    sendResponse(settingsCache);
    return true;
  }
  
  if (request.type === 'settingsUpdated') {
    settingsCache = request.data;
    console.log('[MetrixSense] Settings updated:', settingsCache);
    sendResponse({ success: true });
    return true;
  }
  
  if (request.type === 'getStatus') {
    sendResponse({ status: backendStatus });
    return true;
  }
  
  if (request.type === 'refreshHealth') {
    checkBackendHealth().then((status) => {
      sendResponse({ status });
    });
    return true;
  }

  // Анализ товара: fetch выполняется в service worker — у него есть
  // host_permissions на localhost:8000, поэтому CORS не мешает
  // (из content script на ozon.ru запросы к localhost блокируются).
  // Эндпоинт /api/analytics/product — в планах бэкенда (README, Roadmap):
  // до его реализации виджет покажет ошибку с подсказкой запустить сервер.
  if (request.type === 'analyzeProduct') {
    (async () => {
      try {
        const response = await fetch(`${CONFIG.BACKEND_URL}/api/analytics/product`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(request.payload)
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          sendResponse({ ok: false, error: data.detail || `HTTP ${response.status}` });
        } else {
          sendResponse({ ok: true, data });
        }
      } catch (error) {
        sendResponse({ ok: false, error: 'Бэкенд MetrixSense не отвечает. Запустите сервер.' });
      }
    })();
    return true; // асинхронный sendResponse
  }
});

chrome.runtime.onInstalled.addListener(() => {
  console.log('[MetrixSense] Extension installed');
  loadSettings();
  
  chrome.storage.local.get(['taxSystem'], (result) => {
    if (!result.taxSystem) {
      chrome.storage.local.set({
        taxSystem: 'usn_6',
        adBudget: 5,
        logisticsCost: 150,
        fbo: 'false'
      });
    }
  });
  
  setTimeout(checkBackendHealth, 1000);
});

setInterval(checkBackendHealth, CONFIG.CHECK_INTERVAL);

loadSettings();

console.log('[MetrixSense] Background service worker started');
