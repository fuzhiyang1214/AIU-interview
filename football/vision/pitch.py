"""football/vision/pitch.py — 由球员位置推断攻防态势与「球可能的发展」（v3）

职责：把「谁在哪、球在哪」翻译成「谁在进攻、谁在防守、球接下来可能往哪走」。

★ v3 改了什么、为什么改（v2 会把攻防判反，实测复盘）：
  v2 用「画面纵轴 = 球场纵深、画面中线 = 球场中线」+「两队质心各自占半场」推谁在压上。
  两个硬伤：
    ① 机位不一定是纵向的。侧高位机位下球场纵深其实是**横轴**（实测那帧球门在画面左侧），
       于是「越线人数」统计的是画面上下 —— 一条与攻防无关的轴。
    ② 「谁占哪半场」是拿质心反推的（循环论证）。一旦两队挤在同一侧（比如一方全压上），
       归属就整体翻过来。实测：球明明在浅蓝队 11 号脚下，却被判成红队在进攻。
  改为三条：
    ① **谁控球，谁进攻** —— 球到最近球员的距离 < 1.2 倍身高才算「在他脚下」。
       控球是定义「进攻方」最直接的一手，且与机位、朝向无关。
    ② 纵深轴不再假设，用**门将地标**估：门将站在本方球门，纵深方向 = 门将 → 场上球员质心；
       垂直于它的方向就是通道轴。输出里带上方向词（左/中/右 或 上/中/下），
       读者能直接把数字对回画面。
    ③ 球没检出就不判攻守（相持），只给站位事实 —— 宁可说「不知道」，不给反的结论。
       例外：战术板（无门将、无 role 字段）仍走 v2 的「越线人数」，
       因为那块画布的朝向是约定死的（y=0 = 对方球门），不存在朝向不确定的问题。
"""
import math

import numpy as np

# 球离球员中心的距离小于「身高的这个倍数」才算在该球员脚下
BALL_OWNER_GAP = 1.2
# 没有门将地标时的默认纵深轴：画面向下 = 由远及近（战术板画布按这个约定画）
DEFAULT_DEPTH = (0.0, 1.0)


def _centroid(box):
    x1, y1, x2, y2 = box
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def _proj(p, v) -> float:
    """点 p 在单位向量 v 上的投影。"""
    return p[0] * v[0] + p[1] * v[1]


def _dir_labels(v) -> list:
    """把「沿线递增」的方向向量翻成三个画面方位词。

    d=(1,0) → ['左','中','右']；d=(0,-1) → ['下','中','上']。
    这三个词是给读者对画面用的，不是给坐标用的。
    """
    vx, vy = v
    if abs(vx) >= abs(vy):
        return ["左", "中", "右"] if vx >= 0 else ["右", "中", "左"]
    return ["上", "中", "下"] if vy >= 0 else ["下", "中", "上"]


def _band(v, lo, hi) -> int:
    """投影值归一化后落在第几段（0/1/2）。"""
    r = (v - lo) / max(hi - lo, 1e-6)
    if r < 1 / 3:
        return 0
    return 2 if r > 2 / 3 else 1


def _span(v, size):
    """沿方向 v 的投影跨度：用画面四角，这样三段就是「画面沿该轴的三等分」。"""
    w, h = size
    vals = [_proj((x, y), v) for x in (0, w) for y in (0, h)]
    return min(vals), max(vals)


def _axis(live: bool):
    """定纵深轴。

    两条输入路径的画法约定不同，各用各的（都不靠猜）：
      · 真实画面：转播镜头沿球场长边取景 —— 球门在画面左右两翼，
                 所以**纵深 = 画面横轴**，通道 = 画面纵轴。
      · 战术板：画布按战术图惯例画 —— 球门在上下两端（y=0 是对方球门），
                 所以纵深 = 画布纵轴，通道 = 画布横轴。

    为什么不再拿「门将地标」估轴：门将的归属本身就要靠颜色猜（实测同一帧两种分辨率下
    判出的门将一个对被归队、一个被踢出），拿它当基准会把整条轴带偏 —— 实测轴指向了
    与球门相反的一侧。朝向这件事宁可约定死，也不要半可靠的推断。

    Returns:
        (d, note)：d 为单位纵深向量，note 为口径说明。
    """
    if live:
        return (1.0, 0.0), "转播机位约定：纵深 = 画面横轴（球门在两翼），通道 = 画面纵轴"
    return DEFAULT_DEPTH, "战术板约定：纵深 = 画布纵轴（y=0 为对方球门）"


