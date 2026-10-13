"""football/vision/__init__.py — 视觉分析层的对外入口

职责：把「裁到球场 → 检测 → 分队 → 判读」四步串起来，返回结构化结果 + 带标注的图。
输入：一帧 BGR 图像（来源见 frames.py：上传的 data URL / 本机摄像头）
输出：(analysis_dict, annotated_bgr)

这一步是纯计算，不碰网络、不碰 LLM —— 战术建议由 brain/ 层消费本结果。
"""
import base64

import cv2

from . import detector, locate, pitch, team_split
from .frames import decode_data_url, grab_camera

# 标注颜色（BGR）：0 队红 / 1 队蓝 / 球黄 / 未计入（门将·裁判）灰
TEAM_COLORS = {0: (60, 60, 220), 1: (220, 130, 40)}
BALL_COLOR = (0, 220, 255)
EXCLUDED_COLOR = (150, 150, 150)


def analyze_image(frame, conf: float = 0.35, imgsz: int = 0,
                  device: str = "cuda:0") -> tuple:
    """分析一帧画面。

    Args:
        imgsz: 推理尺寸。0（默认）= 自动 —— 先裁出球场区域，再按长边 2.4 倍换算
               （夹在 1280~3200）。自动放大是必要的：整屏截图（3072×1920）里球
               只有 ~12px，imgsz=1280/1920/2560 全都检不出来；裁到球场再推到 3200
               才能以 0.50 的置信度检出球。球检不出来，攻守就只能靠站位猜，
               结论会反过来（这就是之前「攻守判反」的根因）。

    Returns:
        (analysis, annotated) —— analysis 为结构化字典，annotated 为画好框的 BGR 图。
        坐标口径 = 裁出来的球场区域（analysis["crop"] 里记录了原图里的位置）。
    """
    x1, y1, x2, y2 = locate.pitch_roi(frame)
    roi = frame[y1:y2, x1:x2]
    if roi.size == 0:                     # 极端输入兜底
        roi, x1, y1, x2, y2 = frame, 0, 0, frame.shape[1], frame.shape[0]
    H, W = roi.shape[:2]
    size = int(imgsz) if imgsz else locate.auto_imgsz((W, H))

    objs = detector.detect(roi, conf=conf, imgsz=size, device=device)

    # 先剔掉看台上的观众（否则人数虚高，还会把「门将地标」带偏）
    raw_players = locate.filter_crowd(roi, [o for o in objs if o["label"] == "person"])
    # 找球：主路径 = 在球员脚边开小窗；小窗没找到才退回整图候选
    ball_obj = locate.find_ball(roi, raw_players, device=device)
    if ball_obj is None:
        ball_obj = locate.pick_ball([o for o in objs if o["label"] == "sports ball"],
                                    raw_players)

    # 按球衣颜色分两队；分不出队的（异色门将 / 裁判）由 roles 单独标出
    groups, roles = team_split.split(roi, raw_players)

    # 把队号写回每个球员
    players = []
    for team, info in groups.items():
        for i in info["members"]:
            pl = dict(raw_players[i])
            pl["team"] = team
            pl["role"] = "outfield"
            players.append(pl)
    # 未归队的仍然画在图上（team = -1），但不参与攻防统计
    for i, r in enumerate(roles):
        if r != "outfield":
            pl = dict(raw_players[i])
            pl["team"] = -1
            pl["role"] = r
            players.append(pl)

    geo = pitch.analyze(players, groups, ball_obj, (W, H))

    # ⚠️ **geo 必须排在前面。
    # geo 里也有一个 "unassigned"，但那是**裸 int**（pitch.py 给的人数）；
    # 若把它放在最后展开，会连同名把下面这个结构化版本整个盖掉 ——
    # 前端读 a.unassigned.count 得到 undefined ⇒「未计入（门将 / 裁判）」那一行
    # **永远不会出现在界面上**（踩过一次：截图里 9 = 5 + 3 + 1 却没有这一行）。
    analysis = {
        "source": "image",
        **geo,                                     # 判定层字段先铺开（counts / sides / state / dist / …）
        "image_size": [W, H],                      # 坐标口径 = 裁出来的球场区域
        "crop": {"box": [int(v) for v in (x1, y1, x2, y2)],   # 必须过 int()：numpy 整数没法 jsonify
                 "source_size": [int(frame.shape[1]), int(frame.shape[0])],
                 "cropped": (x1, y1, x2, y2) != (0, 0, frame.shape[1], frame.shape[0]),
                 "imgsz": size},
        "objects_total": len(objs),
        "players": [{"team": p["team"], "role": p["role"], "conf": p["conf"],
                     "xyxy": p["xyxy"]} for p in players],
        "teams": {
            str(t): {"count": len(info["members"]), "color_hsv": info["color_hsv"]}
            for t, info in groups.items()
        },
        "unassigned": {                            # 覆盖 geo 里的裸 int：前端要的是 .count
            "count": geo.get("unassigned", 0),
            "gk": sum(1 for i, r in enumerate(roles) if r == "gk"),
            "unknown": sum(1 for i, r in enumerate(roles) if r == "unknown"),
        },
    }
    # geo 里也有 ball（球权与落位），这里补上检测侧的置信度与框
    analysis["ball"] = {**geo["ball"], "conf": ball_obj["conf"] if ball_obj else None,
                        "xyxy": ball_obj["xyxy"] if ball_obj else None}

    annotated = _draw(roi, players, ball_obj, geo)
    return analysis, annotated


def _draw(frame, players, ball_obj, geo):
    """把检测结果画到图上：球员框按队上色，球画黄框，顶部写态势。

    未计入攻防统计的（异色门将 / 裁判）画灰框，标签写 GK 或 —。
    """
    for p in players:
        x1, y1, x2, y2 = [int(v) for v in p["xyxy"]]
        team = p.get("team")
        if team in TEAM_COLORS:
            color, tag = TEAM_COLORS[team], f"T{team}"
        else:
            color = EXCLUDED_COLOR
            tag = "GK" if p.get("role") == "gk" else "—"
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, tag, (x1, max(y1 - 4, 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

    if ball_obj:
        x1, y1, x2, y2 = [int(v) for v in ball_obj["xyxy"]]
        cv2.rectangle(frame, (x1, y1), (x2, y2), BALL_COLOR, 2)
        cv2.circle(frame, (int((x1 + x2) / 2), int((y1 + y2) / 2)),
                   max(int(max(x2 - x1, y2 - y1)), 8), BALL_COLOR, 1, cv2.LINE_AA)

    banner = f"{geo['state']}"
    if geo["attacking_team"] is not None:
        banner += f"  |  进攻方 T{geo['attacking_team']}"
        if geo.get("direction"):
            banner += f"（{geo['direction']}）"
    if geo.get("ball", {}).get("owner") is not None and geo.get("basis") == "ball":
        banner += f"  |  控球：T{geo['ball']['owner']}"
    if geo.get("gap_channel"):
        banner += f"  |  空当：{geo['gap_channel']}"
    if geo.get("unassigned"):
        banner += f"  |  未计入 {geo['unassigned']} 人（门将/裁判）"
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 26), (30, 30, 30), -1)
    cv2.putText(frame, banner, (8, 18), cv2.FONT_HERSHEY_SIMPLEX,
                0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return frame


def to_base64_jpeg(frame) -> str:
    """把 BGR 图编码成 data URL，供前端 <img> 直接显示。"""
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
    if not ok:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()
