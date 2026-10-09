# harness/ — LLM Agent Harness

用 Python 复刻 **piagent 架构**（`earendil-works/pi`）的分层，把"文本进、文本出"的大模型
变成一个能调用工具、能多步执行、能自己纠错的 agent。

## 一句话原理

> Harness = 一个循环 + 一张工具表 + 一份消息历史 + 一个事件出口。
> 它的全部价值，是让模型的推理**从"说出来"变成"做出来"**。

模型有三条天生限制，Harness 就是三副对策：

| 模型限制 | 后果 | Harness 的对策 |
|---|---|---|
| 只能生成 token | 不会开灯、不会读文件 | 把动作编码成 `tool_calls`，由 executor 代跑 |
| 无状态 | 不记得上一轮 | 消息列表外存，每轮全量重发 |
| 一次前向 = 一步 | 想一步就没法看结果 | 用 `for` 循环包起来 |

## 启动

```bash
# 前置：本机 Ollama 已在运行，且已拉取 qwen2.5:7b

# 终端交互模式
python harness/main.py

# Web 界面（默认 8000 端口）
python harness/main.py --web
python harness/main.py --web --port 8080

# 单次提问（跑完即退出，便于脚本验证）
python harness/main.py --ask "北京现在几点？"
```

依赖：**只用 Python 标准库**（`json` / `urllib` / `re` / `datetime` / `http.server`），
不需要装任何第三方包，也不需要激活 YOLO 的虚拟环境。

> `harness/mini.py` 是最初的单文件验证版（87 行），保留作为"最小历史版本"，
> 与正式骨架行为一致。可直接 `python harness/mini.py` 对照。

## 分层

```
harness/
├─ main.py            组装入口 —— 只接线，无逻辑（规范①）
├─ cli.py             应用层 A —— 终端前端，只订阅事件（规范④）
├─ web/               应用层 B —— 浏览器前端，订阅同一套事件
│  ├─ server.py       HTTP 服务 + SSE 桥接
│  └─ static/index.html
├─ core/              ≈ pi-agent-core：循环骨架，唯一不变的部分
│  ├─ loop.py         agent loop —— 整个框架的心脏
│  ├─ registry.py     工具注册表
│  ├─ executor.py     执行器（异常转字符串回灌）
│  ├─ events.py       事件总线
│  └─ context.py      会话历史 + 截断
├─ backend/           ≈ pi-ai：LLM 网关
│  ├─ gateway.py      抽象接口 + ChatResponse / ToolCall
│  └─ ollama_provider.py  Ollama 适配器
└─ tools/             可插拔能力（"万物皆插件"）
   ├─ get_time.py     查时间（玩具工具）
   ├─ http_get.py     抓网页
   └─ yolo_detect.py  目标检测（★ 复用任务二的 YOLO，跨解释器桥接）
```

**cli.py 和 web/server.py 是同一套事件的两个订阅者** —— core 完全不知道谁在监听。
这就是规范第 4 条"前后端高度解耦"最直接的证据：换前端，core 一行不改。

### `yolo_detect` 的跨解释器设计

harness 跑在系统 Python（无 torch），YOLO 依赖在 `D:\envs\yolo`：

```
harness ──subprocess──► D:\envs\yolo\Scripts\python.exe ──► yolo\detect_cli.py
                                                              └─ stdout: JSON
```

工具侧只负责起子进程 + 解析 JSON，`core` 完全无感。详见 `tools/tools_README.md`。

依赖方向：**所有箭头都从 `core` 指向接口，没有一条从 `backend`/`tools` 指回 `core` 的实现。**

```
main.py ──► core/  ◄── backend/    （core 只认 Gateway 接口）
              ▲
              └──── tools/         （core 只认注册表，不认具体工具）
```

## 三条铁律（保护 `core` 不变）

1. `core/` 里**不出现** `if model == "ollama"`
2. `core/` 里**不出现**具体工具的名字
3. `core/` 里**不出现** `print` —— 输出是 UI 的事

## 怎么加一个工具

```bash
# ① 在 tools/ 下按统一契约新建 xxx.py（NAME / SCHEMA / run）
# ② 在 main.py 加两行：
```

```python
from tools import xxx
reg.register(xxx.NAME, xxx.SCHEMA, xxx.run)
```

`core/` 一个字都不用改。

## 怎么换模型

在 `main.py` 里把 `OllamaProvider(...)` 换成别的 Provider 即可（`backend/README` 有说明）。

## 事件流

`core` 只 `emit`，UI 只 `on`：

| 事件 | 时机 | 数据 |
|---|---|---|
| `turn_start` | 一轮开始 | `user_input` |
| `model_response` | 每次模型返回 | `step` `content` `tool_calls` |
| `tool_start` / `tool_end` | 工具执行前后 | `name` `arguments` / `result` |
| `turn_end` | 循环结束 | `content` `steps` |

已实现的两个订阅者：`cli.py`（打成终端文字）和 `web/server.py`（打成 SSE 帧）。
以后要接第三个前端（桌面通知 / 飞书机器人 / …），再写一个订阅同样事件的类即可，
`core/` 依然一个字不改。
