"""Живые интеграционные тесты новых методов Ozon Seller API.

Пометка ``pytest.mark.live``: исключены из дефолтного прогона
(``pytest.ini`` → ``addopts = -m "not live"``), чтобы нестабильность
реального API не ломала CI. Локальный запуск: ``pytest -m live``.

Запускаются только при наличии валидных ключей Seller API (переменные
``OZON_SELLER_CLIENT_ID`` / ``OZON_SELLER_API_KEY`` или ``.env`` в корне
проекта). Если ключей нет — тесты пропускаются (``pytest.skip``).

Цель — «просмотреть, что возвращают» новые вызовы: тесты реально ходят в
API и печатают упрощённую выжимку ответа (числа товаров, комиссии, тарифы
логистики, сводные финансовые итоги). Так можно быстро убедиться, что
типизированные методы и Pydantic-модели корректно парсят живые ответы Ozon.

Полезная нагрузка покрывает расширенный список API:
- /v5/product/info/prices  — цены, комиссии, тарифы логистики;
- /v3/product/info/list    — карточки товаров (объёмный вес);
- /v3/finance/transaction/list и /totals — фактические начисления;
- /v1/rating/summary       — рейтинг продавца;
- /v1/actions              — проверка подключения.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.app.config import settings
from backend.app.ozon_seller import OzonSellerClient
from backend.app.pydantic_models.ozon.seller.request import (
    FinanceTransactionListRequest,
    FinanceTransactionTotalsRequest,
    ProductInfoListRequest,
    ProductInfoPricesV5Request,
)
from backend.app.pydantic_models.ozon.seller.response import (
    FinanceTransactionTotalsResponse,
    ProductInfoPricesV5Response,
    ProductListResponse,
    RatingSummaryResponse,
)

SELLER_CLIENT_ID = (settings.OZON_SELLER_CLIENT_ID or "").strip()
SELLER_API_KEY = (settings.OZON_SELLER_API_KEY or "").strip()
HAVE_CREDENTIALS = bool(SELLER_CLIENT_ID and SELLER_API_KEY)

# Live-тесты помечены маркером и исключены из дефолтного прогона
# (pytest.ini: addopts = -m "not live"). Явный запуск: pytest -m live.
pytestmark = pytest.mark.live


needs_credentials = pytest.mark.skipif(
    not HAVE_CREDENTIALS,
    reason="OZON_SELLER_CLIENT_ID / OZON_SELLER_API_KEY не заданы (нет .env либо env-переменных)",
)


def _defaults_date_filter() -> dict:
    """Период за последние 7 дней (в пределах лимита Ozon API).

    Финансовые методы (/v3/finance/transaction/*) ожидают ключи
    ``from``/``to`` в формате ``YYYY-MM-DDTHH:mm:ss.sssZ``.
    """
    to_ = datetime.now(tz=UTC)
    from_ = to_ - timedelta(days=7)
    return {"from": from_, "to": to_}


@pytest.fixture
async def seller() -> OzonSellerClient:
    """Клиент Ozon Seller API с вашими ключами; закрывается после теста"""
    if not HAVE_CREDENTIALS:
        pytest.skip("Отсутствуют ключи Ozon Seller API")
    client = OzonSellerClient(SELLER_CLIENT_ID, SELLER_API_KEY)
    yield client
    await client.close()


# /v1/actions — проверка подключения


@needs_credentials
@pytest.mark.asyncio
async def test_check_connection_live(seller: OzonSellerClient) -> None:
    """Реальные ключи должны подтверждать доступ (или явно False)"""
    connected = await seller.check_connection()
    print("\n[check_connection] connected =", connected)
    assert isinstance(connected, bool)


# /v5/product/info/prices — цены, комиссии, тарифы логистики


@needs_credentials
@pytest.mark.asyncio
async def test_get_product_info_prices_live(seller: OzonSellerClient) -> None:
    """Цены/комиссии/логистика реального аккаунта — парсинг в Pydantic"""
    resp = await seller.get_product_info_prices(ProductInfoPricesV5Request())
    assert isinstance(resp, ProductInfoPricesV5Response)
    print(f"\n[product/info/prices] items = {len(resp.items)}")
    for item in resp.items[:3]:
        comm = item.commissions
        price = item.price
        print(
            " -",
            item.product_id,
            "| price=",
            price.price if price else None,
            "| comm%=",
            (comm.sales_percent_fbo if comm else None),
            "| vol_weight(l)=",
            item.volume_weight,
            "| log_FBO_range=",
            (comm.fbo_direct_flow_trans_min_amount if comm else None),
        )


# /v3/product/list — список товаров (чтобы взять реальные SKU и product_id)


@needs_credentials
@pytest.mark.asyncio
async def test_get_product_list_live(seller: OzonSellerClient) -> None:
    """Список товаров; из него можно взять SKU для карточек"""
    resp = await seller.get_product_list()
    assert isinstance(resp, ProductListResponse)
    print(f"\n[product/list] items = {len(resp.items)}")
    for item in resp.items[:3]:
        print("  sku =", item.sku, "| offer_id =", item.offer_id)


# /v3/product/info/list — карточки товаров (объёмный вес)


@needs_credentials
@pytest.mark.asyncio
async def test_get_product_info_list_live(seller: OzonSellerClient) -> None:
    """Карточки товаров: берём sku из списка, проверяем volume_weight"""
    catalog = await seller.get_product_list()
    sku_list = [item.sku for item in catalog.items if item.sku is not None]
    if not sku_list:
        pytest.skip("Нет товаров в каталоге — /v3/product/info/list не вызывается")

    # /v3/product/info/list принимает до 1000 SKU за запрос.
    resp = await seller.get_product_info_list(
        ProductInfoListRequest(sku=sku_list[: min(100, len(sku_list))])
    )
    print(f"\n[product/info/list] cards = {len(resp.items)}")
    for card in resp.items[:3]:
        print(
            "  sku =",
            card.sku,
            "| name =",
            card.name,
            "| price =",
            card.price,
            "| volume_weight =",
            card.volume_weight,
        )


# /v3/finance/transaction/totals — сводные итоги периода


@needs_credentials
@pytest.mark.asyncio
async def test_get_finance_transaction_totals_live(seller: OzonSellerClient) -> None:
    """Сводные финансовые итоги за последние 7 дней"""
    req = FinanceTransactionTotalsRequest.model_validate(
        # У totals фильтр плоский: date на верхнем уровне тела.
        {"date": _defaults_date_filter()}
    )
    resp = await seller.get_finance_transaction_totals(req)
    assert isinstance(resp, FinanceTransactionTotalsResponse)
    print("\n[finance/transaction/totals] result =", resp.result)


# /v3/finance/transaction/list — детальные начисления по отправлениям


@needs_credentials
@pytest.mark.asyncio
async def test_get_finance_transaction_list_live(seller: OzonSellerClient) -> None:
    """Детальная выписка: количество операций и первые 3 (комиссии/доставка)"""
    req = FinanceTransactionListRequest.model_validate(
        {
            "filter": {"date": _defaults_date_filter()},
            "page": 1,
            "page_size": 100,
        }
    )
    resp = await seller.get_finance_transaction_list(req)
    print(f"\n[finance/transaction/list] page_count = {resp.page_count}")
    for op in resp.operations[:3]:
        print(
            "  op_type =",
            op.operation_type,
            "| return =",
            op.accruals_for_sale,
            "| deliv =",
            op.delivery_charge,
            "| commission =",
            op.sale_commission,
        )


# /v1/rating/summary — рейтинг продавца


@needs_credentials
@pytest.mark.asyncio
async def test_get_rating_summary_live(seller: OzonSellerClient) -> None:
    """Текущий рейтинг продавца (группы, баллы, штрафной балл)"""
    resp = await seller.get_rating_summary()
    assert isinstance(resp, RatingSummaryResponse)
    print("\n[rating/summary] groups =", len(resp.groups))
    for group in resp.groups:
        for item in group.items:
            print(f"  {group.group_name} / {item.rating_type} = {item.score}")
