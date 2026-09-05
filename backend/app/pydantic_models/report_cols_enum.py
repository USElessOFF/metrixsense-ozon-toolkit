
from enum import StrEnum


class ColumnsFullReport(StrEnum):

    # Аналитика / продажи
    SKU = "ID Товара"
    NAME = "Наименование"
    REVENUE = "Заказано, ₽"
    ORDERED_UNITS = "Заказано, шт."
    STOCK = "Остаток (на складах)"

    # Реклама
    ROMI = "ROMI, %"
    DRR_PAYED = "ДРР (оплаченные), %"
    CR_ORDER = "CR в заказы, %\n(Готовность к покупке)"

    # Карточки товаров (/v3/product/info/list)
    OFFER_ID = "Артикул (offer_id)"
    PRICE_CARD = "Цена (карточка), ₽"
    OLD_PRICE = "Старая цена, ₽"
    MIN_PRICE = "Мин. цена, ₽"
    VOLUME_WEIGHT_L = "Объёмный вес, л"
    COMMISSION_FBO_PCT = "Комиссия FBO, %"
    COMMISSION_FBS_PCT = "Комиссия FBS, %"
    DELIVERY_FBO = "Доставка FBO, ₽"
    RETURN_FBO = "Возврат FBO, ₽"

    # Финансовая выписка (/v3/finance/transaction/list)
    FIN_COMMISSION = "Комиссия за продажу (выписка), ₽"
    FIN_DELIVERY = "Доставка (выписка), ₽"
    FIN_RETURN_DELIVERY = "Возвратная доставка (выписка), ₽"
    FIN_SERVICES = "Услуги Ozon (выписка), ₽"
    FIN_ACCRUALS = "Начислено за продажи (выписка), ₽"
    FIN_LOGISTICS_PER_UNIT = "Факт. логистика на единицу, ₽"

    # Юнит-экономика
    AVG_PRICE = "Средняя цена товара"
    COMMISSION_OZON = "Комиссия Ozon, ₽"
    LOGISTICS_RUB = "Логистика, ₽"
    PROFIT = "Прибыль, ₽"
    MARGIN = "Маржинальность, %"

    # Локальные габариты (product_dimensions)
    DIM_LENGTH_MM = "Длина, мм"
    DIM_WIDTH_MM = "Ширина, мм"
    DIM_HEIGHT_MM = "Высота, мм"
    DIM_VOLUME_L = "Габаритный объём, л"
    DIM_OVERSIZE = "Крупногабарит (сторона > 500 мм)"
