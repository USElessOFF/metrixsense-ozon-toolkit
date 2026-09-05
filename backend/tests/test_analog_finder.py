"""Тесты TF-IDF поиска аналогов"""

from __future__ import annotations

from backend.app.services.analog_finder import build_tfidf_index, tokenize, top_similar


def test_tokenizer_lowercases_and_drops_short_stopwords():
    tokens = tokenize("Футболка Оверсайз Хлопок для мужчин")
    assert "футболка" in tokens
    assert "оверсайз" in tokens
    assert "для" not in tokens  # стоп-слово
    assert all(len(t) >= 3 for t in tokens)


def test_tfidf_ranks_similar_names_higher():
    names = {
        1: "Футболка оверсайз хлопок белая",
        2: "Футболка оверсайз хлопок чёрная",
        3: "Кроссовки Nike Air",
    }
    index = build_tfidf_index(names)
    matches = top_similar(index, 1, top_n=2, min_similarity=0.0)
    assert matches[0][0] == 2  # ближайший аналог — та же футболка другого цвета


def test_top_similar_excludes_self():
    names = {1: "Футболка", 2: "Футболка белая"}
    matches = top_similar(build_tfidf_index(names), 1, top_n=5, min_similarity=0.0)
    assert all(sku != 1 for sku, _ in matches)


def test_top_similar_respects_top_n_and_threshold():
    names = {
        1: "Футболка хлопок",
        2: "Футболка хлопок белая",
        3: "Футболка поло",
        4: "Кроссовки",
    }
    matches = top_similar(build_tfidf_index(names), 1, top_n=1, min_similarity=0.0)
    assert len(matches) == 1
    matches_all = top_similar(build_tfidf_index(names), 1, top_n=5, min_similarity=0.99)
    assert matches_all == []  # выше порога никого


def test_unknown_sku_returns_empty():
    index = build_tfidf_index({1: "Футболка"})
    assert top_similar(index, 999, top_n=5, min_similarity=0.0) == []
