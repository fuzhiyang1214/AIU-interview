# AIU创智部二面实战部分 说明文件

> 进度：任务1-1（本地大模型）✅ 已完成 ｜ 任务1-2（智能体搭建）✅ 已完成\
> 后续任务：yolo、进阶...(To be continued)

## 目录结构

```
ai-interview/
├─ llm/                    本地大模型：部署、性能测试、智能体与 API 接入
│  ├─ llm_README.md        本目录说明与部署步骤
│  ├─ agent/               智能体与 API 接入（CLI / Web）
│  │  ├─ agent_README.md   本目录说明
│  │  ├─ dify_client.py    Dify 接入模块（通信细节全部封装在此）
│  │  ├─ cli.py            命令行入口（只做组装）
│  │  ├─ server.py         Web 后端（只做路由与转发）
│  │  └─ index.html        Web 前端（只做 UI 与订阅）
│  └─ test/                测试证据：报告、原始数据、复现脚本、截图
│     └─ test_README.md    本目录说明
├─ yolo/                   视觉处理部分（任务二，尚未开始）
│  └─ yolo_README.md       本目录说明
├─ log.md                  工程日志（按天记录进展与卡点）
└─ README.md               说明文件
```

## 任务1-1 · 本地大模型部署 ✅

**运行环境**

| 项 | 值 |
|---|---|
| GPU | NVIDIA RTX 5070 Laptop（8151 MB 显存） |
| 内存 | 24 GB DDR5 |
| 驱动 | 610.74（PyTorch 需 CUDA 12.8+ 的 wheel） |
| 运行时 | Ollama v0.35.1 ｜ qwen2.5:7b（7.6B / Q4_K_M / 4.7 GB） |

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

需要 Windows + 一张 ≥ 8 GB 显存的 N 卡；智能体链另外需要 Docker Desktop。

```bash
# ① 本地大模型（Ollama）
ollama serve                          # 服务化，监听 11434
ollama pull qwen2.5:7b                # 拉模型，约 4.7 GB
ollama run qwen2.5:7b "你好"           # 冒烟测试

# ② 智能体链（Dify，15 个容器）
cd D:\dify && docker compose up -d    # Dify 源码目录（按实际路径改），起来后访问 http://localhost
#   在 Dify 中安装 Ollama 插件并添加模型（Base URL 用 host.docker.internal:11434）
#   → 新建「聊天助手」并「发布」→「访问 API」取得 app-xxxx 密钥

# ③ 应用接入（CLI / Web）
cd llm/agent
export DIFY_API_KEY="app-xxxxxxxx"    # PowerShell 写：$env:DIFY_API_KEY="app-xxxxxxxx"
python cli.py                         # 终端多轮对话
python server.py                      # Web 界面 http://127.0.0.1:8000

# ④ 复现性能测试
bash llm/test/bench.sh
```

各子链路的完整步骤见对应目录：

- **大模型链** → [`llm/llm_README.md`](llm/llm_README.md)（安装 → 迁模型目录 → 拉模型 → 服务化 → 测试）
- **智能体链** → [`llm/agent/agent_README.md`](llm/agent/agent_README.md)（Ollama 作 provider → Dify 应用 → API → CLI / Web）
- **视觉链** → [`yolo/yolo_README.md`](yolo/yolo_README.md)（任务二，尚未开始）

## 进度

| 日期 | 完成内容 |
|---|---|
| 10-01 | 仓库初始化：目录骨架、README、`.gitignore`、工程日志 |
| 10-03 | **任务 1-1**：Ollama 部署、模型目录迁至 D 盘、qwen2.5:7b 服务化、性能测试与报告 |
| 10-04 | **任务 1-2**：Dify 自部署 → Ollama 作 model provider → API 接入；CLI 与 Web 两个自研应用跑通；代码按模块化重组 |

逐日过程与卡点见 [`log.md`](log.md)。

## AI 使用情况声明



### 使用的工具

| 工具 | 版本 / 模型 | 主要用途 |
|---|---|---|
| WorkBuddy | 5.6.2（内置 DeepSeek V4.1-flash） | 环境排障、技术选型、代码初稿、文档起草与评审 |

### 分工

| 环节 | 主导方 | 说明 |
|---|---|---|
| 环境事实（版本 / 端口 / 进程 / 显存） | **我** | 以本机实测为准 |
| 技术选型 | AI 给候选，**我拍板** | 智能体框架在 Dify / n8n / 纯自研中选定 Dify |
| 系统级操作（安装、代理、Docker 配置） | **我亲手执行** | AI 只提供命令，避免其代为操作 |
| 代码实现 | AI 出初稿，**我根据指示进行跑通测试** | `dify_client.py` / `cli.py` / `server.py` / `index.html` |
| 测试与数据 | **我** | 测试用例AI由提供，自己输入Powershell，自己截图|
| REAMDE文档 | 大部分由AI完成，我进行部分删繁就简| `README` / 测试报告 |
| log.md日志| 基本全部由我完成，仅复制一些AI对话|`log.md`|






## 待办


- [ ] 任务二 YOLO 训练与实时推理
