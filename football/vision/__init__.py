"""football/vision/__init__.py — 视觉分析层的对外入口

职责：把「检测 → 分队 → 判读」三步串起来，返回结构化结果 + 带标注的图。
输入：一帧 BGR 图像
输出：(analysis_dict, annotated_bgr)

这一步是纯计算，不碰网络、不碰 LLM —— 战术建议由 brain/ 层消费本结果。
"""
import base64

import cv2
import numpy as np

from . import detector, team_split, pitch

# 两队标注颜色（BGR）：0 队红、1 队蓝，球用黄色
TEAM_COLORS = {0: (60, 60, 220), 1: (220, 130, 40), -1: (0, 220, 255)}


def analyze_image(frame, conf: float = 0.35, imgsz: int = 1280,
                  device: str = "cuda:0") -> tuple:
    """分析一帧画面。

    Returns:
        (analysis, annotated) —— analysis 为结构化字典，annotated 为画好框的 BGR 图。
    """
    H, W = frame.shape[:2]
    objs = detector.detect(frame, conf=conf, imgsz=imgsz, device=device)

    raw_players = [o for o in objs if o["label"] == "person"]
    ball_obj = next((o for o in objs if o["label"] == "sports ball"), None)

    # 按球衣颜色分两队
    groups = team_split.split(frame, raw_players)

    # 把队号写回每个球员
    players = []
    for team, info in groups.items():
        for i in info["members"]:
            pl = dict(raw_players[i])
            pl["team"] = team
            players.append(pl)

    geo = pitch.analyze(players, groups, ball_obj, (W, H))

    analysis = {
        "image_size": [W, H],
        "objects_total": len(objs),
        "players": [{"team": p["team"], "conf": p["conf"], "xyxy": p["xyxy"]} for p in players],
        "teams": {
            str(t): {"count": len(info["members"]), "color_hsv": info["color_hsv"]}
            for t, info in groups.items()
        },
        "ball": {"present": ball_obj is not None,
                 "conf": ball_obj["conf"] if ball_obj else None,
                 "xyxy": ball_obj["xyxy"] if ball_obj else None},
        **geo,
    }

    annotated = _draw(frame.copy(), players, ball_obj, geo)
    return analysis, annotated


def _draw(frame, players, ball_obj, geo):
    """把检测结果画到图上：球员框按队上色，球画黄框，顶部写态势。"""
    for p in players:
        x1, y1, x2, y2 = [int(v) for v in p["xyxy"]]
        color = TEAM_COLORS.get(p["team"], TEAM_COLORS[-1])
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, f"T{p['team']}", (x1, max(y1 - 4, 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

    if ball_obj:
        x1, y1, x2, y2 = [int(v) for v in ball_obj["xyxy"]]
        cv2.rectangle(frame, (x1, y1), (x2, y2), TEAM_COLORS[-1], 2)

    banner = f"{geo['state']}"
    if geo["attacking_team"] is not None:
        banner += f"  |  进攻方 T{geo['attacking_team']}"
        if geo.get("direction"):
            banner += f"（{geo['direction']}）"
    if geo.get("gap_channel"):
        banner += f"  |  空当：{geo['gap_channel']}路"
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
