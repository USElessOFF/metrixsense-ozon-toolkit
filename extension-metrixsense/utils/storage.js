// ========================================
// ========================================

const STORAGE_KEYS = {
  TAX_SYSTEM: 'taxSystem',
  AD_BUDGET: 'adBudget',
  LOGISTICS_COST: 'logisticsCost',
  FBO: 'fbo',
  USER_ID: 'userId',
  INSTALL_DATE: 'installDate'
};

class MetrixStorage {
  static async get(key, defaultValue = null) {
    return new Promise((resolve) => {
      chrome.storage.local.get([key], (result) => {
        resolve(result[key] !== undefined ? result[key] : defaultValue);
      });
    });
  }

  static async getMultiple(keys) {
    return new Promise((resolve) => {
      chrome.storage.local.get(keys, (result) => {
        resolve(result);
      });
    });
  }

  static async set(key, value) {
    return new Promise((resolve) => {
      chrome.storage.local.set({ [key]: value }, () => {
        resolve();
      });
    });
  }

  static async setMultiple(data) {
    return new Promise((resolve) => {
      chrome.storage.local.set(data, () => {
        resolve();
      });
    });
  }

  static async remove(key) {
    return new Promise((resolve) => {
      chrome.storage.local.remove([key], () => {
        resolve();
      });
    });
  }

  static async clear() {
    return new Promise((resolve) => {
      chrome.storage.local.clear(() => {
        resolve();
      });
    });
  }

  static async getAllSettings() {
    const result = await this.getMultiple([
      STORAGE_KEYS.TAX_SYSTEM,
      STORAGE_KEYS.AD_BUDGET,
      STORAGE_KEYS.LOGISTICS_COST,
      STORAGE_KEYS.FBO
    ]);
    
    return {
      taxSystem: result.taxSystem || 'usn_6',
      adBudget: parseFloat(result.adBudget) || 0,
      logisticsCost: parseFloat(result.logisticsCost) || 0,
      fbo: result.fbo === 'true'
    };
  }

  static async saveAllSettings(settings) {
    const data = {
      [STORAGE_KEYS.TAX_SYSTEM]: settings.taxSystem || 'usn_6',
      [STORAGE_KEYS.AD_BUDGET]: settings.adBudget || 0,
      [STORAGE_KEYS.LOGISTICS_COST]: settings.logisticsCost || 0,
      [STORAGE_KEYS.FBO]: settings.fbo ? 'true' : 'false'
    };
    
    await this.setMultiple(data);
    
    // Уведомляем background
    chrome.runtime.sendMessage({
      type: 'settingsUpdated',
      data: settings
    });
  }

  // Генерация ID пользователя (для аналитики, анонимно)
  static async getUserId() {
    let userId = await this.get(STORAGE_KEYS.USER_ID);
    if (!userId) {
      userId = 'user_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
      await this.set(STORAGE_KEYS.USER_ID, userId);
    }
    return userId;
  }

  static async getInstallDate() {
    let date = await this.get(STORAGE_KEYS.INSTALL_DATE);
    if (!date) {
      date = new Date().toISOString();
      await this.set(STORAGE_KEYS.INSTALL_DATE, date);
    }
    return date;
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { MetrixStorage, STORAGE_KEYS };
}
