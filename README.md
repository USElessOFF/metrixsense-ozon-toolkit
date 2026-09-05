<div align="center">

# 📊 MetrixSense

**Бесплатная аналитика для продавцов Ozon — локально, из коробки, без подписок**

[![CI](https://github.com/USElessOFF/metrixsense-ozon-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/USElessOFF/metrixsense-ozon-toolkit/actions/workflows/ci.yml)
[![Release](https://github.com/USElessOFF/metrixsense-ozon-toolkit/actions/workflows/release.yml/badge.svg)](https://github.com/USElessOFF/metrixsense-ozon-toolkit/actions/workflows/release.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](backend/requirements.txt)
[![Docker Compose](https://img.shields.io/badge/docker-compose-2496ED.svg)](docker-compose.yml)

Открытая альтернатива платным сервисам: полные метрики магазина
Ozon и поддержка аналитических решений — **на вашем компьютере**. Данные не
покидают вашу машину: SQLite, локальный запуск, никаких облаков.

</div>

---

## ✨ Возможности

- 📦 **Секции аналитики** — цены и комиссии, карточки товаров (габариты, объёмный вес),
  финансовые начисления, рейтинг продавца — каждый блок доступен отдельно, без ожидания полного отчёта
- 📈 **Полный отчёт в фоне** — собирается асинхронно, статус и скачивание в любой момент
- 💰 **Юнит-экономика** — налоговые режимы (УСН 6%, УСН «доходы − расходы» и др.),
  логистика, рекламный бюджет, доля себестоимости
- 📤 **Экспорт** — Excel и CSV по каждому отчёту
- 🧩 **Расширение для Chrome** — аналитика прямо на страницах Ozon
- 🔐 **Локальность** — ваши API-ключи и данные продаж хранятся только у вас (SQLite + Alembic)

## 🚀 Быстрый старт

### Windows — Docker (рекомендуется)

Одна команда в PowerShell — скрипт сам поставит WSL2 и Docker Desktop (тихо),
попросит одну перезагрузку, затем скачает и запустит MetrixSense:

```powershell
irm https://raw.githubusercontent.com/USElessOFF/metrixsense-ozon-toolkit/main/install_windows_docker.ps1 | iex
```

> Понадобятся права администратора и **одна перезагрузка**. Docker Desktop
> бесплатен для личного использования и малого бизнеса (< 250 сотрудников).
> После перезагрузки установка продолжится автоматически.

### Windows — без Docker и WSL2 (нативно)

Один процесс Python, ничего лишнего — подходит, если не хочется ставить WSL2
или Docker Desktop лицензионно недоступен:

```powershell
irm https://raw.githubusercontent.com/USElessOFF/metrixsense-ozon-toolkit/main/install_windows.ps1 | iex
```

### Linux

```bash
curl -fsSL https://raw.githubusercontent.com/USElessOFF/metrixsense-ozon-toolkit/main/install_linux.sh | bash
```

### Ручная установка (любая ОС)

```bash
git clone https://github.com/USElessOFF/metrixsense-ozon-toolkit.git
cd metrixsense

python -m venv .venv
# Windows:  .venv\Scripts\pip install -r backend\requirements.txt
# Linux/macOS:
source .venv/bin/activate
pip install -r backend/requirements.txt

uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Или через Docker: `docker compose up -d --build` → http://localhost:8080

### Куда смотреть после запуска

| URL | Что это |
|---|---|
| `http://localhost:8080` (Docker) или `http://127.0.0.1:8000` (нативно) | Веб-интерфейс |
| `/docs` | Интерактивная API-документация (Swagger UI) |
| `/redoc` | API-документация (ReDoc) |
| `/health` | Проверка работоспособности |

## 🧭 Первые шаги

1. Откройте веб-интерфейс и войдите: **metrixsense / metrixsense**
   *(смените пароль — задайте `DEFAULT_PASSWORD` в `backend/.env`)*
2. Онбординг: введите **Ozon Seller API** ключи ([где взять](https://seller.ozon.ru/app/settings/api-keys)) — обязательны
3. Опционально: **Performance API** ключи ([где взять](https://performance.ozon.ru/app/settings/api-keys)) — для рекламных данных
4. Сверьте настройки юнит-экономики: налоговый режим, логистика, себестоимость
5. Соберите первый отчёт 🎉

## ⚠️ Возможные проблемы при установке

| Проблема | Решение |
|---|---|
| PowerShell: «выполнение сценариев отключено» | Возникает при запуске сохранённого `.ps1` двойным кликом. One-liner `irm \| iex` работает и без этого. Либо выполните: `Set-ExecutionPolicy -Scope Process Bypass` |
| Установка «зависла» на WSL2 | Нужна перезагрузка. Скрипт планирует автопродолжение (RunOnce) — просто перезагрузитесь и подтвердите UAC |
| «Виртуализация отключена» | Включите VT-x/AMD-V в BIOS/UEFI (Intel VT-x / AMD SVM), затем перезапустите установщик |
| `winget` не найден (старые/LTSC-сборки) | Установщики сами скачают Python / Docker с официальных сайтов напрямую |
| Порт 8000/8080 занят | Освободите порт или смените `PORT` в `backend/.env` / секцию `ports` в `docker-compose.yml` |
| SmartScreen / антивирус предупреждает | «Выполнить в любом случае». Скрипты скачивают только с github.com, python.org, docker.com |
| Лицензия Docker Desktop | Бесплатно для физлиц и бизнеса < 250 сотрудников и < $10M выручки. Иначе — используйте нативный установщик |
| Docker: permission denied (Linux) | Перелогиньтесь после установки (группа docker) или используйте sudo |

## 🧩 Расширение для Chrome

1. Откройте `chrome://extensions`
2. Включите **Режим разработчика**
3. «Загрузить распакованное расширение» → папка `extension-metrixsense`
4. Убедитесь, что MetrixSense запущен — расширение работает с локальным бэкендом

## 🏗 Архитектура

```
┌──────────────┐  /api /auth /health   ┌──────────────────────────────┐
│   Browser /  │ ─────────────────────▶│  nginx (Docker) или FastAPI  │
│  Extension   │                       └───────────────┬──────────────┘
└──────────────┘                                       ▼
                                         ┌──────────────────────────────┐
                                         │  FastAPI (backend/app)       │
                                         │  routers → services →        │
                                         │  adapters → models           │
                                         └───────┬─────────────┬────────┘
                                                 ▼             ▼
                                         ┌────────────┐  ┌──────────────────┐
                                         │ SQLite WAL │  │ Ozon Seller API  │
                                         │ (alembic)  │  │ Ozon Perf. API   │
                                         └────────────┘  └──────────────────┘
```

| Компонент | Технологии |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2 (async), Alembic, httpx, structlog, pandas |
| База данных | SQLite (WAL) — нулевая настройка; схема через Alembic-миграции |
| Frontend | Статика в `web/` |
| Расширение | Chrome MV3 (`extension-metrixsense`) |
| CI/CD | GitHub Actions: тесты (py3.11/3.12) + ruff + docker build; релизы — ghcr.io |

Слои backend: `app/routers` (HTTP) → `app/services/report_service` (сборка отчётов)
→ `app/ozon_seller`, `app/ozon_performance` (клиенты Ozon API) → `app/adapters`
(доступ к данным) → `app/models` (SQLAlchemy). Фоновые задачи — `app/get_bg_tasks`,
кэш аналитики — `models/analytics_cache`.

## 🗺 Roadmap

- [x] Backend: отчёты, секции, юнит-экономика, миграции Alembic
- [x] Установка «из коробки»: Windows (Docker / нативно) и Linux
- [x] Расширение для Chrome (MVP)
- [ ] Эндпоинт аналитики товара `/api/analytics/product` для виджета расширения
- [ ] Веб-интерфейс
- [ ] Графики динамики, DRR, ABC-анализ
- [ ] Профиль PostgreSQL для серверной установки
- [ ] i18n веб-интерфейса (ru/en)

## 🛠 Разработка

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r backend/requirements.txt

python -m pytest backend/tests -m "not live" -q   # тесты (live-тесты: pytest -m live)
ruff check backend                                 # линтер
uvicorn backend.app.main:app --reload              # dev-сервер
```

Утилита чистки логов: `python backend/scripts/format_log.py --latest`.

## 📄 Лицензия и дисклеймер

[MIT](LICENSE). MetrixSense **не аффилирован** с Ozon и не является официальным
продуктом компании. Использование API Ozon регулируется условиями вашей
аккредитации продавца.