def analyze(players: list, teams: dict, ball: dict | None, size) -> dict:
    """综合球员与球的位置，得出攻防态势与静态发展线索。

    Args:
        players: 球员列表，每项含 xyxy 与 team。
                 team == 0/1 才参与统计；team = -1（异色门将 / 裁判 / 分不出队者）
                 一律跳过 —— 他们不属于任何一方的攻防结构，混进来会把人数与质心带偏。
                 图像路径的每项还带 role（outfield / gk / unknown）：
                 有 role 字段视为「真实画面」，没有则视为「战术板」（朝向由画布约定）。
        teams: team_split.split() 的结果（本层只用分组，不用颜色）。
        ball: 球的框 dict（{"xyxy":[...]}）或 None。
        size: (width, height)。

    Returns:
        结构化态势字典（字段见 vision_README.md）。坐标口径全部是传进来那幅图的像素。
    """
    W, H = size

    by_team = {0: [], 1: []}
    by_team_box = {0: [], 1: []}
    excluded = 0
    for p in players:
        t = p.get("team")
        if t in by_team:
            by_team[t].append(_centroid(p["xyxy"]))
            by_team_box[t].append(p)
        else:
            excluded += 1
    live = any("role" in p for p in players)      # 图像路径才有 role 字段

    # ---------------- 坐标轴：纵深 / 通道 ----------------
    d, axis_note = _axis(live)
    nrm = (d[1], -d[0])                            # 通道轴 = 纵深轴转 90°
    d_lo, d_hi = _span(d, size)
    c_lo, c_hi = _span(nrm, size)
    depth_labels = _dir_labels(d)
    channel_labels = _dir_labels(nrm)

    # ---------------- 球 ----------------
    ball_xy = _centroid(ball["xyxy"]) if ball else None
    ball_band = channel_band = None
    if ball_xy is not None:
        ball_band = depth_labels[_band(_proj(ball_xy, d), d_lo, d_hi)]
        channel_band = channel_labels[_band(_proj(ball_xy, nrm), c_lo, c_hi)]

    # ---------------- 攻守判定 ----------------
    attacking = defending = None
    basis = "none"                                 # ball / position / none
    owner = owner_gap = None
    reason = "画面里只识别出一方球员，无法比较攻防。"

    # ① 球权优先：球在谁脚下，谁就是进攻方（与机位朝向无关）
    if ball_xy is not None:
        best = None                                # (距离, 队号, 距离/身高)
        for t in (0, 1):
            for p in by_team_box[t]:
                c = _centroid(p["xyxy"])
                dist = math.hypot(ball_xy[0] - c[0], ball_xy[1] - c[1])
                height = max(p["xyxy"][3] - p["xyxy"][1], 1.0)
                if best is None or dist < best[0]:
                    best = (dist, t, dist / height)
        if best:
            owner, owner_gap = best[1], best[2]
            if owner_gap <= BALL_OWNER_GAP:
                attacking = owner
                basis = "ball"
                reason = (f"球落在球员脚下（离该球员中心 {best[0]:.0f}px，"
                          f"约其身高的 {owner_gap:.1f} 倍）—— 控球方即进攻方。")
            else:
                reason = (f"球已检出，但离最近的球员还有 {owner_gap:.1f} 倍身高"
                          f"（{best[0]:.0f}px），球权不明，不判攻守。")

    # ② 战术板兜底：画布朝向约定死（y=0 = 对方球门），用「越线人数」判。
    #    只在「根本没摆球」时走这条路 —— 摆了球但球权不明（球在空档里）时，
    #    再拿站位补一个结论，反而会盖掉「球权不明」这个更准的判断。
    order = [t for t in (0, 1) if by_team[t]]
    if basis == "none" and not live and ball is None and len(order) == 2:
        top_team, bottom_team = sorted(order, key=lambda t: np.mean([c[1] for c in by_team[t]]))
        mid = (d_lo + d_hi) / 2.0
        up_push = sum(1 for c in by_team[top_team] if _proj(c, d) > mid)
        dn_push = sum(1 for c in by_team[bottom_team] if _proj(c, d) < mid)
        if dn_push > up_push:
            attacking = bottom_team
            reason = f"未摆球：靠下的一方有 {dn_push} 人越过中线压上，对方只有 {up_push} 人回防。"
        elif up_push > dn_push:
            attacking = top_team
            reason = f"未摆球：靠上的一方有 {up_push} 人越过中线压上，对方只有 {dn_push} 人回防。"
        else:
            reason = "未摆球，双方越线人数相同，暂无一方明显压上。"
        if attacking is not None:
            basis = "position"
    elif basis == "none" and len(order) == 1:
        attacking = order[0]
        basis = "position"
        reason = "只识别出一方球员，默认其为进攻方。"

    defending = None if attacking is None else 1 - attacking
    state = "相持" if attacking is None else "进攻"

    # 推进方向：只有战术板能给出（画布的朝向是约定死的）；
    # 真实画面单帧无法确认「哪一侧球门归谁」，所以不硬给方向。
    direction = None
    if attacking is not None and not live:
        top_team = min(order, key=lambda t: np.mean([c[1] for c in by_team[t]])) if len(order) == 2 else order[0]
        direction = "向下推进" if attacking == top_team else "向上推进"

    # ---------------- 三段人数分布（沿纵深轴，顺序同 depth_labels） ----------------
    dist = {}
    for t in (0, 1):
        z = [0, 0, 0]
        for c in by_team[t]:
            z[_band(_proj(c, d), d_lo, d_hi)] += 1
        dist[str(t)] = z

    # ---------------- 防守方通道空当（沿通道轴） ----------------
    def_channels = [0, 0, 0]
    if defending is not None:
        for c in by_team[defending]:
            def_channels[_band(_proj(c, nrm), c_lo, c_hi)] += 1
    gap = None
    if defending is not None:
        gap = channel_labels[min(range(3), key=lambda i: def_channels[i])]

    # ---------------- 静态发展线索（喂给 LLM 的事实碎片） ----------------
    cues = []
    if attacking is None:
        cues.append("没有判定出进攻方，以下只给站位与球的位置这类客观事实。")
    else:
        cues.append(f"进攻方场上 {len(by_team[attacking])} 人，防守方 {len(by_team[defending])} 人。")
        if gap is not None:
            cues.append(f"防守方「{gap}」通道人数最少（{def_channels[channel_labels.index(gap)]} 人），"
                        "是最可能的突破口。")
    if ball_xy is not None:
        take = ("球在球员脚下，控球方已判定" if basis == "ball"
                else "球离球员较远，球权不明")
        cues.append(f"球在画面「{ball_band}」纵深段 · 「{channel_band}」通道；{take}。")
    else:
        cues.append("球未被检出（太小或被遮挡），以上结论由球员位置推断。")
    if excluded:
        cues.append(f"另有 {excluded} 人未计入（异色球衣的门将或裁判），不参与攻防统计。")

    return {
        "counts": {"players": len(players),
                   "on_pitch": len(players) - excluded,
                   "team0": len(by_team[0]), "team1": len(by_team[1])},
        "unassigned": excluded,
        "axis": {"depth": [round(d[0], 3), round(d[1], 3)],
                 "channel": [round(nrm[0], 3), round(nrm[1], 3)],
                 "labels": {"depth": depth_labels, "channel": channel_labels},
                 "note": axis_note},
        "ball": {"present": ball is not None,
                 "xy": [round(ball_xy[0], 1), round(ball_xy[1], 1)] if ball_xy else None,
                 "depth_band": ball_band, "channel_band": channel_band,
                 "owner": owner, "owner_gap": round(owner_gap, 2) if owner_gap is not None else None},
        "sides": {"attacking": attacking, "defending": defending},
        "state": state,                  # 进攻 / 相持
        "attacking_team": attacking,     # 兼容字段：0 / 1 / None
        "direction": direction,          # 向上推进 / 向下推进 / None
        "basis": basis,                  # 判定依据：ball(控球) / position(站位) / none
        "reason": reason,                # 判定依据（一句话）
        "dist": dist,                    # {"0":[三段人数],"1":[...]}，顺序同 axis.labels.depth
        "gap_channel": gap,              # 防守方最空的通道（方向词）
        "defender_channels": def_channels,   # 顺序同 axis.labels.channel
        "cues": cues,
    }
