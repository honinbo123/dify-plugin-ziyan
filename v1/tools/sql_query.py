from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from utils.sql import check_sql, run_query
from utils.table import read_table, to_markdown, to_records


class SqlQueryTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        file_obj = tool_parameters.get("data_file")
        if not file_obj:
            raise ValueError("缺少参数 data_file：请上传需要查询的 CSV / Excel 文件")

        sql = check_sql(str(tool_parameters.get("sql") or ""))

        raw_limit = tool_parameters.get("limit")
        limit = 200 if raw_limit is None else max(1, min(int(raw_limit), 2000))

        fmt = str(tool_parameters.get("output_format") or "json").strip().lower()

        df = read_table(file_obj)
        result, total = run_query(df, sql, limit)
        returned = int(len(result))

        if fmt == "markdown":
            header = f"共 {total} 行"
            if total > returned:
                header += f"，已截断为前 {returned} 行"
            yield self.create_text_message(f"{header}\n\n{to_markdown(result)}")
            return

        yield self.create_json_message(
            {
                "sql": sql,
                "columns": [str(c) for c in result.columns],
                "total_rows": total,
                "returned_rows": returned,
                "truncated": total > returned,
                "rows": to_records(result),
            }
        )
