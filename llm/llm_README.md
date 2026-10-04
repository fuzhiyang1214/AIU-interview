# llm · 本地大模型部署及应用

任务一：本地部署大模型 → 服务化 → 智能体 → 应用接入。

## 运行环境

| 项 | 值 |
|---|---|
| GPU | NVIDIA RTX 5070 Laptop（8151 MB 显存） |
| 驱动 | 610.74 |
| 内存 | 24 GB DDR5 |
| Ollama | v0.35.1 |
| 模型 | qwen2.5:7b（7.6B / Q4_K_M / 4.7 GB） |
| 模型存放 | `D:\OllamaModels`（用 `OLLAMA_MODELS` 从 C 盘迁出） |
| 服务地址 | `http://127.0.0.1:11434` |

## 怎么跑起来

> 前置：Windows 10/11 + 一张 ≥ 8 GB 显存的 N 卡。全程约 10 分钟。

**① 安装 Ollama**（在 PowerShell 里）

```powershell
winget install Ollama.Ollama
```

**② 把模型目录迁到 D 盘**（重要，否则会撑爆系统盘）

模型默认落在 `C:\Users\<用户名>\.ollama\models`，单个 7B 就占 4.7 GB：

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_MODELS","D:\OllamaModels","User")
```

设完必须**退出 Ollama 再重开**才生效。

**③ 拉取并运行模型**

```bash
ollama pull qwen2.5:7b          # 下载，约 4.7 GB
ollama run qwen2.5:7b "你好"    # 跑通一次对话
ollama ps                       # 确认 PROCESSOR 列显示 100% GPU
```

**④ 验证服务化**（把"装了软件"变成"提供了服务"）

Ollama 启动后自动监听 `http://127.0.0.1:11434`，并暴露 OpenAI 兼容接口：

```bash
curl --noproxy '*' http://127.0.0.1:11434/api/generate \
  -d '{"model":"qwen2.5:7b","prompt":"你好","stream":false}'
```

> `--noproxy '*'` 用于避免发给 `127.0.0.1` 的请求被环境里残留的代理设置带偏。
> 本机实测并无代理在运行，仍保留该参数以防环境变化。

**⑤ 复现性能测试**

```bash
bash llm/test/bench.sh
```

输出指标与 [`test/test_report.md`](test/test_report.md) 一致。

## 目录内容

| 路径 | 内容 |
|---|---|
| `agent/` | 智能体与 API 接入：CLI、Web 后端/前端 —— 见 [`agent/agent_README.md`](agent/agent_README.md) |
| `test/` | 测试证据：报告、API 原始返回、复现脚本、截图 —— 见 [`test/test_README.md`](test/test_README.md) |

## 进度

| 日期 | 内容 |
|---|---|
| 2026-10-03 | **任务 1-1**：Ollama 部署 → 模型目录迁至 D 盘 → 拉取 `qwen2.5:7b` → 服务化 → 性能测试（见 [`test/test_report.md`](test/test_report.md)） |
| 2026-10-04 | **任务 1-2**：Dify 自部署 → Ollama 作 model provider → API 接入 → CLI / Web 应用（见 [`agent/agent_README.md`](agent/agent_README.md)） |

