# AIU创智部二面实战部分 说明文件

> 进度：任务1-1（本地大模型）✅ ｜ 任务1-2（智能体搭建）✅ ｜ 任务二（YOLO）✅ 两轮训练 + 摄像头实时推理均已实机跑通\
> 后续任务：进阶...(To be continued)

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
├─ yolo/                   视觉处理部分（任务二：训练与实时推理）
│  ├─ yolo_README.md       本目录说明（环境、路线、卡点、步骤）
│  ├─ main.py              训练入口（组装模型 + 配置 + 参数）
│  ├─ config/              train.yaml（超参数）｜ dataset.yaml（数据与类别）
│  ├─ script/              resize.py（图片预处理）｜ json2txt.py（标注转换）｜ DataProess.py（数据集划分）
│  ├─ your_data/           第一轮数据：示例 10 张（cat / dog）
│  ├─ your_data2/          第二轮数据：自采 60 张（shoe）
│  ├─ first_train/         第一次训练的产物归档（说明 + 截图 + 曲线）
│  │  └─ first_train_README.md
│  └─ infer/               摄像头实时推理（后端 app.py ｜ 前端 index.html）
│     ├─ infer_README.md   本目录说明
│     └─ images/           实时推理验证截图
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

## 任务二 · YOLO 训练与实时推理 ✅

