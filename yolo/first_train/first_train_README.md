# first_train/ · 第一次训练（示例数据）

用出题人提供的 **10 张示例图**（cat / dog）跑通的第一轮训练，目的是**验证整条管道能否走通**，
不是最终成果。完整流程、环境与卡点见 [`../yolo_README.md`](../yolo_README.md)。

## 训练配置

参数全部取自 [`../config/train.yaml`](../config/train.yaml)，**未做任何改动**（出题人默认值）：

| 项 | 值 |
|---|---|
| 模型 | `yolov8n.pt`（预训练权重） |
| 数据 | `../config/dataset.yaml` ｜ train 6 / val 3 / test 1 |
| 轮数 / 输入尺寸 / 批次 | 100 / 640 / 2 |
| 优化器 / AMP | auto（最终选 AdamW）/ 开 |
| 设备 | RTX 5070 Laptop（CUDA 12.8），**全程 GPU** |

## 训练结果

| 指标 | 值 |
|---|---|
| 训练轮数 | 100 epochs |
| 训练耗时 | 约 59 s |
| Precision | 0.981 |
| Recall | 0.986 |
| **mAP50** | **0.866** |
| mAP50-95 | 0.459 |

> ⚠️ 验证集只有 **3 张图 / 3 个目标**，这个数字**只说明"管道通了"**，不代表模型真实能力。
> 换成自有数据、扩大样本后需要重新评估。

## 目录内容

| 文件 | 说明 |
|---|---|
| `images/01_labeling.png` | X-AnyLabeling 打标界面（cat 框选） |
| `images/02_dataset_split.png` | `DataProess.py` 划分结果（总数 10 / 训练 6 / 验证 3 / 测试 1） |
| `images/03_train_result.png` | 训练终端：100 epochs 完成 + `best.pt` 复核指标 |
| `images/results.png` | **loss / mAP 曲线**（训练全过程） |
| `images/confusion_matrix.png` | 混淆矩阵（另有 `_normalized` 归一化版） |
| `images/Box*_curve.png` | P / R / F1 / PR 曲线 |
| `images/val_batch0_pred.jpg` | 验证集预测效果（`val_batch0_labels.jpg` 为原标注对照） |
| `images/train_batch*.jpg` | 训练批次样本（首尾各 3 张） |
| `images/labels.jpg` | 全数据集标注分布 |

权重 `best.pt` / `last.pt` 与原始 `results.csv` 保留在
`../runs/detect/runs/train/exp/`（体积大，已在根 `.gitignore` 中排除，不入库）。

## 复现

```bash
cd C:\Users\FU\Desktop\ai-interview\yolo
D:\envs\yolo\Scripts\python.exe main.py
```
