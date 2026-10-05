# yolo/ · 视觉处理链

任务二：用自采数据训练目标检测模型，并调用摄像头实时推理。

**当前状态**：主流程已跑通（打标 → 转标注 → 划分 → 训练），第一轮训练已完成并归档到
[`first_train/`](first_train/first_train_README.md)；待补**摄像头实时推理**。

## 技术路线

沿用出题人博客《【小白】【超详细】从零开始搭建自己的 YOLO》及其配套仓库
[`Linmoqian/yolo_train`](https://github.com/Linmoqian/yolo_train) 的现成流程：

```
your_data/  图片 + json 标注
   ├─ script/json2txt.py     json → YOLO txt（CLASSES 须与 dataset.yaml 的 names 一致）
   ├─ script/DataProess.py   划分 train / val / test
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
| 标注工具 | X-AnyLabeling（`Windows-CUDA12` 版，exe 双开即用） |
| 训练参数 | yolov8n ｜ imgsz=640 ｜ batch=2 ｜ epochs=100 ｜ nc=2（cat / dog） |

装环境（在 D 盘建独立环境，避免占系统盘）：

```bash
python -m venv D:\envs\yolo
source /d/envs/yolo/Scripts/activate
pip install --index-url https://download.pytorch.org/whl/cu128 torch torchvision
pip install ultralytics
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

## 踩坑记录（三处对出题人原版的必要偏离）

1. **必须用 cu128 的 wheel**。RTX 5070 是 Blackwell（sm_120），CUDA 12.7 及以下的预编译包跑起来会报
   `no kernel image is available for execution on the device`。
2. **用 venv 而非 Miniforge**。本机 C 盘紧张，Miniforge 默认装 C 盘且体积大；
   `venv` 可整体建在 D 盘，隔离、好删，也不动系统 Python。
3. **`main.py` 必须加 `if __name__ == '__main__':` 保护**（出题人原版没有）。

   - **现象**：训练在 `Plotting labels ...` 之后中断，`runs/.../exp-N/` 里只留下 `args.yaml` 和 `labels.jpg`，
     **从不生成 `weights/best.pt`**；终端报
     ```
     RuntimeError: DataLoader worker (pid(s) ...) exited unexpectedly
     ```
   - **根因**：Windows 下 DataLoader 用 **spawn** 启动子进程，子进程会**重新导入 `__main__`**。
     `main.py` 顶层没有入口保护，于是子进程又执行了一遍 `YOLO(...).train(...)` → 递归 → worker 崩溃。
     真正的错误在子进程里：`An attempt has been made to start a new process before the current process has finished its bootstrapping phase`。
   - **修法**：把训练逻辑包进 `def main():`，再用 `if __name__ == '__main__': main()` 启动
     （同时满足出题人规范「主程序只负责模块的组装」）。Linux 用 fork 不受影响，所以原版能跑。

> 另注：训练前 ultralytics 会为 AMP 检查**联网下载一次 `yolo26n.pt`**（约 5 MB），
> 属正常行为；本机已缓存，**训练过程不需要联网**。

## 使用步骤

数据已就绪，直接复现训练：

```bash
cd C:\Users\FU\Desktop\ai-interview\yolo
D:\envs\yolo\Scripts\python.exe script\json2txt.py      # json 标注 → YOLO txt
D:\envs\yolo\Scripts\python.exe script\DataProess.py    # 划分 train / val / test
D:\envs\yolo\Scripts\python.exe main.py                 # 训练
```

> ① 三条命令的**工作目录必须停在 `yolo\`**：`main.py` 里 `config/...` 与
> `dataset.yaml` 里的 `path: dataset` 都是相对路径，换目录会报找不到数据集。
> ② 用 `python.exe` 全路径可绕开 PowerShell 执行策略对 `Activate.ps1` 的拦截。

打标（重新造数据时才需要）：用 X-AnyLabeling 打开 `your_data/`，矩形框标注，
标签**只能**是小写 `cat` / `dog`（大小写不符会被 `json2txt.py` 静默跳过），
`Ctrl+S` 保存为同名 `.json`。

## 第一次训练结果

用出题人给的 **10 张示例图**跑通的一轮训练，产物归档在 [`first_train/`](first_train/first_train_README.md)。
所有参数为默认值（100 epochs / imgsz 640 / batch 2），耗时约 **59 s**：

| 指标 | 值 |
|---|---|
| Precision | 0.981 |
| Recall | 0.986 |
| **mAP50** | **0.866** |
| mAP50-95 | 0.459 |

> ⚠️ 验证集仅 3 张图，指标**只用于确认管道打通**，不代表真实性能。

![训练曲线](first_train/images/results.png)

![训练完成](first_train/images/03_train_result.png)

## 目录结构

| 路径 | 内容 |
|---|---|
| `yolo_README.md` | 本说明（环境、路线、卡点、步骤） |
| `main.py` | 训练入口（组装模型 + 配置 + 参数） |
| `config/train.yaml` | 训练超参数（epochs / imgsz / batch …） |
| `config/dataset.yaml` | 数据集路径与类别（`nc=2`，`cat` / `dog`） |
| `script/json2txt.py` | 标注转换（json → YOLO txt） |
| `script/DataProess.py` | 数据集划分（train 6 / val 3 / test 1） |
| `your_data/` | 原始图片 + json + 转换后的 txt |
| `first_train/` | 第一次训练的产物归档（说明 + 截图 + 曲线） |
| `dataset/` `runs/` `*.pt` | 训练与划分产物，**仓库不提交**（见根 `.gitignore`） |

## 进度

| 日期 | 内容 |
|---|---|
| 10-04~05 | 对照出题人博客与仓库确定路线；建 `D:\envs\yolo`；装好 torch 2.11.0+cu128 + ultralytics 8.4.173，`cuda.is_available()` 验证通过；下载 X-AnyLabeling（CUDA12 版）；素材与脚本拷入本目录 |
| 10-05 | X-AnyLabeling 标注 10 张图（标签全部 `cat` / `dog`）；`json2txt.py` 转出 10 个 txt；`DataProess.py` 划分 6 / 3 / 1；删掉 `main.py` 里引发 `SyntaxWarning` 的 ASCII art |
| 10-06 | 定位并修复 Windows 多进程入口保护问题（见踩坑 3）；**训练跑通**（100 epochs，mAP50 0.866），产物归档至 `first_train/` |

## 待办

- [x] 用 X-AnyLabeling 标注 10 张图（类名与 `dataset.yaml` 的 `names` 对齐）
- [x] `python script/json2txt.py` → `python script/DataProess.py`
- [x] `python main.py` 训练跑通，产出 `best.pt` 与 `results.png`
- [x] 训练产物与截图归档到 `first_train/`
- [ ] 摄像头实时推理 demo（`best.pt` + OpenCV，出题人点名要求）
