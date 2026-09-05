"""Очистка JSON-логов MetrixSense от служебных записей.

Утилита разработки: убирает из лога шумные записи (SQL-движок, тестовые
HTTP-запросы и т.п.) и пишет результат рядом в ``<name>_clean.json``.

Использование:
    python backend/scripts/format_log.py                 # самый свежий лог
    python backend/scripts/format_log.py --latest        # то же самое
    python backend/scripts/format_log.py --file app_20260829_173654.json
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import pandas as pd

LOG_DIR = Path(__file__).resolve().parents[1] / "logs"

# Логгеры, которые всегда вырезаются из результата.
EXCLUDED_LOGGERS: tuple[str, ...] = (
    "sqlalchemy.engine.Engine",
    "backend.app.adapters.base",
)

# Фильтры событий: (шаблон, является_ли_регулярным_выражением).
EXCLUDED_EVENT_FILTERS: tuple[tuple[str, bool], ...] = (
    (
        r"HTTP Request: GET http://test/api/reports/"
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12} \"HTTP/1.1 200 OK\"",
        True,
    ),
    ("::get_analytics_stocks", False),
)


def find_latest_log() -> Path:
    """Самый свежий app_*.json, к которому ещё не применялась очистка"""
    candidates = [
        p for p in LOG_DIR.glob("app_*.json") if not p.stem.endswith("_clean")
    ]
    if not candidates:
        raise SystemExit(f"No app_*.json logs found in {LOG_DIR}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    for logger_name in EXCLUDED_LOGGERS:
        df = df[~df["logger"].str.contains(logger_name, regex=False, na=False, case=False)]
    for pattern, is_regex in EXCLUDED_EVENT_FILTERS:
        df = df[~df["event"].str.contains(pattern, regex=is_regex, na=False, case=False)]
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean MetrixSense JSON logs")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--latest", action="store_true", help="clean the newest app_*.json (default)")
    group.add_argument(
        "--file",
        metavar="NAME",
        help="log file name inside backend/logs, e.g. app_20260829_173654.json",
    )
    args = parser.parse_args()

    if args.file:
        log_path = LOG_DIR / args.file
        if not log_path.exists():
            raise SystemExit(f"File not found: {log_path}")
    else:
        log_path = find_latest_log()

    print(f"Source log: {log_path}")
    df = pd.read_json(log_path, lines=True)
    df_clean = clean_data(df.copy())

    output_path = log_path.with_name(f"{log_path.stem}_clean.json")
    json_lines = df_clean.to_json(orient="records", lines=True, force_ascii=False)
    with open(output_path, "w", encoding="utf-8") as f_out:
        for line in io.StringIO(json_lines):
            record = json.loads(line)
            clean_record = {k: v for k, v in record.items() if v is not None}
            f_out.write(json.dumps(clean_record, ensure_ascii=False) + "\n")

    print(f"Cleaned log written to: {output_path}")
    print(f"Rows: {len(df)} -> {len(df_clean)}")


if __name__ == "__main__":
    main()
