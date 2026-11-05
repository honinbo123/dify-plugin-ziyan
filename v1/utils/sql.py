"""在 DuckDB 内存库里对 DataFrame 执行只读 SQL。"""

from __future__ import annotations

import re

import duckdb
import pandas as pd

TABLE_NAME = "data"

_ALLOWED_HEADS = {"SELECT", "WITH", "FROM", "DESCRIBE", "SUMMARIZE", "PIVOT", "UNPIVOT"}

_FORBIDDEN = (
    (re.compile(r"\b(attach|detach|install|load|pragma|export|import|copy)\b", re.I), "文件或扩展操作"),
    (re.compile(r"\b(create|drop|alter|insert|update|delete|truncate)\b", re.I), "写操作"),
    (re.compile(r"\breplace\s+into\b", re.I), "写操作"),
    (
        re.compile(
            r"\b(read_csv|read_csv_auto|read_parquet|read_json|read_json_auto|read_text|glob)\b",
            re.I,
        ),
        "直接读取容器内文件",
    ),
)


def check_sql(sql: str) -> str:
    """只放行单条只读查询，挡掉 DDL / 文件读取 / 多语句。"""
    cleaned = (sql or "").strip().rstrip(";").strip()
    if not cleaned:
        raise ValueError("SQL 不能为空")

    body = _strip_literals(cleaned)
    if ";" in body:
        raise ValueError("只允许执行单条 SQL 语句")

    head = body.split(None, 1)[0].upper() if body.split() else ""
    if head not in _ALLOWED_HEADS:
        raise ValueError(f"只支持只读查询（SELECT / WITH / FROM），收到 {head or '空语句'}")

    for pattern, reason in _FORBIDDEN:
        hit = pattern.search(body)
        if hit:
            raise ValueError(f"SQL 中包含不被允许的关键字：{hit.group(0)}（{reason}）")

    return cleaned


def _strip_literals(sql: str) -> str:
    """把字符串字面量抹掉，避免关键字误判。"""
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


def run_query(df: pd.DataFrame, sql: str, limit: int | None = None) -> tuple[pd.DataFrame, int]:
    """把 df 注册成表 data 执行查询，返回 (截断后的结果, 总行数)。"""
    con = duckdb.connect(database=":memory:")
    try:
        con.register(TABLE_NAME, df)
        result = con.execute(sql).fetchdf()
    finally:
        con.close()

    total = int(len(result))
    if limit is not None and limit > 0:
        result = result.head(limit)
    return result, total
