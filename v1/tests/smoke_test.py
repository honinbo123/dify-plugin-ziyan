"""本地冒烟测试。

不依赖 Dify 运行时：用一个假的 Tool 基类替换 dify_plugin，直接跑三个工具的核心逻辑，
同时做打包前自检（yaml 可解析、声明引用的文件都存在）。
"""

from __future__ import annotations

import io
import sys
import types
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ---------- mock dify_plugin ----------
pkg = types.ModuleType("dify_plugin")


class _Tool:
    def create_text_message(self, text, meta=None):
        return {"type": "text", "text": text}

    def create_json_message(self, obj, meta=None):
        return {"type": "json", "data": obj}

    def create_blob_message(self, blob, meta=None, **kwargs):
        return {"type": "blob", "blob": blob, "meta": meta or {}}


class _ToolInvokeMessage:
    pass


pkg.Tool = _Tool
entities = types.ModuleType("dify_plugin.entities")
entities_tool = types.ModuleType("dify_plugin.entities.tool")
entities_tool.ToolInvokeMessage = _ToolInvokeMessage
sys.modules["dify_plugin"] = pkg
sys.modules["dify_plugin.entities"] = entities
sys.modules["dify_plugin.entities.tool"] = entities_tool

import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from tools.export_csv import ExportCsvTool  # noqa: E402
from tools.profile_data import ProfileDataTool  # noqa: E402
from tools.sql_query import SqlQueryTool  # noqa: E402

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(name)
        print(f"  [ok]   {name}")
    else:
        FAILED.append(f"{name} {detail}")
        print(f"  [FAIL] {name} {detail}")


class FakeFile:
    """模拟 Dify 传入的 file 对象：只暴露 filename / blob / mime_type。"""

    def __init__(self, filename: str, data: bytes):
        self.filename = filename
        self.blob = data
        self.mime_type = "text/csv"
        self.extension = filename.rsplit(".", 1)[-1].lower()
        self.size = len(data)


def build_csv() -> bytes:
    frame = pd.DataFrame(
        {
            "日期": pd.date_range("2026-01-01", periods=50),
            "地区": ["华东", "华北", "华南", "西南", "东北"] * 10,
            "销售额": [100 + i * 3.5 for i in range(50)],
            "数量": [i % 7 for i in range(50)],
            "备注": [None if i % 5 == 0 else f"n{i}" for i in range(50)],
        }
    )
    buf = io.StringIO()
    frame.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8-sig")


def build_xlsx() -> bytes:
    frame = pd.DataFrame({"城市": ["北京", "上海", "广州"], "人口": [2189, 2487, 1881]})
    buf = io.BytesIO()
    frame.to_excel(buf, index=False)
    return buf.getvalue()


def section(title: str) -> None:
    print(f"\n{title}")


def test_static() -> None:
    section("打包前自检")

    manifest = yaml.safe_load((PLUGIN_DIR / "manifest.yaml").read_text(encoding="utf-8"))
    check("manifest.yaml 可解析", isinstance(manifest, dict))
    check("manifest.author 已填写", bool(manifest.get("author")))
    check("manifest.name 合法（小写/数字/下划线）", manifest["name"].isidentifier())
    check("manifest.meta.runner.version == 3.12", manifest["meta"]["runner"]["version"] == "3.12")
    check("图标存在", (PLUGIN_DIR / "_assets" / manifest["icon"]).exists(), manifest.get("icon", ""))

    for rel in manifest["plugins"]["tools"]:
        provider_path = PLUGIN_DIR / rel
        check(f"provider 声明存在：{rel}", provider_path.exists())
        if not provider_path.exists():
            continue
        provider = yaml.safe_load(provider_path.read_text(encoding="utf-8"))
        check(f"provider.author 与 manifest 一致：{rel}", provider["identity"]["author"] == manifest["author"])
        src = provider.get("extra", {}).get("python", {}).get("source")
        check(f"provider python 源存在：{src}", bool(src) and (PLUGIN_DIR / src).exists())
        for tool_rel in provider["tools"]:
            tool_path = PLUGIN_DIR / tool_rel
            check(f"tool 声明存在：{tool_rel}", tool_path.exists())
            if not tool_path.exists():
                continue
            tool = yaml.safe_load(tool_path.read_text(encoding="utf-8"))
            check(f"tool.author 与 manifest 一致：{tool_rel}", tool["identity"]["author"] == manifest["author"])
            tool_src = tool.get("extra", {}).get("python", {}).get("source")
            check(f"tool python 源存在：{tool_src}", bool(tool_src) and (PLUGIN_DIR / tool_src).exists())


def test_profile() -> None:
    section("工具 1：数据画像")
    out = list(ProfileDataTool()._invoke({"data_file": FakeFile("sales.csv", build_csv())}))
    check("返回单条消息", len(out) == 1)
    payload = out[0]["data"]
    check("message 类型为 json", out[0]["type"] == "json")
    check("行数 = 50", payload["shape"]["rows"] == 50, str(payload["shape"]))
    check("列数 = 5", payload["shape"]["columns"] == 5, str(payload["shape"]))

    cols = {c["name"]: c for c in payload["columns"]}
    check("识别出全部中文列名", set(cols) == {"日期", "地区", "销售额", "数量", "备注"}, str(list(cols)))
    check("备注列缺失 = 10", cols["备注"]["missing"] == 10, str(cols["备注"]["missing"]))
    check("销售额有数值统计", "stats" in cols["销售额"])
    check("销售额均值 = 185.75", abs(cols["销售额"]["stats"]["mean"] - 185.75) < 0.01,
          str(cols["销售额"].get("stats")))
    check("地区列有高频取值", len(cols["地区"].get("top_values", [])) > 0)
    check("日期列给出 date 语义提示", cols["日期"].get("semantic_hint") == "date",
          str(cols["日期"].get("semantic_hint")))
    check("文本列不会被误判为数字", "semantic_hint" not in cols["备注"],
          str(cols["备注"].get("semantic_hint")))
    check("预览行数 = 5", len(payload["preview"]) == 5)
    check("预览里的空值已转成 None", any(v is None for v in [payload["preview"][0].get("备注")]))

    # 中文文件名 + GB18030 编码
    gbk = build_csv().decode("utf-8-sig").encode("gb18030")
    out2 = list(ProfileDataTool()._invoke({"data_file": FakeFile("销售数据.csv", gbk)}))
    check("GBK 编码 CSV 可解析", out2[0]["data"]["shape"]["rows"] == 50)

    # Excel
    out3 = list(ProfileDataTool()._invoke({"data_file": FakeFile("cities.xlsx", build_xlsx())}))
    check("xlsx 可解析", out3[0]["data"]["shape"]["rows"] == 3, str(out3[0]["data"]["shape"]))
    check("xlsx 列名正确", [c["name"] for c in out3[0]["data"]["columns"]] == ["城市", "人口"])


