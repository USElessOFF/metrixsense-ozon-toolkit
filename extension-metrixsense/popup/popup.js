// ========================================
// ========================================

const CONFIG = {
  BACKEND_URL: 'http://localhost:8000',
  STORAGE_KEYS: {
    TAX_SYSTEM: 'taxSystem',
    AD_BUDGET: 'adBudget',
    LOGISTICS_COST: 'logisticsCost',
    FBO: 'fbo'
  }
};

const elements = {
  status: document.getElementById('connectionStatus'),
  taxSystem: document.getElementById('taxSystem'),
  adBudget: document.getElementById('adBudget'),
  logisticsCost: document.getElementById('logisticsCost'),
  fbo: document.getElementById('fbo'),
  saveBtn: document.getElementById('saveSettings'),
  dashboardBtn: document.getElementById('openDashboard'),
  backendUrl: document.getElementById('backendUrl'),
  toast: document.getElementById('toast')
};

function createToast() {
  if (!document.getElementById('toast')) {
    const toast = document.createElement('div');
    toast.id = 'toast';
    toast.className = 'toast';
    document.body.appendChild(toast);
    return toast;
  }
  return document.getElementById('toast');
}

function showToast(message, type = 'success') {
  const toast = createToast();
  toast.textContent = message;
  toast.className = `toast ${type}`;
  
  setTimeout(() => toast.classList.add('show'), 10);
  
  setTimeout(() => {
    toast.classList.remove('show');
  }, 2500);
}

async function checkBackendHealth() {
  const statusEl = elements.status;
  statusEl.className = 'status checking';
  statusEl.querySelector('.status-text').textContent = 'Проверка подключения...';
  
  try {
    const response = await fetch(`${CONFIG.BACKEND_URL}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(3000)
    });
    
    if (response.ok) {
      statusEl.className = 'status online';
      statusEl.querySelector('.status-text').textContent = '✅ Бэкенд доступен';
      return true;
    } else {
      throw new Error('Бэкенд не отвечает');
    }
  } catch (error) {
    console.error('[MetrixSense] Backend health check failed:', error);
    statusEl.className = 'status offline';
    statusEl.querySelector('.status-text').textContent = '❌ Бэкенд недоступен';
    return false;
  }
}

function loadSettings() {
  chrome.storage.local.get(
    [
      CONFIG.STORAGE_KEYS.TAX_SYSTEM,
      CONFIG.STORAGE_KEYS.AD_BUDGET,
      CONFIG.STORAGE_KEYS.LOGISTICS_COST,
      CONFIG.STORAGE_KEYS.FBO
    ],
    (result) => {
      elements.taxSystem.value = result.taxSystem || 'usn_6';
      elements.adBudget.value = result.adBudget || 5;
      elements.logisticsCost.value = result.logisticsCost || 150;
      elements.fbo.value = result.fbo || 'false';
    }
  );
}

function saveSettings() {
  const data = {
    [CONFIG.STORAGE_KEYS.TAX_SYSTEM]: elements.taxSystem.value,
    [CONFIG.STORAGE_KEYS.AD_BUDGET]: parseFloat(elements.adBudget.value) || 0,
    [CONFIG.STORAGE_KEYS.LOGISTICS_COST]: parseFloat(elements.logisticsCost.value) || 0,
    [CONFIG.STORAGE_KEYS.FBO]: elements.fbo.value
  };
  
  chrome.storage.local.set(data, () => {
    if (chrome.runtime.lastError) {
      showToast('❌ Ошибка сохранения: ' + chrome.runtime.lastError.message, 'error');
    } else {
      showToast('✅ Настройки сохранены!', 'success');
      
      // Уведомляем background о смене настроек
      chrome.runtime.sendMessage({
        type: 'settingsUpdated',
        data: data
      });
    }
  });
}

// Открытие веб-интерфейса в новой вкладке (корень локального бэкенда;
// отдельная страница /dashboard появится с развитием веб-интерфейса)
function openDashboard() {
  chrome.tabs.create({ url: 'http://localhost:8000/' });
}

async function init() {
  await checkBackendHealth();
  
  loadSettings();
  
  elements.backendUrl.textContent = CONFIG.BACKEND_URL;
  
  elements.saveBtn.addEventListener('click', saveSettings);
  elements.dashboardBtn.addEventListener('click', openDashboard);
  
  elements.taxSystem.addEventListener('change', saveSettings);
  elements.fbo.addEventListener('change', saveSettings);
  
  [elements.adBudget, elements.logisticsCost].forEach(input => {
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        saveSettings();
      }
    });
  });
  
  setInterval(checkBackendHealth, 30000);
  
  console.log('[MetrixSense] Popup initialized');
}

document.addEventListener('DOMContentLoaded', init);
