# vision/ · 视觉分析层

把「画面」变成「谁在哪、谁在进攻、哪条通道空」。**纯计算**，不碰网络与 LLM。

```
球员/足球检测  →  球衣分两队  →  攻防态势 + 空当判读
 detector.py      team_split.py     pitch.py
```

| 文件 | 职责 |
|---|---|
| `detector.py` | 加载 COCO `yolov8n.pt`，只保留 `person` 与 `sports ball` |
| `team_split.py` | 取球员躯干颜色 → 1D k-means 分两队 |
| `pitch.py` | 由两队位置 + 球的位置推断攻防态势、空当通道与静态发展线索 |
| `__init__.py` | 串起三步，输出结构化字典 + 带标注的图（`analyze_image`） |

## 关键设计

- **零训练**：用 COCO 权重里本就存在的 `person` / `sports ball` 两类。
- **攻防判据（两条路，优先用更硬的证据）**：
  1. 球若检出 → 球进了哪一侧半场，就是哪一侧在挨打，另一方在压上；
  2. 球若未检出 → **越线人数**：以画面中线（≈球场中线）为界，
     谁有更多人越过中线进入对方半场，谁就在压上。
- **空当判据**：把画面横向分「左/中/右」三通道，看**防守方**哪条通道人数最少。
- **不做阵型命名**：只给「上/中/下三区人数」这种可解释的分布，不硬套 `4-3-3`。
- **量纲统一**：内部聚类用 OpenCV 的 HSV（S/V 0-255），对外输出归一到 0-1。

## 对外接口

```python
from vision import analyze_image, to_base64_jpeg
analysis, annotated = analyze_image(frame, conf=0.35, imgsz=1280, device="cuda:0")
```

`analysis` 主要字段：

| 字段 | 含义 |
|---|---|
| `counts` | 球员总数与两队人数 |
| `state` / `attacking_team` / `sides` | 攻防态势：进攻 / 相持；进攻方与防守方队号 |
| `direction` / `reason` | 推进方向（向上/向下）与判定依据（一句话） |
| `dist` | 两队「上/中/下」三区人数分布 |
| `gap_channel` / `defender_channels` | 防守方最空的通道及各通道人数 |
| `ball` | 球是否检出、所在区与通道 |
| `cues` | 给上层 LLM 的事实碎片 |

## 局限

- 视角要求侧高/高位；纯俯视会漏检。
- 球衣颜色接近或包含裁判（黑/黄）时，分队可能出错。
- **球的检测不可靠**：`sports ball` 在本场景常失效 —— 因此攻防判定优先走「越线人数」，
  不把结论押在球上。详见 `pitch.py` 顶部注释。
