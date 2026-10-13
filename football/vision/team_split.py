"""football/vision/team_split.py — 按球衣颜色把球员分成两队

职责：给每名球员估计「球衣色」，聚成两队；不属于任何一队的（异色门将 / 裁判 /
      取样不可靠者）标为 gk / unknown，由上层（pitch）不计入攻防统计。
输入：BGR 图像 + 球员框列表
输出：(groups, roles)
    groups = {0: {"color_hsv": [H,S,V]|None, "members": [序号..]}, 1: {...}}
    roles  = ["outfield" | "gk" | "unknown", ...]     下标与传入 players 对齐

思路（v2，2026-10-13 重写）：
  1. 取样区 = 胸部（纵向 15%~40%、横向 35%~65%）。
     原先的 20%~55% / 25%~75% 太大，在真实直播帧里会吃进大量草地
     —— 实测取样区内草地像素占 7%~69%，是「蓝队球员被判成红队」的主因。
  2. 先估「草地色」：取画面四周 14px 边框的中位 HSV。取样时剔除色相接近、
     且亮度也接近的像素。
  3. 有彩球衣：36 桶色相直方图取**主峰**当球衣色，并记录主峰占比（纯度）。
     用主峰而不是中位数 —— 少量被污染的像素拖不动主峰。
  4. 无彩球衣（黑 / 白）：走**亮度通道** —— 取低饱和（S≤60）像素的亮度中位数。
     黑衣（裁判）的球衣 S、V 都低，会被 (S>40)&(V>40) 整个筛掉；
     旧实现在这种情况下回退成「色调 = 0」，正好与红队（H≈0~16）撞车。
  5. 两队色心同样用直方图主峰，而不是 k-means 均值
     —— 实测均值色心 27/84，真值约 16/98，被污染样本整体拖偏 10 度以上。
  6. 归不了队的两种情形：
       · 色相离两队色心都 > gk_tol  → gk（异色球衣，最可能是门将）
       · 纯度不足 / 取样太少 / 黑白但与两队亮度都对不上 → unknown（裁判、遮挡、太远）
     两者都不计入攻防统计，画面上一律画灰框。
"""
import cv2
import numpy as np

# ---- 可调参数（都收在这里，便于按素材调） ----
CHEST_Y = (0.15, 0.40)      # 取样区纵向比例（胸部）
CHEST_X = (0.35, 0.65)      # 取样区横向比例
MIN_CHROMA_PX = 15          # 有彩像素少于这个数就不承认色相
MIN_PURITY = 0.45           # 主峰占比低于这个数视为「杂色」
GRASS_BAND = 12.0           # 与草地色相差在此范围内视为草地
GRASS_V_TOL = 75.0          # 且亮度也接近，才排除
DARK_V = 75                 # 低饱和像素亮度低于此 → 深色球衣
LIGHT_V = 165               # 高于此 → 浅色球衣
V_TOL = 60                  # 黑白球员与某队平均亮度差在此内才归队
GK_TOL = 22.0               # 色相离两队都超过此值 → 判为异色（门将）。
                            # 28 → 22：真实直播帧里深色球衣的门将取样常被草地暗部污染，
                            # 采出的色相离本队色心约 23°，28 太宽会把它吸进某一队。
PEAK_SEP = 30.0             # 两个队色主峰的最小间隔


def _ring(a: float, b: float) -> float:
    """色相是 0~180 的环，取环形距离。"""
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


def _grass_ref(frame, band: int = 14):
    """从画面四周边框估计草地色，返回 (H, V)；取不到返回 None。"""
    h, w = frame.shape[:2]
    parts = [frame[0:band, :], frame[-band:, :], frame[:, 0:band], frame[:, -band:]]
    parts = [p for p in parts if p.size]
    if not parts:
        return None
    hsv = np.vstack([cv2.cvtColor(p, cv2.COLOR_BGR2HSV).reshape(-1, 3)
                     for p in parts]).astype(float)
    chroma = hsv[(hsv[:, 1] > 40) & (hsv[:, 2] > 40)]
    if len(chroma) < 30:
        return None
    return float(np.median(chroma[:, 0])), float(np.median(chroma[:, 2]))


