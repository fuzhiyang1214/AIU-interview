# AI 实战项目（人工智能协会创智部二面）

> 一句话介绍：本项目围绕「本地大模型部署 + 自建智能体 + YOLO 视觉流水线」，从 0 搭一套可跑通、可复现的完整工程。

## 目录结构

```
.
├── README.md          # 本文件：项目说明
├── log.md             # 工程日志（每日进展 / 卡点 / 想法）
├── .gitignore         # 忽略大文件 / 训练产物 / 密钥
├── llm/               # 任务一：本地大模型 + 智能体 + 应用接入
└── yolo/              # 任务二：模型训练 + 实时推理 + 应用接入
```

## 我们要做的事（任务分解）

| # | 任务 | 当前状态 |
|---|------|---------|
| 1 | 本地部署大模型（Ollama / llama.cpp / LM Studio） | 未开始 |
| 1.2 | 搭建智能体（Dify / n8n / 扣子），以本地模型为 provider | 未开始 |
| 1.3 | 通过 API 接入自有应用（CLI → Web → 桌面） | 未开始 |
| 2.1 | 完成一次 ultralytics 训练 | 未开始 |
| 2.2 | YOLO 实时推理部署 | 未开始 |
| 2.3 | 推理结果接入应用 | 未开始 |
| 进阶 | 硬件联动 / 自建 Harness / 创意作品 | 视时间决定 |

## 环境准备

```bash
# 1. 本地大模型（推荐 Ollama，Windows 有 exe，开箱即用）
ollama pull qwen2.5:7b        # 显存不足换 :3b / :1.5b
ollama serve                  # 服务地址 http://localhost:11434（OpenAI 兼容）

# 2. YOLO
pip install ultralytics
yolo detect train data=coco8.yaml model=yolov8n.pt epochs=20 imgsz=640
yolo detect predict model=runs/detect/train/weights/best.pt source=0  # 0 = 摄像头
```

## 怎么跑起来

<!-- 每个模块完成后，把下面对应的占位替换成真实命令 -->

### 对话应用（待补）

```bash
cd llm && python app.py        # 后端
# 终端 A: ollama serve
# 浏览器打开: http://localhost:8000
```

### YOLO 实时检测（待补）

```bash
cd yolo && python infer.py     # 调用摄像头并输出画面
```

## 实现思路（重点：讲思路，不是贴代码）

<!-- 完成一个模块就补一段，这是面试最看重的部分 -->

### 1. 为什么选 Ollama 而不是直接跑 llama.cpp

（待补：设备条件 / 部署成本 / 生态取舍）

### 2. 智能体怎么接本地模型

（待补：把 Ollama 当 model provider，通过 API 转发到前端）

### 3. YOLO 训练与推理的取舍

（待补：为什么用小数据集先验证 / 推理端为什么用官方库而非自研）

## AI 使用情况声明

本项目开发过程中使用了 AI 助手辅助（代码生成、方案讨论、文档润色）。
核心思路、目录结构决策、模块取舍均由本人主导确认，具体用量见 `log.md`。

## 开发日志

每天开发完请往 `log.md` 追加一条，格式见该文件顶部说明。

## 参考

- 出题人：https://github.com/Linmoqian
- 工作流参考：https://github.com/Linmoqian/lin-workflow
- 模型下载：https://www.modelscope.cn/ · https://huggingface.co/