**路线**：沿用出题人博客《从零开始搭建自己的 YOLO》及配套仓库 [`Linmoqian/yolo_train`](https://github.com/Linmoqian/yolo_train) 的现成流程 —— `json2txt.py`（标注转换）→ `DataProess.py`（划分数据集）→ `main.py`（训练），本机只在**环境**与**数据**上做适配，流程本身不改。

**运行环境**（独立虚拟环境，不占系统盘）

| 项 | 值 |
|---|---|
| 虚拟环境 | `D:\envs\yolo`（官方 Python 3.14 + `venv`） |
| PyTorch | 2.11.0+cu128 ｜ CUDA 12.8（`cuda.is_available() = True`） |
| Ultralytics | 8.4.173 ｜ OpenCV 5.0.0 ｜ Flask 3.1.3 |
| GPU | RTX 5070 Laptop（sm_120，必须 cu128 轮子） |
| 标注工具 | X-AnyLabeling（`Windows-CUDA12` 版） |
| 数据集（第一次） | 示例 10 张 ｜ `nc=2`（cat / dog）｜ train 6 / val 3 / test 1 |
| 数据集（第二次） | **自采 60 张 ｜ `nc=1`（shoe）｜ train 36 / val 18 / test 6** |

**三处对出题人原版的必要偏离**（详细理由见 [`yolo/yolo_README.md`](yolo/yolo_README.md)）：

1. **必须用 cu128 的 wheel** —— RTX 5070 是 Blackwell（sm_120），低版本 CUDA 预编译包会报 `no kernel image is available`；
2. **用 `venv` 而非 Miniforge** —— 本机 C 盘紧张，Miniforge 默认装 C 盘且体积大，`venv` 可整体建在 D 盘；
3. **`main.py` 加 `if __name__ == '__main__':` 保护** —— Windows 下 DataLoader 用 spawn 起子进程会重新导入 `__main__`，出题人原版无入口保护，会二次执行 `train()` 并报 `DataLoader worker ... exited unexpectedly`。

**训练结果**

| 轮次 | 数据 | 类别 | 耗时 | mAP50 | 归档 |
|---|---|---|---|---|---|
| 第一次 | 出题人示例 10 张 | cat / dog | 59 s | 0.866 | [`yolo/first_train/`](yolo/first_train/first_train_README.md) |
| 第二次 | **自采 60 张鞋子** | shoe | 2.66 min | **0.882** | `yolo/runs/.../train/exp-2` |

> ⚠️ 第一轮验证集仅 3 张图，指标只用于确认**管道打通**；第二轮 60 张仍属小样本，指标仅供参考。

![训练曲线](yolo/first_train/images/results.png)

**摄像头实时推理** 见 [`yolo/infer/`](yolo/infer/infer_README.md)：Flask 后端 + HTML 前端，严格按规范第 4 条解耦（前端只订阅、后端只计算推送）。

```bash
cd yolo\infer
D:\envs\yolo\Scripts\python.exe app.py     # 浏览器打开 http://localhost:8000
```

实测帧率稳定 **30 FPS**，真鞋与手机屏幕图片均能实时检出：

![真鞋实时检测](yolo/infer/images/01_realtime_shoe.png)

> 过程中踩到一个值得记录的坑：训练图是手机俯拍特写（目标大、光线足），而摄像头是平视且台灯直射导致过曝，
> 一度出现「真鞋检不出、手机屏幕里的鞋照片反而能检出」的现象 —— 属**域差异**而非代码问题。
> 避免过曝、让目标占画面 1/3 以上即可正常检出；根治方向是用**同一个摄像头在实际场景补拍数据重训**。
> 详细排查过程见 [`yolo/yolo_README.md`](yolo/yolo_README.md) 与 [`log.md`](log.md)。

详细步骤与卡点见 [`yolo/yolo_README.md`](yolo/yolo_README.md)。

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

# ⑤ 任务二 · YOLO（独立虚拟环境，与上面的 llm 链互不干扰）
cd yolo                                     # 必须在本目录执行：脚本里用的是相对路径
D:\envs\yolo\Scripts\python.exe script\json2txt.py      # json 标注 → YOLO txt
D:\envs\yolo\Scripts\python.exe script\DataProess.py    # 划分 train / val / test
D:\envs\yolo\Scripts\python.exe main.py                 # 训练，产出 runs/.../weights/best.pt

# ⑥ 摄像头实时推理
cd yolo\infer
D:\envs\yolo\Scripts\python.exe app.py                  # 浏览器打开 http://localhost:8000
```

各子链路的完整步骤见对应目录：

- **大模型链** → [`llm/llm_README.md`](llm/llm_README.md)（安装 → 迁模型目录 → 拉模型 → 服务化 → 测试）
- **智能体链** → [`llm/agent/agent_README.md`](llm/agent/agent_README.md)（Ollama 作 provider → Dify 应用 → API → CLI / Web）
- **视觉链** → [`yolo/yolo_README.md`](yolo/yolo_README.md)（venv 环境 → 标注 → 训练 → 实时推理）

## 进度

| 日期 | 完成内容 |
|---|---|
| 10-01 | 仓库初始化：目录骨架、README、`.gitignore`、工程日志 |
| 10-03 | **任务 1-1**：Ollama 部署、模型目录迁至 D 盘、qwen2.5:7b 服务化、性能测试与报告 |
| 10-04 | **任务 1-2**：Dify 自部署 → Ollama 作 model provider → API 接入；CLI 与 Web 两个自研应用跑通；代码按模块化重组 |
| 10-05 | **任务二启动**：确定 YOLO 路线；建独立 venv（`D:\envs\yolo`），装好 torch 2.11.0+cu128 与 ultralytics；标注 10 张图并完成划分（train 6 / val 3 / test 1） |
| 10-06 | **任务二训练跑通**：定位并修复 Windows 多进程入口保护问题（`main.py` 加 `if __name__ == '__main__':`）；完成 100 epochs 训练（mAP50 0.866），产物归档至 `yolo/first_train/` |
| 10-07 | **任务二收尾**：新增 `yolo/infer/` 摄像头实时推理（Flask + HTML，前后端解耦）与 `script/resize.py`；自采 60 张鞋子图完成标注与第二轮训练（mAP50 0.882）；**实时推理实机验证通过**（30 FPS），并定位「检不出」的域差异问题 |

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

- [x] 用 X-AnyLabeling 标注 `your_data/` 10 张图（类名与 `dataset.yaml` 一致）
- [x] `json2txt.py` 转标注 → `DataProess.py` 划分数据集
- [x] 训练（`main.py`：yolov8n / imgsz=640 / epochs=100）并留存曲线与权重
- [x] 训练产物与截图归档（`yolo/first_train/`）
- [x] 调用摄像头做实时推理 demo（`yolo/infer/`）
- [x] 采集自己的数据（60 张鞋子图）重新训练并用新模型实时推理
- [ ] 补拍实际推理场景的数据混入重训，改善泛化能力（可选优化）
