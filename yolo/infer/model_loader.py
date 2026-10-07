# model_loader.py
# 模型加载模块：只负责把 best.pt 读成可调用的 YOLO 对象。
# 把"模型从哪来、怎么加载"收敛在一处，后端与前端都不需要关心权重路径。
#
# 权重位置：每跑一次 main.py，ultralytics 都会在 runs/detect/runs/train/ 下
#           新建一个实验目录（exp、exp-2、exp-3 …），权重在其中 weights/best.pt。
#           本模块默认自动挑「最近一次训练」的 best.pt，
#           所以重新训练之后，不需要改任何代码。

from pathlib import Path

from ultralytics import YOLO

# 所有实验目录的根（相对本文件定位，换工作目录也能找到）
WEIGHTS_ROOT = Path(__file__).resolve().parent.parent / "runs" / "detect" / "runs" / "train"


def latest_weight(root: Path = WEIGHTS_ROOT) -> Path:
    """返回最近一次训练产出的 best.pt（按文件修改时间取最新）。

    Args:
        root: 实验目录根，默认 runs/detect/runs/train。

    Returns:
        最新的 best.pt 路径。

    Raises:
        FileNotFoundError: 该目录下没有任何 best.pt（通常是还没训练）。
    """
    candidates = sorted(root.glob("exp*/weights/best.pt"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"在 {root} 下找不到任何 best.pt，请先跑 main.py 完成训练。")
    return candidates[-1]


def load_model(weight: Path | str | None = None, device: str = "cuda:0") -> YOLO:
    """加载 YOLO 权重并绑定推理设备。

    Args:
        weight: 权重文件路径；默认 None，表示自动取最近一次训练的 best.pt。
        device: 推理设备，'cuda:0' 用 GPU，'cpu' 用 CPU。

    Returns:
        已加载好的 YOLO 实例。

    Raises:
        FileNotFoundError: 权重文件不存在（通常是还没训练）。
    """
    weight = Path(weight) if weight else latest_weight()
    if not weight.is_file():
        raise FileNotFoundError(f"找不到权重文件：{weight}\n请先跑 main.py 完成训练。")

    model = YOLO(str(weight))
    model.to(device)
    return model
