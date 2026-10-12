"""football/vision/detector.py — 球员 / 足球检测（复用任务二的 COCO 权重）

职责：只用 COCO 预训练的 yolov8n.pt，检测画面里的「人」和「球」。
输入：一帧 BGR 图像（numpy.ndarray）
输出：[{label, conf, xyxy}, ...]，只保留 person 与 sports ball

★ 关键前提：本模块**不做任何训练**。
  足球场上的人是 COCO 的 person 类（id 0），球是 sports ball 类（id 32），
  这两类本来就在 80 类预训练权重里 —— 换任务只换权重，不换代码。
"""
from pathlib import Path

from ultralytics import YOLO

# 仓库根：本文件 → vision → football → 仓库根
ROOT = Path(__file__).resolve().parents[2]
WEIGHT = ROOT / "yolo" / "yolov8n.pt"

# 只关心这两类，其余 78 类一律丢弃
KEEP = {"person", "sports ball"}

_model = None   # 进程内缓存，避免每次调用都重新加载权重


def load(device: str = "cuda:0") -> YOLO:
    """加载并缓存 YOLO 模型（进程内只加载一次）。"""
    global _model
    if _model is None:
        if not WEIGHT.is_file():
            raise FileNotFoundError(
                f"找不到 COCO 权重：{WEIGHT}\n"
                "该权重随任务二一起放在 yolo/ 目录，用于识别人与球。"
            )
        _model = YOLO(str(WEIGHT))
        _model.to(device)
    return _model


def detect(frame, conf: float = 0.35, imgsz: int = 1280,
           device: str = "cuda:0") -> list:
    """对一帧画面做检测，返回过滤后的目标列表。

    Args:
        frame: BGR 图像。
        conf: 置信度阈值，默认 0.35（比任务二的 0.25 略高，抑制误检）。
        imgsz: 推理尺寸，默认 1280 —— 球员目标偏小，放大尺寸能显著减少漏检。
        device: 'cuda:0' 或 'cpu'。

    Returns:
        [{"label": "person"|"sports ball", "conf": float, "xyxy": [x1,y1,x2,y2]}, ...]
    """
    model = load(device)
    result = model.predict(frame, imgsz=imgsz, conf=conf, verbose=False)[0]

    objects = []
    if result.boxes is not None:
        names = result.names
        for box in result.boxes:
            label = names[int(box.cls[0])]
            if label in KEEP:
                objects.append({
                    "label": label,
                    "conf": round(float(box.conf[0]), 3),
                    "xyxy": [round(float(v), 1) for v in box.xyxy[0].tolist()],
                })
    return objects
