# llm/test · 本地大模型测试说明文件

本目录存放本地部署大模型的**测试证据**：测试报告、API 原始返回、复现脚本与截图。

## 目录结构

| 文件 | 内容 |
|---|---|
| `test_report.md` | AI测试报告 |
| `raw-cold.json` | 冷启动请求的 API 原始返回 |
| `raw-hot.json` | 热启动请求的 API 原始返回 |
| `bench.sh` | 一键复现脚本 |
| `images/` | 截图（清单见下） |

## 复现命令

```
bash llm/test/bench.sh
```

前提条件：Ollama 服务运行中（`http://127.0.0.1:11434`），且已下载 `qwen2.5:7b`。
脚本会重新生成 `raw-cold.json` / `raw-hot.json` 并打印指标汇总。

## 简单结论

冷启动瓶颈在模型加载（5.33 s，占 58%）；模型驻留后首字延迟 0.03 s，生成稳定在 55–60 tok/s，全程 100% GPU，显存 4.8 / 8 GB。

## 截图清单

| 文件名 |截图内容| 状态 |
|---|---|---|
| `images/env-gpu.png` | `nvidia-smi` + `ollama --version` 同屏 | 已完成 |
| `images/ollama-ps.png` | `ollama ps`（100% GPU + 显存占用） | 已完成 |
| `images/chat-demo.png` | 一次真实对话效果 | 已完成 |