def test_sql() -> None:
    section("工具 2：SQL 查询")
    csv = FakeFile("sales.csv", build_csv())
    sql = 'SELECT "地区", SUM("销售额") AS total FROM data GROUP BY "地区" ORDER BY total DESC'

    out = list(SqlQueryTool()._invoke({"data_file": csv, "sql": sql, "limit": 200}))
    check("message 类型为 json", out[0]["type"] == "json")
    payload = out[0]["data"]
    check("分组结果 = 5 行", payload["total_rows"] == 5, str(payload["total_rows"]))
    check("返回列名正确", payload["columns"] == ["地区", "total"], str(payload["columns"]))
    top = payload["rows"][0]
    check("金额最高的地区是东北", top["地区"] == "东北", str(top))
    check("聚合值约为 1927.5", abs(top["total"] - 1927.5) < 0.5, str(top["total"]))

    out_md = list(SqlQueryTool()._invoke({"data_file": csv, "sql": sql, "output_format": "markdown"}))
    check("markdown 模式返回 text", out_md[0]["type"] == "text")
    check("markdown 含表头", "| 地区 | total |" in out_md[0]["text"])

    out_lim = list(SqlQueryTool()._invoke({"data_file": csv, "sql": "SELECT * FROM data", "limit": 10}))
    check("limit 生效", out_lim[0]["data"]["returned_rows"] == 10)
    check("truncated 标记正确", out_lim[0]["data"]["truncated"] is True)

    out_from = list(SqlQueryTool()._invoke({"data_file": csv, "sql": 'FROM data SELECT COUNT(*) AS n'}))
    check("FROM-first 语法可用", out_from[0]["data"]["rows"][0]["n"] == 50)

    out_date = list(SqlQueryTool()._invoke(
        {"data_file": csv, "sql": 'SELECT date_trunc(\'month\', "日期"::DATE) AS m, COUNT(*) AS n FROM data GROUP BY 1'}
    ))
    check("字符串日期可 CAST 后按月聚合", out_date[0]["data"]["total_rows"] == 2,
          str(out_date[0]["data"]["total_rows"]))

    section("工具 2：SQL 安全拦截")
    for bad, label in [
        ("DROP TABLE data", "DDL"),
        ("DELETE FROM data", "DML"),
        ("SELECT 1; SELECT 2", "多语句"),
        ("SELECT * FROM read_csv('/etc/passwd')", "读文件函数"),
    ]:
        try:
            list(SqlQueryTool()._invoke({"data_file": csv, "sql": bad}))
            check(f"拦截 {label}", False, "未抛错")
        except ValueError:
            check(f"拦截 {label}", True)


def test_export() -> None:
    section("工具 3：导出 CSV")
    csv = FakeFile("sales.csv", build_csv())
    sql = 'SELECT "地区", COUNT(*) AS cnt FROM data GROUP BY "地区"'

    out = list(ExportCsvTool()._invoke(
        {"data_file": csv, "sql": sql, "file_name": "分区统计", "encoding": "utf-8-sig"}
    ))
    blob_msg = out[0]
    check("首条为 blob", blob_msg["type"] == "blob")
    check("mime_type 正确", blob_msg["meta"]["mime_type"] == "text/csv")
    check("文件名带扩展名", str(blob_msg["meta"].get("filename", "")).endswith(".csv"),
          str(blob_msg["meta"]))

    text = blob_msg["blob"].decode("utf-8-sig")
    lines = [ln for ln in text.strip().splitlines() if ln]
    check("导出表头正确", lines[0].strip() == "地区,cnt", lines[0] if lines else "空")
    check("导出 5 行数据", len(lines) == 6, str(len(lines)))
    check("产出说明文本", out[1]["type"] == "text" and "已导出" in out[1]["text"])

    out_gbk = list(ExportCsvTool()._invoke(
        {"data_file": csv, "sql": "SELECT * FROM data", "encoding": "gbk"}
    ))
    check("GBK 导出可解码", out_gbk[0]["blob"].decode("gbk").startswith("日期"))

    try:
        list(ExportCsvTool()._invoke({"data_file": csv, "sql": "SELECT * FROM data WHERE 1=0"}))
        check("空结果报错", False, "未抛错")
    except ValueError:
        check("空结果报错", True)


def main() -> int:
    print(f"插件目录：{PLUGIN_DIR}")
    test_static()
    test_profile()
    test_sql()
    test_export()

    print(f"\n{'=' * 46}")
    print(f"通过 {len(PASSED)} 项，失败 {len(FAILED)} 项")
    if FAILED:
        for item in FAILED:
            print(f"  - {item}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
