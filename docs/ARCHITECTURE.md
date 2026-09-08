# Архитектура MetrixSense

Документ для контрибьюторов. Пользовательская инструкция — в [README](../README.md).

## Общая схема

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

## Компоненты

| Компонент | Технологии |
|---|---|
| Backend | Python 3.12+, FastAPI, SQLAlchemy 2 (async), Alembic, httpx, structlog, pandas |
| База данных | SQLite (WAL) — нулевая настройка; схема через Alembic-миграции |
| Frontend | React 19 + TypeScript, Vite; сборка коммитится в `web/dist/` |
| Расширение | Chrome MV3 (`extension-metrixsense`) |
| CI/CD | GitHub Actions: тесты (py3.12/3.13), ruff, фронт-проверки, docker build; релизы — ghcr.io |

## Слои backend

`app/routers` (HTTP) → `app/services/report_service` (сборка отчётов)
→ `app/ozon_seller`, `app/ozon_performance` (клиенты Ozon API) → `app/adapters`
(доступ к данным) → `app/models` (SQLAlchemy). Фоновые задачи — `app/get_bg_tasks`,
кэш аналитики — `models/analytics_cache`.

## Frontend

Исходники — в `web/`, точка входа `src/main.tsx`. Сборка Vite пишется в
`web/dist/`, и именно её раздают FastAPI (нативный запуск) и nginx (Docker).

Ключевые решения:

- **Hash-роутинг** (`HashRouter`) — deep links работают без настроек fallback'а
  ни в FastAPI StaticFiles, ни в nginx; страницы = файлы в `src/pages/`.
- **Сборка в репозитории** — пользователю не нужен Node.js: `git clone` → uvicorn →
  веб-интерфейс работает. Node требуется только для изменений фронтенда.
- **Минимум зависимостей** — react, react-dom, react-router-dom; без UI-китов
  и HTTP-клиентов (нативный fetch в `src/api/client.ts`).
- **Типы API** — рукописные контракты в `src/api/types.ts`, повторяющие pydantic-схемы
  бэкенда; `npm run gen:api` генерирует схему из живого `/openapi.json` для сверки.
- Авторизация — JWT в HttpOnly cookie, фронт лишь триггерит `/auth/*`;
  на 401 глобальный обработчик возвращает на экран входа.

## CI-контракт для фронтенда

`ci.yml` активирует job `frontend-check` при наличии `web/package.json`:
`npm ci` → `npm run check` (tsc + eslint) → `npm run build` →
проверка, что закоммиченный `web/dist` совпадает со свежей сборкой
(`git diff --exit-code`). Dependabot обновляет npm-зависимости из `/web`.
