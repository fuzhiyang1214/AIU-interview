"""football/vision/pitch.py — 由球员位置推断攻防态势与「球可能的发展」

职责：把「谁在哪、球在哪」翻译成「谁在进攻、谁在防守、球接下来可能往哪走」。

思路（全部是启发式，不追求精确，追求可解释）：
  - 画面纵向（y）近似球场纵深：约定「上方 = 远端球门，下方 = 近端球门」。
  - 谁在进攻（两种途径，优先用更硬的证据）：
      ① 球若检出 → 球进了哪一侧半场，就是哪一侧在挨打，另一方在压上；
      ② 球若未检出 → 用「越线人数」：以两队质心的中点为中线，
         谁有更多人越过中线进入对方半场，谁就在压上。
  - 空当：把画面横向分「左 / 中 / 右」三通道，看**防守方**哪条通道人最少。
  - 不硬套「4-3-3」这类阵型名；只给「上 / 中 / 下三区人数」这种可解释的分布。

为什么砍掉阵型与球队：出题 PDF 第 2 页要求「做减法」——
静态单帧本就不足以断定精确阵型，与其编一个像模像样的 4-3-3，
不如老实给出「谁在压、哪条线人少、球可能往哪走」。
"""
import numpy as np


def _centroid(box):
    x1, y1, x2, y2 = box
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def _zone(y, height) -> str:
    """把 y 归一化成三区：上 / 中 / 下。"""
    r = y / max(height, 1)
    if r < 1 / 3:
        return "上"
    if r > 2 / 3:
        return "下"
    return "中"


def _channel(x, width) -> str:
    """把 x 归一化成三通道：左 / 中 / 右。"""
    r = x / max(width, 1)
    if r < 1 / 3:
        return "左"
    if r > 2 / 3:
        return "右"
    return "中"


def analyze(players: list, teams: dict, ball: dict | None, size) -> dict:
    """综合球员与球的位置，得出攻防态势与静态发展线索。

    Args:
        players: 球员列表，每项含 xyxy 与 team。
        teams: team_split.split() 的结果（本层只用分组，不用颜色）。
        ball: 球的框 dict（{"xyxy":[...]}）或 None。
        size: (width, height)。

    Returns:
        结构化态势字典（字段见文件顶部说明与 README）。
    """
    W, H = size

    by_team = {0: [], 1: []}
    for p in players:
        by_team[p["team"]].append(_centroid(p["xyxy"]))

    cent = {}
    for t, pts in by_team.items():
        if pts:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            cent[t] = {"cx": float(np.mean(xs)), "cy": float(np.mean(ys))}
        else:
            cent[t] = None

    # ---------------- 球 ----------------
    ball_xy = _centroid(ball["xyxy"]) if ball else None
    ball_zone = _zone(ball_xy[1], H) if ball_xy else None
    ball_channel = _channel(ball_xy[0], W) if ball_xy else None

    # ---------------- 攻防判定 ----------------
    order = [t for t in (0, 1) if cent[t] is not None]
    top_team = bottom_team = None
    mid_y = H / 2.0     # 用「画面中线 ≈ 球场中线」作越线基准（比两队质心中点稳）
    if len(order) == 2:
        top_team, bottom_team = sorted(order, key=lambda t: cent[t]["cy"])

    attacking = None
    reason = "画面里只识别出一方球员，无法比较攻防。"
    if len(order) == 2:
        if ball_zone == "上":
            attacking = bottom_team
            reason = "球已进入上方（远端）半场，是下方一方把它打过去的。"
        elif ball_zone == "下":
            attacking = top_team
            reason = "球已进入下方（近端）半场，是上方一方把它打过去的。"
        else:
            up_push = sum(1 for _, y in by_team[top_team] if y > mid_y)      # 上方队越线人数
            dn_push = sum(1 for _, y in by_team[bottom_team] if y < mid_y)   # 下方队越线人数
            if dn_push > up_push:
                attacking = bottom_team
                reason = f"下方一方有 {dn_push} 人越过中线压上，对方只有 {up_push} 人回防。"
            elif up_push > dn_push:
                attacking = top_team
                reason = f"上方一方有 {up_push} 人越过中线压上，对方只有 {dn_push} 人回防。"
            else:
                reason = "双方越线人数相同，暂无一方明显压上。"
    elif len(order) == 1:
        attacking = order[0]
        reason = "只识别出一方球员，默认其为进攻方。"

    defending = None if attacking is None else 1 - attacking

    state = "相持" if attacking is None else "进攻"
    if attacking is None:
        direction = None
    elif attacking == bottom_team:
        direction = "向上推进"
    elif attacking == top_team:
        direction = "向下推进"
    else:
        direction = None

    # ---------------- 三区人数分布（客观事实，不做阵型命名） ----------------
    dist = {}
    for t in (0, 1):
        z = {"上": 0, "中": 0, "下": 0}
        for _, y in by_team[t]:
            z[_zone(y, H)] += 1
        dist[str(t)] = z

    # ---------------- 防守方通道空当 ----------------
    def_channels = {"左": 0, "中": 0, "右": 0}
    if defending is not None:
        for x, _ in by_team[defending]:
            def_channels[_channel(x, W)] += 1
    gap = min(def_channels, key=def_channels.get) if defending is not None else None

    # ---------------- 静态发展线索（喂给 LLM 的事实碎片） ----------------
    cues = []
    if attacking is None:
        cues.append("没有明显压上的一方，球权归属不明。")
    else:
        cues.append(f"进攻方投入 {len(by_team[attacking])} 人，防守方回防 {len(by_team[defending])} 人。")
        if gap is not None:
            cues.append(f"防守方「{gap}」通道人数最少（{def_channels[gap]} 人），是最可能的突破口。")
    if ball_xy is not None:
        cues.append(f"球当前在「{ball_zone}区 · {ball_channel}通道」。")
    else:
        cues.append("球未被检出（太小或被遮挡），以下按球员站位推断。")

    return {
        "counts": {"players": len(players),
                   "team0": len(by_team[0]), "team1": len(by_team[1])},
        "ball": {"present": ball is not None,
                 "xy": [round(ball_xy[0], 1), round(ball_xy[1], 1)] if ball_xy else None,
                 "zone": ball_zone, "channel": ball_channel},
        "sides": {"attacking": attacking, "defending": defending},
        "state": state,                  # 进攻 / 相持
        "attacking_team": attacking,     # 兼容字段：0 / 1 / None
        "direction": direction,          # 向上推进 / 向下推进 / None
        "reason": reason,                # 判定依据（一句话）
        "dist": dist,                    # {0:{上,中,下}, 1:{...}}
        "gap_channel": gap,              # 防守方最空的通道
        "defender_channels": def_channels,
        "cues": cues,
    }
