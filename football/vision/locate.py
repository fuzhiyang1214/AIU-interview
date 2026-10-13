"""football/vision/locate.py — 分析前的预处理：裁球场、清看台、找球、定推理尺寸

为什么需要这一层（都是实测数据）：
  ① 截图往往是**整块桌面**（3072×1920），球在画面里只有 ~12px。同一帧实测：
       imgsz=1280 / 1920 / 2560 整图推理 → 球检不出来，只给出门将手套的误检
       先裁出球场区域再按长边 2.4 倍推到 imgsz=3200 → 球能出来，但置信度只有 0.29
     球检不出来，攻守就只能靠站位猜，结论会反过来 —— 这是「攻守判反了」的根因之一。
  ② 看台上的人也会被 COCO 认成 person，混进分队与「门将地标」里，
     实测把纵深轴整个带偏（门将明明在画面左侧，轴却指向右边）。
  ③ 于是找球改用「在球员脚边开小窗、窗内推理」：球在窗里足够大，
     同一帧置信度 0.29 → **0.78**，且窗口里没有它的对手（手套、看台）。

纯函数（不依赖 YOLO，可单独测）：
  pitch_roi(frame)             草坪色的最大连通块 → 球场区域的像素框
  auto_imgsz(size)             按球场长边换算推理尺寸（夹在 1280~3200，32 的整数倍）
  filter_crowd(frame, people)  剔掉脚不在草地上的（看台观众）
  pick_ball(balls, people)     整图候选的取舍（找球失败时的兜底）
  find_ball(frame, people)     在球员脚边开窗找球（主路径，需要 detector）
"""
import cv2
import numpy as np

from . import detector

# 草坪绿的 HSV 区间：收紧到「饱和的草绿」，界面的浅绿卡片、图标不会被误当成球场
GRASS_LO = (35, 90, 70)
GRASS_HI = (85, 255, 255)
MIN_AREA = 0.04      # 球场至少占画面 4%，否则认为找不到球场 → 不裁
MIN_RECT = 0.55      # 矩形度 = 连通块面积 / 外接框面积，低于此认为不是一整块球场
MARGIN = 0.03        # 裁切的四周外扩比例

SCALE = 2.4          # 推理尺寸 / 球场长边
IMGSZ_MIN, IMGSZ_MAX = 1280, 3200

BALL_TILE = (0.7, 0.1, 0.6)   # 找球小窗：以球员框为基准（左右外扩 0.7 宽、上收 0.1 高、下扩 0.6 高）
BALL_IMGSZ = 640              # 小窗内的推理尺寸（窗小，球在窗里就够大）
BALL_CONF = 0.25
BALL_MAX_PEOPLE = 20          # 只给框最大的这些人开窗（离镜头近的才可能拿球）
FEET_GRASS_MIN = 0.35         # 脚下一小块草地的占比低于此 → 认为是看台上的人


def pitch_roi(frame) -> tuple:
    """定位画面里的球场区域，返回像素框 (x1, y1, x2, y2)，四个值都是 Python int。

    找不到足够可信的球场时返回整幅画面 —— 宁可不裁，也不裁错。

    ⚠️ `cv2.connectedComponentsWithStats` 的 stats 是 **np.int32** 数组，
       直接把它当返回值会让 Flask `jsonify` 报
       「Object of type int32 is not JSON serializable」——
       而且这条路径只在「真找到球场」时才走到，普通照片（走 full 分支）测不出来。
       所以这里统一 `int()` 过一遍；坐标本来就是像素整数，转换无损。
    """
    h, w = frame.shape[:2]
    full = (0, 0, w, h)
    if frame.size == 0:
        return full

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, GRASS_LO, GRASS_HI)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))

    n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    if n <= 1:
        return full
    x, y, bw, bh, area = stats[1 + int(np.argmax(stats[1:, 4]))]
    x, y, bw, bh, area = int(x), int(y), int(bw), int(bh), int(area)
    if bw < 8 or bh < 8 or area < MIN_AREA * w * h:
        return full
    if area / float(bw * bh) < MIN_RECT:
        return full

    mx, my = int(bw * MARGIN), int(bh * MARGIN)
    return (max(x - mx, 0), max(y - my, 0),
            min(x + bw + mx, w), min(y + bh + my, h))


def auto_imgsz(size, scale: float = SCALE,
               lo: int = IMGSZ_MIN, hi: int = IMGSZ_MAX) -> int:
    """按画面长边反推推理尺寸（向上取 32 的整数倍，并夹在 lo~hi）。"""
    long_side = max(int(size[0]), int(size[1]))
    v = int(np.ceil(long_side * scale / 32.0) * 32)
    return int(min(hi, max(lo, v)))


