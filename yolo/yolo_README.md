# yolo/ · 视觉处理链

任务二：用自采数据训练目标检测模型，并调用摄像头实时推理。
**路线已定、环境就绪**，待标注与训练。



## 技术路线

沿用出题人博客《【小白】【超详细】从零开始搭建自己的 YOLO》及其配套仓库
[`Linmoqian/yolo_train`](https://github.com/Linmoqian/yolo_train) 的现成流程：

```
your_data/  图片 + json 标注
   ├─ script/json2txt.py     json → YOLO txt（CLASSES 须与 dataset.yaml 的 names 一致）
   ├─ script/DataProess.py   划分 train / val
   └─ main.py                读 config/train.yaml 训练
```

本机只在**环境**与**数据**上适配，流程本身不改。

## 运行环境

| 项 | 值 |
|---|---|
| 虚拟环境 | `D:\envs\yolo`（官方 Python 3.14 + `venv`） |
| PyTorch | 2.11.0+cu128 ｜ CUDA 12.8（`torch.cuda.is_available() = True`） |
| Ultralytics | 8.4.173 ｜ OpenCV 5.0.0 |
| GPU | RTX 5070 Laptop（Blackwell / sm_120） |
| 标注工具 | X-AnyLabeling（`Windows-CUDA12` 版） |
| 训练参数 | yolov8n ｜ imgsz=640 ｜ batch=2 ｜ epochs=100 ｜ nc=2（cat / dog） |

两条踩坑记录：

- **必须用 cu128 的 wheel**。RTX 5070 是 Blackwell（sm_120），CUDA 12.7 及以下的预编译包跑起来会报
  `no kernel image is available for execution on the device`。
- **用 venv 而非 Miniforge**。本机 C 盘紧张，Miniforge 默认装 C 盘且体积大；
  `venv` 可整体建在 D 盘，隔离、好删，也不动系统 Python。

装环境（在 D 盘建独立环境，避免占系统盘）：

```bash
python -m venv D:\envs\yolo
source /d/envs/yolo/Scripts/activate
pip install --index-url https://download.pytorch.org/whl/cu128 torch torchvision
pip install ultralytics
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

## 目录规划

| 路径 | 内容 |
|---|---|
| `yolo_README.md` | 本说明（环境、路线、进度） |
| `main.py` `config/` `script/` | 训练入口与脚本（待从 `yolo_train` 仓库拷入） |
| `your_data/` | 原始图片与 json 标注（待拷入并打标） |
| `dataset/` `runs/` `*.pt` | 训练与划分产物，仓库不提交。根 `.gitignore` 已含 `runs/`、`*.pt`，**`dataset/` 需补一行** |

> 素材（10 张图 + `main.py` + `config/` + `script/`）目前放在 D 盘的参考克隆
> `D:\X\yolo_train`，打标阶段再挑需要的拷进本目录。

## 进度

| 日期 | 内容 |
|---|---|
| 10-04~05 | 对照出题人博客与仓库确定路线；建 `D:\envs\yolo`；装好 torch 2.11.0+cu128 + ultralytics 8.4.173，`cuda.is_available()` 验证通过；下载 X-AnyLabeling（CUDA12 版）；定位素材与脚本 |

## 待办

- [ ] 打标：用 X-AnyLabeling 标注 10 张图（类名与 `dataset.yaml` 的 `names` 对齐）
- [ ] `python script/json2txt.py` → `python script/DataProess.py`
- [ ] `python main.py` 训练，留存 `results.png` / 权重
- [ ] 摄像头实时推理 demo
- [ ] 训练产物与截图回填 README / log
