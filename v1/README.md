# 紫烟数据分析 · Dify 插件

把表格数据分析能力装进 Dify：上传 CSV / Excel，做数据画像、跑 SQL、导出处理结果。计算全部在插件容器内用 pandas + DuckDB 完成。

## 三个工具

| 工具 | 作用 | 典型用法 |
|---|---|---|
| **数据画像** `profile_data` | 行列数、字段类型、缺失率、数值分位数、文本高频值、样例行、重复行 | 分析前先摸清数据结构，把结果喂给 LLM 生成分析思路 |
| **SQL 查询** `sql_query` | 把文件注册成 DuckDB 表 `data`，执行单条只读 SQL | `SELECT 地区, SUM(销售额) FROM data GROUP BY 1` |
| **导出 CSV** `export_csv` | 按 SQL 清洗/聚合后导出为可下载文件 | 清洗后的数据集、聚合报表交付给用户 |

三者组合的典型工作流：

```
开始（文件上传）
  → 数据画像 → LLM（生成分析计划 / SQL）
  → SQL 查询 → LLM（解读结果、写报告）
  → 导出 CSV（可选，交付处理后的文件）
```

## ⚠️ 上线前必须改一处

`manifest.yaml` 和 `provider/ziyan_data.yaml` 里的 `author` 字段**必须改成你自己的 GitHub 用户名**（两处都要改，且一致）。

不一致时，Dify 安装会报 `plugin_unique_identifier is not valid`，这是官方明确的行为。

```yaml
author: ziyan        # ← 改成你的 GitHub 用户名
```

## 目录结构

```
dify-plugin-ziyan/
├── manifest.yaml             # 插件清单：元信息、内存配额、注册哪些 provider
├── main.py                   # 入口，Plugin(DifyPluginEnv(...))
├── requirements.txt          # 运行时依赖，安装时在插件容器内 pip install
├── pyproject.toml            # 本地开发依赖
├── _assets/icon.svg          # 图标，manifest 里写 icon.svg（相对 _assets）
├── provider/
│   ├── ziyan_data.yaml       # 供应商层：无凭据，挂 3 个 tool
│   └── ziyan_data.py
├── tools/
│   ├── profile_data.yaml     # 参数声明（给 LLM 看的说明书）
│   ├── profile_data.py       # 参数实现
│   ├── sql_query.yaml
│   ├── sql_query.py
│   ├── export_csv.yaml
│   └── export_csv.py
└── utils/
    ├── table.py              # 读文件、JSON 安全转换、markdown 表格
    └── sql.py                # SQL 白名单校验 + DuckDB 执行
```

每个工具是「一对文件」：`.yaml` 声明参数（LLM 靠它决定怎么调），`.py` 写实现。

## 本地调试

先装依赖（Python 3.12）：

```bash
uv venv --python 3.12
uv pip install -r requirements.txt
```

在 Dify 里拿调试凭据：插件页 → 右上角「调试」→ 复制 key 和 host。

```bash
cp .env.example .env
# 编辑 .env，填入 REMOTE_INSTALL_KEY 和 REMOTE_INSTALL_URL

.venv/Scripts/python.exe -m main     # Linux/macOS 用 .venv/bin/python -m main
```

启动成功后，插件会以「调试中」状态出现在 Dify 的插件页，改代码重启即可生效，**不用每次打包**。

跑本地测试（不依赖 Dify 运行时）：

```bash
.venv/Scripts/python.exe tests/smoke_test.py     # 三工具逻辑 + 打包前自检，56 项
.venv/Scripts/python.exe tests/sdk_file_test.py  # 真实 SDK File 对象解析
```

## 打包

在**插件目录的上一级**执行（产物落在当前目录）：

```bash
cd E:/python
dify plugin package ./dify-plugin-ziyan
# => E:/python/dify-plugin-ziyan.difypkg
```

`dify` 是 CLI 二进制，从 [dify-plugin-daemon releases](https://github.com/langgenius/dify-plugin-daemon/releases) 下载对应平台版本，改名后放进 PATH。

## 发布到 GitHub（三个硬性要求，缺一装不上）

1. **`author` = 仓库所属 GitHub 用户名**，`manifest.yaml` 和 `provider/*.yaml` 都要改
2. **Release tag 与 `manifest.yaml` 的 `version` 一致**（`v0.0.1` ↔ `0.0.1`）
3. **Release 的 Assets 里必须真的有 `.difypkg` 文件**（不是源码包，是打包产物）

```bash
git init
git add .
git commit -m "feat: ziyan data analytics plugin v0.0.1"
git branch -M main
git remote add origin https://github.com/<你的用户名>/dify-plugin-ziyan.git
git push -u origin main
```

然后在 GitHub 上：Releases → Draft a new release → tag 填 `v0.0.1` → 把 `.difypkg` 拖进 Assets → Publish。

以后每发一版：改 `manifest.yaml` 的 `version` → 重新 `dify plugin package` → 打新 tag → 新 Release。

也可以直接推 tag 让 CI 代劳（见 `.github/workflows/release.yml`）：

```bash
git tag v0.0.1 && git push origin v0.0.1
```

## 在 Dify 安装

插件页 → 「安装插件」→「从 GitHub」→ 粘贴仓库 URL：

```
https://github.com/<你的用户名>/dify-plugin-ziyan
```

下拉框会自动列出 Release 里的版本，选中安装即可。

## 已知限制

- **文件读取走 HTTP**：SDK 里 `File.blob` 不是内存直传，而是按 `url` 现场下载。所以插件容器必须能访问到 Dify 的文件地址（`FILES_URL`）。Docker 部署时如果 `FILES_URL` 填的是 `localhost` 或公网域名，容器内很可能访问不到，会报「读取上传文件失败」。排查：进插件容器 `curl` 一下报错里的文件 URL。
- **内存**：`manifest.yaml` 里申请了 512MB。处理几十万行以上、或宽表时仍可能 OOM，可上调 `resource.memory`（单位字节）。
- **超时**：`main.py` 里 `MAX_REQUEST_TIMEOUT=120` 秒。超大文件的全量 groupby 可能超时，建议先用 SQL 聚合再返回。
- **依赖安装**：插件首次安装时会在容器内 `pip install` pandas/openpyxl/duckdb，需要容器能出网。内网环境要预置镜像源或本地 wheel。
- **SQL 安全**：只放行单条只读语句，挡掉了 DDL/DML 和 DuckDB 的文件读取函数，防止越权访问容器内文件。这不是完备的沙箱，但足以拦住 LLM 生成的危险语句。
- **列名含中文**：SQL 里要用双引号，`SELECT "销售额" FROM data`。工具的 `llm_description` 里已经提示，模型一般能照做。
- **CSV 日期是字符串**：CSV 读进来日期列是文本，画像会给 `semantic_hint: date`，SQL 里需要 `"日期"::DATE` 再 `date_trunc`。

## 隐私

见 [PRIVACY.md](PRIVACY.md)。插件不发起任何外部网络请求，数据只在内存中处理，不做持久化。
