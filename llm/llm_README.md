# llm · 本地大模型部署及应用

任务一：本地部署大模型 → 服务化 → 智能体 → 应用接入。

## 运行环境

| 项 | 值 |
|---|---|
| GPU | NVIDIA RTX 5070 Laptop（8151 MB 显存） |
| 驱动 | 610.74 |
| 内存 | 24 GB DDR5 |
| Ollama | v0.35.0 |
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

> `--noproxy '*'` 是必需的：本机 `HTTPS_PROXY` 指向本地代理，不加这个参数会把发给 `127.0.0.1` 的请求也塞进代理，导致连不上。

**⑤ 复现性能测试**

```bash
bash llm/test/bench.sh
```

输出指标与 [`test/test_report.md`](test/test_report.md) 一致。

## 目录内容

| 路径 | 内容 |
|---|---|
| `test/` | 测试证据：报告、API 原始返回、复现脚本、截图 —— 见 [`test/test_README.md`](test/test_README.md) |

