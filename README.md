# AIU创智部二面实战部分 说明文件

> 进度：任务1-1（本地大模型）✅ 已完成 ｜ 任务1-2（智能体搭建）🚧 进行中\
> 后续任务：yolo、进阶...(To be continued)

## 目录结构

```
ai-interview/
├─ llm/                本地大模型部分（部署、性能测试、应用接入）
│  ├─ llm_README.md    部署与运行步骤
│  └─ test/            测试报告、复现脚本、截图
├─ yolo/               视觉处理部分（数据集、训练、推理）
├─ log.md              工程日志（按天记录进展与卡点）
└─ README.md           说明文件
```

## 任务1-1 · 本地大模型部署 ✅

**运行环境**

| 项 | 值 |
|---|---|
| GPU | NVIDIA RTX 5070 Laptop（8151 MB 显存） |
| 内存 | 24 GB DDR5 |
| 驱动 | 610.74（PyTorch 需 CUDA 12.8+ 的 wheel） |
| 运行时 | Ollama v0.35.0 ｜ qwen2.5:7b（7.6B / Q4_K_M / 4.7 GB） |

> 模型存放在 `D:\OllamaModels`（用 `OLLAMA_MODELS` 从 C 盘迁出），服务地址 `http://127.0.0.1:11434`。

**实测性能**

| 指标 | 冷启动 | 热启动 |
|---|---:|---:|
| 首字延迟 TTFT | 5.46 s | **0.03 s** |
| 生成速度 | 59.0 tok/s | 55.6 tok/s |
| 显存占用 | 4.8 / 8 GB | 4.8 / 8 GB |
| 运行位置 | 100% GPU | 100% GPU |

**结论**：冷启动的瓶颈是**模型加载**（5.33 s，占总耗时 58%），不在推理；模型驻留后首字延迟降到 0.03 s，生成稳定在 55–60 tok/s。

完整测试报告见 [`llm/test/test_report.md`](llm/test/test_report.md)，部署与运行步骤见 [`llm/llm_README.md`](llm/llm_README.md)，一键复现：`bash llm/test/bench.sh`

![运行状态](llm/test/images/ollama-ps.png)

## 怎么跑起来

需要 Windows + 一张 ≥ 8 GB 显存的 N 卡。各子链路的完整步骤见对应目录：

- **大模型链** → [`llm/llm_README.md`](llm/llm_README.md)（安装 → 迁模型目录 → 拉模型 → 服务化 → 测试）
- **视觉链** → `yolo/`（待补）

快速验证（Ollama 与模型就绪后）：

```bash
ollama run qwen2.5:7b "你好"
bash llm/test/bench.sh
```

## AI 使用情况声明

（待补）

## 待办

- [ ] 任务一 1.2 本地智能体搭建
- [ ] 任务二 YOLO 训练与实时推理
