from __future__ import annotations

import io
import re
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from utils.sql import check_sql, run_query
from utils.table import read_table

_ALLOWED_ENCODINGS = {"utf-8-sig", "utf-8", "gbk"}


class ExportCsvTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        file_obj = tool_parameters.get("data_file")
        if not file_obj:
            raise ValueError("缺少参数 data_file：请上传需要导出的 CSV / Excel 文件")

        sql = check_sql(str(tool_parameters.get("sql") or "SELECT * FROM data"))

        encoding = str(tool_parameters.get("encoding") or "utf-8-sig").strip().lower()
        if encoding not in _ALLOWED_ENCODINGS:
            encoding = "utf-8-sig"

        name = _safe_file_name(str(tool_parameters.get("file_name") or "export"))

        df = read_table(file_obj)
        result, total = run_query(df, sql, None)
        if total == 0:
            raise ValueError("SQL 结果为空，没有可导出的数据")

        buffer = io.StringIO()
        result.to_csv(buffer, index=False)
        blob = buffer.getvalue().encode(encoding, errors="replace")

        yield self.create_blob_message(
            blob=blob,
            meta={"mime_type": "text/csv", "filename": f"{name}.csv"},
        )
        yield self.create_text_message(
            f"已导出 {total} 行 × {int(result.shape[1])} 列到 {name}.csv（{encoding}）"
        )


def _safe_file_name(raw: str) -> str:
    cleaned = re.sub(r"[^\w\-.]+", "_", raw, flags=re.UNICODE).strip("._-")
    return cleaned[:64] or "export"
