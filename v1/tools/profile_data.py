from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pandas as pd

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from utils.table import num_or_none, read_table, semantic_hint, text_or_empty, to_records


class ProfileDataTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        file_obj = tool_parameters.get("data_file")
        if not file_obj:
            raise ValueError("缺少参数 data_file：请上传需要分析的 CSV / Excel 文件")

        raw_sample = tool_parameters.get("sample_rows")
        sample_rows = 5 if raw_sample is None else max(0, int(raw_sample))

        raw_top_n = tool_parameters.get("top_n")
        top_n = 5 if raw_top_n is None else max(1, int(raw_top_n))

        df = read_table(file_obj)
        if df.shape[1] == 0:
            raise ValueError("文件解析后没有任何列，请确认文件格式与分隔符是否正确")

        total = int(len(df))
        columns = [self._describe_column(df, col, total, top_n) for col in df.columns]

        result = {
            "shape": {"rows": total, "columns": int(df.shape[1])},
            "columns": columns,
            "duplicated_rows": int(df.duplicated().sum()) if total else 0,
            "preview": to_records(df, sample_rows) if sample_rows > 0 else [],
        }
        yield self.create_json_message(result)

    @staticmethod
    def _describe_column(
        df: pd.DataFrame, col: Any, total: int, top_n: int
    ) -> dict[str, Any]:
        series = df[col]
        missing = int(series.isna().sum())

        info: dict[str, Any] = {
            "name": str(col),
            "dtype": str(series.dtype),
            "non_null": int(total - missing),
            "missing": missing,
            "missing_pct": round(missing / total * 100, 2) if total else 0.0,
            "unique": int(series.nunique(dropna=True)),
        }

        if pd.api.types.is_bool_dtype(series):
            counts = series.value_counts(dropna=True).head(top_n)
            info["top_values"] = [
                {"value": text_or_empty(k), "count": int(v)} for k, v in counts.items()
            ]
        elif pd.api.types.is_numeric_dtype(series):
            desc = series.describe()
            info["stats"] = {
                "mean": num_or_none(desc.get("mean")),
                "std": num_or_none(desc.get("std")),
                "min": num_or_none(desc.get("min")),
                "p25": num_or_none(desc.get("25%")),
                "p50": num_or_none(desc.get("50%")),
                "p75": num_or_none(desc.get("75%")),
                "max": num_or_none(desc.get("max")),
            }
        elif pd.api.types.is_datetime64_any_dtype(series):
            info["semantic_hint"] = "date"
            info["range"] = {
                "min": text_or_empty(series.min()),
                "max": text_or_empty(series.max()),
            }
        else:
            hint = semantic_hint(series)
            if hint:
                info["semantic_hint"] = hint
            counts = series.value_counts(dropna=True).head(top_n)
            info["top_values"] = [
                {"value": text_or_empty(k), "count": int(v)} for k, v in counts.items()
            ]

        return info