def _shirt(frame, box, grass) -> dict:
    """估计一名球员的球衣色。

    Returns:
        {"kind": "chroma"|"dark"|"light"|"none", "hue": float|None,
         "purity": float, "n": int, "val": float|None}
    """
    x1, y1, x2, y2 = [int(v) for v in box]
    h, w = y2 - y1, x2 - x1
    out = {"kind": "none", "hue": None, "purity": 0.0, "n": 0, "val": None}
    if h < 10 or w < 6:
        return out

    py1 = y1 + int(CHEST_Y[0] * h)
    py2 = y1 + max(int(CHEST_Y[1] * h), int(CHEST_Y[0] * h) + 1)
    px1 = x1 + int(CHEST_X[0] * w)
    px2 = x1 + max(int(CHEST_X[1] * w), int(CHEST_X[0] * w) + 1)
    patch = frame[max(py1, 0):max(py2, 1), max(px1, 0):max(px2, 1)]
    if patch.size == 0:
        return out

    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(float)
    hue, sat, val = hsv[:, 0], hsv[:, 1], hsv[:, 2]

    chroma = (sat > 40) & (val > 40)
    if grass is not None:
        gh, gv = grass
        d = np.minimum(np.abs(hue - gh), 180 - np.abs(hue - gh))
        chroma = chroma & ~((d < GRASS_BAND) & (np.abs(val - gv) < GRASS_V_TOL))

    out["n"] = int(chroma.sum())
    if out["n"] >= MIN_CHROMA_PX:
        bins = (hue[chroma] // 5).astype(int) % 36
        cnt = np.bincount(bins, minlength=36)
        peak = int(np.argmax(cnt))
        band = (bins == peak) | (bins == (peak - 1) % 36) | (bins == (peak + 1) % 36)
        hb = hue[chroma][band]
        m = float(hb.mean())
        out["hue"] = float(min(hb, key=lambda t: _ring(t, m)))
        out["purity"] = float(band.mean())
        out["val"] = float(np.median(val[chroma]))
        if out["purity"] >= MIN_PURITY:
            out["kind"] = "chroma"

    if out["kind"] != "chroma":
        # 亮度通道：低饱和像素基本就是黑/白球衣（草地是有彩的，落在 neutral 之外）
        neutral = sat <= 60
        if int(neutral.sum()) >= 8:
            vn = float(np.median(val[neutral]))
            out["val"] = vn
            if vn < DARK_V:
                out["kind"] = "dark"
            elif vn > LIGHT_V:
                out["kind"] = "light"
    return out


def _kmeans_hue(values, k: int = 2, iters: int = 20) -> np.ndarray:
    """对 1D 数值做 k-means，返回聚类中心（升序）。"""
    arr = np.sort(np.asarray(values, float))
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


def _two_peaks(hues: list, sep: float = PEAK_SEP):
    """在色相直方图上找两个主峰（间隔需 > sep），返回 (c1, c2)；找不到返回 None。"""
    if len(hues) < 2:
        return None
    hist = np.zeros(36)
    for h in hues:
        hist[int(h // 5) % 36] += 1
    sm = np.convolve(np.r_[hist[-1], hist, hist[0]], [0.25, 0.5, 0.25], "valid")
    p1 = int(np.argmax(sm))
    c1p = p1 * 5 + 2.5
    allow = np.array([_ring(b * 5 + 2.5, c1p) > sep for b in range(36)])
    if not allow.any():
        return None
    p2 = int(np.argmax(np.where(allow, sm, -1)))
    if sm[p2] <= 0 or _ring(p2 * 5 + 2.5, c1p) <= sep:
        return None
    # 平票时（样本少很常见）选离 p1 更远的那个 —— 两个队色被拉开才是我们想要的
    top = sm[p2]
    tied = [b for b in range(36) if allow[b] and sm[b] >= top - 1e-9]
    p2 = max(tied, key=lambda b: _ring(b * 5 + 2.5, c1p))

    def refine(p):
        pv = p * 5 + 2.5
        v = [h for h in hues if _ring(h, pv) <= 12.5]
        if not v:
            return pv
        m = float(np.mean(v))
        return float(min(v, key=lambda t: _ring(t, m)))

    return refine(p1), refine(p2)


def _team_color(shirts: list, members: list):
    """把一组球员的球衣色归一到对外口径（H 0-180，S/V 0-1）。"""
    hs = [shirts[i]["hue"] for i in members if shirts[i]["hue"] is not None]
    vs = [shirts[i]["val"] for i in members if shirts[i]["val"] is not None]
    if not hs or not vs:
        return None
    return [float(np.mean(hs)), float(np.mean(vs) / 255.0), float(np.mean(vs) / 255.0)]


def split(frame, players: list, gk_tol: float = GK_TOL) -> tuple:
    """把球员按球衣颜色分成两队。

    Args:
        frame: BGR 图像。
        players: 球员框列表（[{xyxy:...}, ...]）。
        gk_tol: 色相离两队色心都超过此值 → 判为异色球员（门将）。

    Returns:
        (groups, roles)
        groups: {0: {"color_hsv":.., "members":[序号..]}, 1: {...}}
                members 只含已归队的球员。
        roles:  每个球员的角色，outfield / gk / unknown。
    """
    n = len(players)
    if n == 0:
        return {}, []

    grass = _grass_ref(frame)
    shirts = [_shirt(frame, p["xyxy"], grass) for p in players]
    roles = ["unknown"] * n
    team = [-1] * n

    chroma_idx = [i for i in range(n) if shirts[i]["kind"] == "chroma"]

    centers = _two_peaks([shirts[i]["hue"] for i in chroma_idx]) if len(chroma_idx) >= 4 else None
    if centers is None and len(chroma_idx) >= 2:
        # 人太少时直方图峰值不稳，退回 1D k-means（仍保留纯度门槛）
        centers = tuple(float(c) for c in
                        _kmeans_hue(np.array([shirts[i]["hue"] for i in chroma_idx])))
    if centers is not None and _ring(centers[0], centers[1]) < 5.0:
        # 两个色心几乎重合 = 两队球衣同色，硬分只会制造假象 → 交给亮度兜底
        centers = None

    if centers is not None:
        for i in chroma_idx:
            d1, d2 = _ring(shirts[i]["hue"], centers[0]), _ring(shirts[i]["hue"], centers[1])
            if min(d1, d2) <= gk_tol:
                team[i] = 0 if d1 <= d2 else 1
                roles[i] = "outfield"
            else:
                roles[i] = "gk"
        # 黑白球衣：按亮度靠到已有两队（两队本身都不是黑白时自然靠不上 → unknown）
        ref = {}
        for t in (0, 1):
            vs = [shirts[i]["val"] for i in range(n)
                  if team[i] == t and shirts[i]["val"] is not None]
            ref[t] = float(np.median(vs)) if vs else None
        for i in range(n):
            if shirts[i]["kind"] not in ("dark", "light") or shirts[i]["val"] is None:
                continue
            v = shirts[i]["val"]
            cand = [(abs(v - ref[t]), t) for t in (0, 1) if ref[t] is not None]
            if not cand:
                continue
            dv, t = min(cand)
            if dv <= V_TOL:
                team[i] = t
                roles[i] = "outfield"
            else:
                roles[i] = "unknown"          # 黑白但与两队亮度都对不上（典型：黑衣裁判）
    else:
        # 两队都没有可用的色相信息 → 退化为按亮度分
        vals = [shirts[i]["val"] for i in range(n)]
        usable = [i for i in range(n) if vals[i] is not None]
        if len(usable) >= 2:
            cs = _kmeans_hue(np.array([vals[i] for i in usable], float))
            if cs[1] - cs[0] >= 25:
                for i in usable:
                    team[i] = 0 if abs(vals[i] - cs[0]) <= abs(vals[i] - cs[1]) else 1
                    roles[i] = "outfield"

    if all(t == -1 for t in team):
        # 完全分不开：全部交给 0 队，让上层给出「只识别出一方」的判定
        for i in range(n):
            team[i] = 0
            roles[i] = "outfield"

    groups = {}
    for t in (0, 1):
        members = [i for i in range(n) if team[i] == t]
        groups[t] = {"color_hsv": _team_color(shirts, members), "members": members}
    return groups, roles
