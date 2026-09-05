"""Поиск аналогов товаров: TF-IDF по названиям, косинусная близость.

Чистый Python без scikit-learn: для каталога до ~1000 SKU
счёт занимает миллисекунды, зависимостей не добавляет.
"""

from __future__ import annotations

import math
import re
from typing import Any

import structlog
from pydantic import ValidationError

from backend.app.exceptions import SettingsError
from backend.app.pydantic_models.analog import AnalogItem, AnalogsResponse
from backend.app.pydantic_models.ozon.seller.request import (
    ProductInfoPricesV5Filter,
    ProductInfoPricesV5Request,
)
from backend.app.ozon_seller import OzonSellerClient

logger = structlog.get_logger(__name__)

_TOKEN_RE = re.compile(r"[а-яёa-z0-9]+")
_STOPWORDS = {
    "для", "и", "в", "на", "с", "по", "из", "от", "до", "у", "о",
    "the", "of", "new", "упак", "шт", "см", "мм", "мл", "штук",
}


def tokenize(name: str) -> list[str]:
    """Нижний регистр, слова от 3 символов, без служебных"""
    return [
        token
        for token in _TOKEN_RE.findall(name.lower())
        if len(token) >= 3 and token not in _STOPWORDS
    ]


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    dot = sum(weight * b.get(token, 0.0) for token, weight in a.items())
    norm_a = math.sqrt(sum(weight * weight for weight in a.values()))
    norm_b = math.sqrt(sum(weight * weight for weight in b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def build_tfidf_index(names_by_sku: dict[int, str]) -> dict[int, dict[str, float]]:
    """TF-IDF векторы: tf = count/len(tokens), idf = log(N / (1 + df))"""
    token_counts: dict[int, dict[str, int]] = {}
    for sku, name in names_by_sku.items():
        counts: dict[str, int] = {}
        for token in tokenize(name):
            counts[token] = counts.get(token, 0) + 1
        if counts:
            token_counts[sku] = counts

    total_docs = len(token_counts)
    if total_docs == 0:
        return {}

    document_frequency: dict[str, int] = {}
    for counts in token_counts.values():
        for token in counts:
            document_frequency[token] = document_frequency.get(token, 0) + 1

    index: dict[int, dict[str, float]] = {}
    for sku, counts in token_counts.items():
        tokens_len = sum(counts.values())
        index[sku] = {
            token: (count / tokens_len) * math.log(total_docs / (1 + document_frequency[token]))
            for token, count in counts.items()
        }
    return index


def top_similar(
    index: dict[int, dict[str, float]],
    target_sku: int,
    top_n: int,
    min_similarity: float,
) -> list[tuple[int, float]]:
    target_vector = index.get(target_sku)
    if target_vector is None:
        return []
    scored = [
        (sku, _cosine(target_vector, vector))
        for sku, vector in index.items()
        if sku != target_sku
    ]
    scored = [(sku, score) for sku, score in scored if score >= min_similarity]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_n]


class AnalogFinderService:
    def __init__(self, db: Any):
        self.db = db

    async def find_analogs(
        self,
        seller: OzonSellerClient,
        sku: int,
        top_n: int = 10,
        min_similarity: float = 0.1,
    ) -> AnalogsResponse:
        catalog = await seller.get_product_info_list()
        products = [
            {"sku": item.sku, "name": item.name or "", "offer_id": item.offer_id, "product_id": item.product_id}
            for item in catalog.items
            if item.sku is not None and item.name
        ]
        logger.info("::analog_finder catalog", size=len(products), target_sku=sku)

        target = next((p for p in products if p["sku"] == sku), None)
        if target is None:
            raise SettingsError(f"SKU {sku} не найден в каталоге из {len(products)} товаров")

        names_by_sku = {p["sku"]: p["name"] for p in products}
        index = build_tfidf_index(names_by_sku)
        matches = top_similar(index, sku, top_n=top_n, min_similarity=min_similarity)
        logger.info(
            "::analog_finder found",
            sku=sku,
            analogs=len(matches),
            top=[{"sku": s, "sim": round(v, 3)} for s, v in matches[:3]],
        )

        matches_by_sku = {match_sku: score for match_sku, score in matches}
        match_products = [p for p in products if p["sku"] in matches_by_sku]

        price_by_product_id: dict[int, float] = {}
        product_ids = [p["product_id"] for p in match_products if p["product_id"] is not None]
        if product_ids:
            prices = await seller.get_product_info_prices(
                ProductInfoPricesV5Request(
                    filter=ProductInfoPricesV5Filter(product_id=product_ids),
                    limit=1000,
                )
            )
            for item in prices.items:
                if item.product_id is not None and item.price and item.price.price:
                    price_by_product_id[item.product_id] = float(item.price.price)

        analog_items: list[AnalogItem] = []
        for product in match_products:
            try:
                analog_items.append(
                    AnalogItem(
                        sku=product["sku"],
                        name=product["name"],
                        offer_id=product["offer_id"],
                        similarity=round(matches_by_sku[product["sku"]], 3),
                        price=price_by_product_id.get(product["product_id"]),
                    )
                )
            except ValidationError:
                continue

        response = AnalogsResponse(
            sku=sku,
            name=target["name"],
            total_catalog=len(products),
            analogs=analog_items,
        )
        logger.info(
            "::analog_finder result",
            sku=sku,
            total_catalog=response.total_catalog,
            returned=len(response.analogs),
        )
        return response
