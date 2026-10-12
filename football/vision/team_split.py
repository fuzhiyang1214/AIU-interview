"""football/vision/team_split.py — 按球衣颜色把球员分成两队

职责：对每个球员框取「躯干」区域的颜色，聚成两类，输出每名球员属于哪一队。
输入：BGR 图像 + 球员框列表
输出：{0: {"color_bgr":.., "color_hsv":.., "members":[序号..]}, 1: {...}}

思路：
  1. 取球员框的躯干部分（纵向 20%~55%，横向 25%~75%），避开头部与腿部。
  2. 转 HSV，只保留「有色像素」（饱和度/亮度够高），取色调中位数 —— 抗光照。
  3. 把各球员的色调做 1D k-means（k=2），即分成两队。

局限（写进 README）：
  - 两队球衣颜色接近时（红 vs 橙）会分不开；
  - 裁判（通常黑/黄）可能被并进某一队；
  - 白色 / 黑色球衣没有色调信息，退化用亮度区分，效果一般。
"""
import cv2
import numpy as np


def _torso_hsv(frame, box) -> np.ndarray | None:
    """取一名球员躯干区域的颜色，返回 [H,S,V]；取不到返回 None。"""
    x1, y1, x2, y2 = [int(v) for v in box]
    h, w = y2 - y1, x2 - x1
    if h < 8 or w < 4:
        return None
    # 躯干：纵向 20%~55%，横向 25%~75%
    ty1, ty2 = y1 + int(0.20 * h), y1 + int(0.55 * h)
    tx1, tx2 = x1 + int(0.25 * w), x1 + int(0.75 * w)
    patch = frame[max(ty1, 0):max(ty2, 1), max(tx1, 0):max(tx2, 1)]
    if patch.size == 0:
        return None

    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV).reshape(-1, 3)
    sat, val = hsv[:, 1], hsv[:, 2]
    chroma = (sat > 40) & (val > 40)          # 只保留有颜色的像素（排除黑白灰）
    if chroma.sum() >= 10:
        sel = hsv[chroma]
        return np.array([float(np.median(sel[:, 0])),
                         float(np.median(sel[:, 1])),
                         float(np.median(sel[:, 2]))])
    # 没有颜色信息（白衣/黑衣）：退化用中位亮度，色调置 0
    return np.array([0.0, float(np.median(sat)), float(np.median(val))])


def _kmeans_hue(values: np.ndarray, k: int = 2, iters: int = 20):
    """对 1D 色调做 k-means，返回聚类中心（升序）。"""
    arr = np.sort(values.astype(float))
    centers = np.linspace(arr.min(), arr.max(), k)
    for _ in range(iters):
        labels = np.argmin(np.abs(arr[:, None] - centers[None, :]), axis=1)
        new = np.array([
            arr[labels == i].mean() if (labels == i).any() else centers[i]
            for i in range(k)
        ])
        if np.allclose(new, centers):
            break
        centers = new
    return np.sort(centers)


def split(frame, players: list) -> dict:
    """把球员按球衣颜色分成两队。

    Args:
        frame: BGR 图像。
        players: 球员框列表（[{xyxy:...}, ...]）。

    Returns:
        {0: {"color_hsv": [H,S,V], "members": [球员序号...]}, 1: {...}}
        球员不足 2 名时返回单队（全部归 0）。
    """
    turbos = [_torso_hsv(frame, p["xyxy"]) for p in players]

    def _norm(t):
        # 统一量纲：H 保持 0-180，S/V 从 OpenCV 的 0-255 归一到 0-1
        return None if t is None else [float(t[0]), float(t[1] / 255.0), float(t[2] / 255.0)]

    if len(players) < 2:
        return {0: {"color_hsv": _norm(turbos[0]) if turbos else None,
                    "members": list(range(len(players)))}}

    # 用色调做聚类；取不到颜色的球员用均值兜底
    hues = np.array([t[0] if t is not None else np.nan for t in turbos], float)
    valid = ~np.isnan(hues)
    if valid.sum() < 2:
        # 全都没颜色信息：退化为按亮度分
        vals = np.array([t[2] if t is not None else 0.0 for t in turbos], float)
        centers = _kmeans_hue(vals)
        basis = vals
    else:
        centers = _kmeans_hue(hues[valid])
        basis = hues

    # 为每个球员指派最近的聚类；缺失值用最近的有效球员补
    assign = []
    for i, v in enumerate(basis):
        if np.isnan(v):
            v = centers[0]
        assign.append(int(np.argmin(np.abs(centers - v))))

    groups = {0: [], 1: []}
    for i, g in enumerate(assign):
        groups[g].append(i)

    result = {}
    for g, members in groups.items():
        cols = [turbos[i] for i in members if turbos[i] is not None]
        color = _norm(np.mean(cols, axis=0)) if cols else None
        result[g] = {"color_hsv": color, "members": members}
    return result
