"""读取表格文件、并把 DataFrame 转成可安全 JSON 序列化的结构。"""

from __future__ import annotations

import io
import json
from typing import Any

import pandas as pd

_HEAD_BYTES = 4096
_EXCEL_SUFFIXES = ("xlsx", "xls", "xlsm", "xlsb")


def file_suffix(file_obj: Any) -> str:
    """从 Dify 传入的 file 对象里取扩展名，优先用 SDK 给出的 extension 字段。"""
    ext = str(getattr(file_obj, "extension", "") or "").strip().lower().lstrip(".")
    if ext:
        return ext
    name = str(getattr(file_obj, "filename", "") or "")
    if "." in name:
        return name.rsplit(".", 1)[-1].lower()
    return ""


def file_blob(file_obj: Any) -> bytes:
    """取文件原始字节。

    SDK 里 File.blob 是个 property，会按 url 现拉内容，所以这里要把下载失败的
    情况翻译成能看懂的报错（最常见原因是 FILES_URL / 网络没配通）。
    """
    try:
        blob = file_obj.blob
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            f"读取上传文件失败：{exc}。"
            "插件需要能从容器内访问 Dify 的文件地址，请检查 FILES_URL 与插件 Daemon 的网络配置。"
        ) from exc

    if blob is None:
        raise ValueError("无法读取上传文件的内容（blob 为空）")
    if callable(blob):
        blob = blob()
    if isinstance(blob, str):
        blob = blob.encode("utf-8")
    return bytes(blob)


def decode_text(raw: bytes) -> str:
    """按常见编码顺序尝试解码，覆盖中文 CSV 的 GBK 场景。"""
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def read_table(file_obj: Any) -> pd.DataFrame:
    """把上传的 csv / tsv / xlsx / parquet / json 读成 DataFrame。"""
    raw = file_blob(file_obj)
    if not raw:
        raise ValueError("上传的文件是空的")

    suffix = file_suffix(file_obj)

    if suffix in _EXCEL_SUFFIXES:
        return pd.read_excel(io.BytesIO(raw))
    if suffix == "parquet":
        return pd.read_parquet(io.BytesIO(raw))
    if suffix == "json":
        return pd.read_json(io.BytesIO(raw))

    text = decode_text(raw)
    head = text[:_HEAD_BYTES]
    sep = "\t" if head.count("\t") > head.count(",") else ","
    return pd.read_csv(
        io.StringIO(text),
        sep=sep,
        skipinitialspace=True,
        on_bad_lines="skip",
    )


def to_records(df: pd.DataFrame, limit: int | None = None) -> list[dict[str, Any]]:
    """转成 JSON 安全的 records：NaN 变 null、时间变 ISO 字符串。"""
    if limit is not None:
        df = df.head(limit)
    if df.empty and len(df.columns) == 0:
        return []
    return json.loads(df.to_json(orient="records", force_ascii=False, date_format="iso"))


def to_markdown(df: pd.DataFrame) -> str:
    """不依赖 tabulate 的轻量 markdown 表格。"""
    if len(df.columns) == 0:
        return "_(无结果集)_"
    cols = [str(c) for c in df.columns]
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join(["---"] * len(cols)) + " |",
    ]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(_cell(v) for v in row) + " |")
    return "\n".join(lines)


def _cell(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).replace("|", "\\|").replace("\n", " ")


def num_or_none(value: Any) -> float | None:
    """把 numpy 标量 / NaN 转成 float 或 None。"""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        return None
    return float(value)


def text_or_empty(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def semantic_hint(series: pd.Series, sample_size: int = 200) -> str | None:
    """猜文本列的语义类型（date / numeric_text），只做标注，不改变 dtype。

    CSV 里的日期和数字默认都读成字符串，标注出来才能让模型知道要 CAST。
    """
    sample = series.dropna()
    if sample.empty:
        return None
    as_text = sample.head(sample_size).astype(str).str.strip()
    if as_text.empty:
        return None

    numeric = pd.to_numeric(as_text.str.replace(",", "", regex=False), errors="coerce")
    if numeric.notna().mean() >= 0.9:
        return "numeric_text"

    try:
        parsed = pd.to_datetime(as_text, errors="coerce", format="mixed")
    except (ValueError, TypeError):
        return None
    if parsed.notna().mean() >= 0.9:
        return "date"

    return None
