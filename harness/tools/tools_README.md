# tools/ — 可插拔工具层

一个个独立能力。**加工具不改 core** —— 这是这个框架最值钱的性质。

## 统一契约

每个工具文件只暴露两样东西：

```python
NAME = "get_time"          # 工具名，必须和 schema 里的 name 一致

SCHEMA = {                 # 给模型看的"工具说明书"
    "type": "function",
    "function": {
        "name": NAME,
        "description": "……",              # 模型靠这句决定什么时候用它，要写清楚
        "parameters": {"type": "object", "properties": {...}, "required": [...]},
    },
}

def run(**kwargs) -> str:  # 实现，返回值必须是字符串
    ...
```

## 现有工具

| 文件 | 工具 | 说明 |
|---|---|---|
| `get_time.py` | `get_time` | 查时间（玩具工具，用于验证链路） |
| `http_get.py` | `http_get` | 抓网页并剥离 HTML 标签 |
| `yolo_detect.py` | `yolo_detect` | **目标检测（复用任务二的 YOLO）** |

## ⚠️ 跨解释器工具：`yolo_detect.py`

这是唯一一个"特殊"的工具，因为它要调另一个 Python 环境。

```
harness（系统 Python，无 torch）
   │  subprocess
   ▼
D:\envs\yolo\Scripts\python.exe  yolo\detect_cli.py
   │  ultralytics + torch(cu128)
   ▼
stdout 一行 JSON  →  harness 侧解析成自然语言
```

**为什么这么做**：torch / ultralytics 装在任务二的虚拟环境里，harness 用的是系统 Python
（只用标准库）。用子进程桥接，两边互不污染；`core` 完全无感。

**代价**：每次调用都要冷启动一次 Python 并加载模型（首次 ~13 秒，热缓存 ~2.5 秒）。
这是刻意接受的取舍——改成常驻服务会更快，但两边就耦合了。

**相关文件**：

| 文件 | 跑在哪 | 职责 |
|---|---|---|
| `yolo/detect_cli.py` | venv（`D:\envs\yolo`） | 读图/抓帧 → 推理 → 输出 JSON |
| `harness/tools/yolo_detect.py` | 系统 Python | 起子进程、解析 JSON、转成自然语言 |

**依赖**：`D:\envs\yolo` 必须存在且装了 torch/ultralytics；权重由 `model_loader.latest_weight()`
自动选最近一次训练的 `best.pt`。

## 怎么加一个新工具

1. 在 `tools/` 下新建 `xxx.py`，按上面的契约写 `NAME` / `SCHEMA` / `run()`
2. 在 `main.py` 里加一行：

```python
reg.register(xxx.NAME, xxx.SCHEMA, xxx.run)
```

`core/` 一个字都不用改。

## 写 description 的讲究

`description` 是模型唯一能看到的说明 —— **它靠这句话决定要不要调这个工具**。

- ❌ `"查时间"` —— 太短，模型不知道参数含义
- ✅ `"查询指定城市的当前时间"` —— 说清"做什么"和"要什么参数"

## 异常怎么处理

`run()` 里**不用**自己 try/except —— `core/executor.py` 会统一兜住异常，
把 `工具执行失败：xxx` 当作正常结果回灌给模型，让它自己纠偏。
