import asyncio
import io
import zipfile
from concurrent.futures import ThreadPoolExecutor
from types import CoroutineType
from typing import IO, Any

import numpy as np
import pandas as pd
import structlog

logger = structlog.getLogger(__name__)


class PandasUtil:
    """Асинхронные обёртки pandas (thread pool)"""

    def __init__(self):
        self.executor = ThreadPoolExecutor()

    async def write_csv_async(self, df: pd.DataFrame, filename: str = "output.csv"):
        try:
            await asyncio.get_event_loop().run_in_executor(self.executor, lambda: df.to_csv(filename, index=False))
        except Exception as e:
            logger.error(f"Error writing CSV: {e}")
            raise

    async def write_exel_async(self, df: pd.DataFrame, filename: str = "output.xlsx"):
        try:
            await asyncio.get_event_loop().run_in_executor(
                self.executor, lambda: df.to_excel(filename, engine="openpyxl") # type: ignore
            )
        except Exception as e:
            logger.error(f"Error writing CSV: {e}")
            raise

    def highlight_max(self, s): # type: ignore
        is_max = s == s.max() # type: ignore
        return ["background-color: yellow" if v else "" for v in is_max] # type: ignore

    def color_negative_red(self, val: int) -> str:
        color = "red" if val < 100 else "black"
        return f"color: {color}"

    async def extract_unique_campaign_buffer_csv(self, data: io.BytesIO) -> list[str]:
        try:
            df = await self.pd_read_csv(data)
            df_cleaned = await self.pd_drop_duplicates(df)
            return df_cleaned["ID"].tolist()
        except Exception as e:
            logger.error(f"Error extracting unique campaigns: {e}")
            raise

    async def get_max_value(self, df: pd.DataFrame, search_key: str, return_key: str) -> tuple[str, int]:
        try:
            max_index = df[search_key].idxmax()
            result_row = df.loc[[max_index]]
            max_value = df[search_key].max()
            logger.info(f"Max value {max_value} corresponds to row: {result_row.to_dict()}")
            return result_row[return_key].iloc[0]
        except ValueError as ve:
            logger.error(f"No maximum value found in column '{search_key}': {ve}")
            raise
        except KeyError as ke:
            logger.error(f"Column '{ke}' not found in DataFrame")
            raise

    async def pd_read_csv(self, data: io.BytesIO | IO[bytes] | str, **kwargs: dict[str, Any]) -> pd.DataFrame:
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, lambda: pd.read_csv(filepath_or_buffer=data, encoding="utf-8-sig", sep=";", decimal=",", **kwargs) # type: ignore
        )

    async def pd_drop_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, lambda: df.drop_duplicates(subset=["ID"], keep="first")
        )

    def split_list(self, original_list: list[Any], max_length: int = 6) -> list[Any]:
        return [original_list[i : i + max_length] for i in range(0, len(original_list), max_length)]

    async def unzip_with_combine(self, data: io.BytesIO, **kwargs: dict[str, Any]) -> pd.DataFrame | None:
        try:
            dfs: list[pd.DataFrame] = []
            with zipfile.ZipFile(data) as zip_file:
                tasks: list[CoroutineType[Any, Any, pd.DataFrame | None]] = []
                for filename in zip_file.namelist():
                    if filename.endswith(".csv"):
                        tasks.append(self.process_csv_in_zip(zip_file, filename, **kwargs))
                results = await asyncio.gather(*tasks)
                dfs.extend([df for df in results if df is not None])
            dfs = [df.dropna(axis=1, how="all") for df in dfs if not df.empty] # type: ignore
            return await self.concatenate(dfs) if dfs else None
        except zipfile.BadZipFile:
            return None
        except Exception as e:
            logger.error(f"Error processing zip file: {e}")
            raise

    async def concatenate(self, dfs: list[pd.DataFrame]) -> pd.DataFrame:
        return await asyncio.get_event_loop().run_in_executor(self.executor, lambda: pd.concat(dfs, ignore_index=True))

    async def process_csv_in_zip(self, zip_file: zipfile.ZipFile, filename: str , **kwargs: dict[str, Any]) -> pd.DataFrame | None:
        try:
            with zip_file.open(filename) as csv_file:
                return await self.pd_read_csv(csv_file, **kwargs)
        except Exception as e:
            logger.error(f"Error processing CSV {filename}: {e}")
            return None

    def agg_mixed(self, series: pd.Series) -> Any:
        if pd.api.types.is_numeric_dtype(series.dtype):
            return series.fillna(0).sum() # type: ignore
        else:
            non_nulls = series.dropna()
            return non_nulls.iloc[0] if not non_nulls.empty else np.nan
