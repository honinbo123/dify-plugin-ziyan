"""用真实 dify_plugin 的 File 实体验证读取链路。

不走网络：直接给 File 注入 _blob，模拟 Dify 运行时把文件内容喂进来的效果。
主要用来确认 file_suffix / read_table 对真实 SDK 类型的兼容性。
"""

from __future__ import annotations

import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd  # noqa: E402
from dify_plugin.file.entities import FileType  # noqa: E402
from dify_plugin.file.file import File  # noqa: E402

from utils.table import file_suffix, read_table  # noqa: E402


def make_file(name: str, data: bytes, ext: str | None) -> File:
    file_obj = File(
        url=f"http://127.0.0.1:1/{name}",
        mime_type="text/csv",
        type=FileType.DOCUMENT,
        filename=name,
        extension=ext,
        size=len(data),
    )
    file_obj._blob = data
    return file_obj


def main() -> int:
    frame = pd.DataFrame({"城市": ["北京", "上海"], "人口": [2189, 2487]})
    csv_bytes = frame.to_csv(index=False).encode("utf-8")

    real = make_file("cities.csv", csv_bytes, "csv")
    print(f"真实 File 对象：suffix={file_suffix(real)!r} filename={real.filename!r}")
    loaded = read_table(real)
    print(loaded.to_string(index=False))

    assert list(loaded.columns) == ["城市", "人口"], list(loaded.columns)
    assert len(loaded) == 2, len(loaded)

    no_ext = make_file("report.xlsx", b"", None)
    assert file_suffix(no_ext) == "xlsx", file_suffix(no_ext)
    print(f"extension 缺失时回退到 filename：suffix={file_suffix(no_ext)!r}")

    print("\nOK: 真实 SDK File 对象可被正确解析")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
