# 紫烟基础示例 · Dify 插件

最小的可用 Tool 插件：接收一个文本变量 → 返回字符长度（number）和一条消息（string）。

## 输入

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `text` | string | 是 | 要统计长度的文本，在工作流里绑定上游变量即可 |

## 输出

工具返回一个 JSON 消息，两个字段：

```json
{ "length": 7, "message": "文本长度为 7 个字符" }
```

- `length` — number，字符数（中文按字符计，不按字节）
- `message` — string，可直接展示的提示文本

下游节点引用方式：

```
{{#工具节点.json.length#}}
{{#工具节点.json.message#}}
```

## 文件结构

```
v0/
├── manifest.yaml              # 插件清单
├── main.py                    # 入口
├── requirements.txt           # 只有 dify_plugin，很轻
├── _assets/icon.svg
├── provider/
│   ├── ziyan_basic.yaml
│   └── ziyan_basic.py
└── tools/
    ├── text_length.yaml       # 参数声明
    └── text_length.py         # 实现（核心就 4 行）
```

## 跑起来

```bash
cd E:\python\dify-plugin-ziyan\v0

# 0) 装依赖（只有 dify_plugin 一个包）
pip install -r requirements.txt

# 1) 本地调试（先把 .env.example 复制成 .env，填 Dify 插件页「调试」给的 key）
python -m main

# 2) 打包（在上一级目录执行）
cd E:\python\dify-plugin-ziyan
dify plugin package ./v0
```

## 发布到 GitHub

三个必须同时满足，否则装不上：

1. `manifest.yaml` 和 `provider/ziyan_basic.yaml` 的 `author` 改成你的 GitHub 用户名（两处一致）
2. Release tag 与 `manifest.yaml` 的 `version` 对齐（`v0.0.1` ↔ `0.0.1`）
3. Release 的 Assets 里真的挂上 `.difypkg` 文件

然后在 Dify：插件 → 安装插件 → 从 GitHub → 粘贴仓库 URL → 选版本 → 安装。