def filter_crowd(frame, people: list) -> list:
    """剔掉「脚下不是草地」的检测框（典型：看台上的观众）。

    COCO 把人认得很全，看台观众照样是 person。他们混进来有两重代价：
      ① 人数虚高（实测 10 人变 17 人）、被当成「异色门将」；
      ② 门将地标被带偏 —— 实测纵轴判反，攻守跟着判反。
    判据：球员框底边中点周围一小块里，草地像素占比。真球员的脚一定在草地上。
    兜底：如果超过一半的人都被判成观众，说明草地掩膜这次不可靠 → 全部保留。
    """
    if not people:
        return people

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    grass = cv2.inRange(hsv, GRASS_LO, GRASS_HI)
    h, w = grass.shape[:2]

    kept = []
    for p in people:
        x1, y1, x2, y2 = p["xyxy"]
        bw, bh = x2 - x1, max(y2 - y1, 1.0)
        fx, fy = int((x1 + x2) / 2.0), int(y2)
        px, py = max(int(0.35 * bw), 3), max(int(0.12 * bh), 3)
        patch = grass[max(fy - py, 0):min(fy + py, h), max(fx - px, 0):min(fx + px, w)]
        ratio = float(patch.mean()) / 255.0 if patch.size else 0.0
        if ratio >= FEET_GRASS_MIN:
            kept.append(p)
    return kept if len(kept) * 2 >= len(people) else people


def find_ball(frame, people: list, device: str = "cuda:0",
              imgsz: int = BALL_IMGSZ, conf: float = BALL_CONF):
    """在球员脚边开小窗找球，返回置信度最高的候选 dict（含 label/conf/xyxy）或 None。

    这是找球的主路径。整图推理（哪怕 3200）对 ~12px 的球只有 0.29 的置信度，
    还常被门将手套、看台亮点压过；窗内推理能把球放大到足够大 —— 同一帧 0.78。
    """
    h, w = frame.shape[:2]
    cands = []
    for p in sorted(people, key=lambda q: -(q["xyxy"][2] - q["xyxy"][0]) * (q["xyxy"][3] - q["xyxy"][1]))[:BALL_MAX_PEOPLE]:
        x1, y1, x2, y2 = p["xyxy"]
        bw, bh = x2 - x1, max(y2 - y1, 1.0)
        wx1 = int(max(x1 - BALL_TILE[0] * bw, 0))
        wy1 = int(max(y1 + BALL_TILE[1] * bh, 0))
        wx2 = int(min(x2 + BALL_TILE[0] * bw, w))
        wy2 = int(min(y2 + BALL_TILE[2] * bh, h))
        tile = frame[wy1:wy2, wx1:wx2]
        if tile.size == 0:
            continue
        foot = ((x1 + x2) / 2.0 - wx1, y2 - wy1)
        for o in detector.detect(tile, conf=conf, imgsz=imgsz, device=device):
            if o["label"] != "sports ball":
                continue
            bx1, by1, bx2, by2 = o["xyxy"]
            cx, cy = (bx1 + bx2) / 2.0, (by1 + by2) / 2.0
            cands.append({"label": "sports ball", "conf": o["conf"],
                          "xyxy": [round(bx1 + wx1, 1), round(by1 + wy1, 1),
                                   round(bx2 + wx1, 1), round(by2 + wy1, 1)],
                          "_near": float(np.hypot(cx - foot[0], cy - foot[1]))})
    if not cands:
        return None
    top = max(c["conf"] for c in cands)
    # 置信度接近时（差 0.15 以内）以「离脚更近」为准：球总在人脚边
    best = min([c for c in cands if c["conf"] >= top - 0.15], key=lambda c: c["_near"])
    best.pop("_near", None)
    return best


def pick_ball(balls: list, people: list):
    """整图候选的兜底取舍（find_ball 没找到球时才用）；没有候选返回 None。

    评分优先级：① 是否有球员框把它罩住（球在脚下）② 置信度 ③ 离球员脚底的距离。
    单看置信度分不开：真球 0.50 只比门将手套的误检 0.48 高一点点。
    """
    if not balls:
        return None

    def score(b):
        cx = (b["xyxy"][0] + b["xyxy"][2]) / 2.0
        cy = (b["xyxy"][1] + b["xyxy"][3]) / 2.0
        inside, near = 0, float("inf")
        for p in people:
            x1, y1, x2, y2 = p["xyxy"]
            bw, bh = x2 - x1, max(y2 - y1, 1.0)
            if (x1 - 0.15 * bw <= cx <= x2 + 0.15 * bw
                    and y1 + 0.35 * bh <= cy <= y2 + 0.15 * bh):
                inside = 1
            near = min(near, float(np.hypot(cx - (x1 + x2) / 2.0, cy - y2)))
        return (inside, b["conf"], -near / 100.0)

    return max(balls, key=score)
