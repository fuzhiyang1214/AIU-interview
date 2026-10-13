# -*- coding: utf-8 -*-
"""team_split 自测：合成带草地的画面 + 边界用例。

验证「球衣分队」的四个环节：胸区取样 / 剔除草地色 / 色相主峰 / 黑白走亮度通道，
以及判不出队的人（异色门将、黑衣裁判）是否被正确踢出攻防统计。

用法（需要 cv2，用 yolo 的 venv）：
    D:\\envs\\yolo\\Scripts\\python.exe test_team_split.py
"""
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def _find_root():
    """从脚本所在位置向上找带 football/ 的目录。"""
    p = HERE
    for _ in range(6):
        if os.path.isdir(os.path.join(p, "football")):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    return os.environ.get("FOOTBALL_ROOT", r"C:\Users\FU\Desktop\ai-interview")


REPO = _find_root()
sys.path.insert(0, os.path.join(REPO, "football"))
from vision import team_split, pitch  # noqa: E402

W, H = 1050, 680
BW, BH = 44, 110
GRASS = (39, 170, 135)          # 直播帧实测的草地色
RED = (0, 210, 200)
BLUE = (115, 210, 200)
GREEN = (60, 210, 180)          # 门将（深绿）
LBLUE = (115, 90, 230)          # 门将（浅蓝，与本队同色相）
BLACK = (0, 0, 45)              # 裁判（黑）
WHITE = (0, 10, 235)            # 白色球衣


def build(spec):
    img = np.full((H, W, 3), 0, np.uint8)
    img[:] = cv2.cvtColor(np.uint8([[list(GRASS)]]), cv2.COLOR_HSV2BGR)[0][0]
    players, tags = [], []
    for (x, y, hsv, tag) in spec:
        bgr = cv2.cvtColor(np.uint8([[list(hsv)]]), cv2.COLOR_HSV2BGR)[0][0]
        img[y:y + BH, x:x + BW] = bgr
        players.append({"xyxy": [x, y, x + BW, y + BH]})
        tags.append(tag)
    return img, players, tags


def run(spec):
    img, players, tags = build(spec)
    groups, roles = team_split.split(img, players)
    team = {}
    for t, info in groups.items():
        for i in info["members"]:
            team[i] = t
    return players, tags, groups, roles, team


def line(spec, expect_counts=None, expect_excluded=(), expect_team=None):
    players, tags, groups, roles, team = run(spec)
    c0, c1 = len(groups[0]["members"]), len(groups[1]["members"])
    excluded = sorted(tags[i] for i, r in enumerate(roles) if r != "outfield")
    bad = []
    if expect_counts and (c0, c1) != expect_counts:
        bad.append(f"人数 {c0}/{c1} != {expect_counts[0]}/{expect_counts[1]}")
    if sorted(expect_excluded) != excluded:
        bad.append(f"未计入 {excluded} != {sorted(expect_excluded)}")
    if expect_team:
        for tag, want in expect_team.items():
            got = next((t for i, t in team.items() if tags[i] == tag), None)
            if got != want:
                bad.append(f"{tag} 归队 {got} != {want}")
    return (c0, c1), excluded, bad


def main():
    results = []

    def case(name, fn):
        try:
            cc, ex, bad = fn()
            results.append((name, not bad, f"T0/T1={cc[0]}/{cc[1]} 未计入={ex or '无'}",
                            "；".join(bad)))
        except Exception as e:                                    # noqa: BLE001
            results.append((name, False, "抛异常", f"{type(e).__name__}: {e}"))

    # S1 基线：草地上一场干净的 5v5
    case("S1 基线 5v5（红 vs 蓝）", lambda: line([
        (60, 100, RED, "A1"), (200, 160, RED, "A2"), (340, 220, RED, "A3"),
        (480, 280, RED, "A4"), (620, 340, RED, "A5"),
        (60, 400, BLUE, "B1"), (200, 460, BLUE, "B2"), (340, 520, BLUE, "B3"),
        (480, 560, BLUE, "B4"), (620, 560, BLUE, "B5"),
    ], expect_counts=(5, 5), expect_excluded=[],
        expect_team={"A3": 0, "B3": 1}))

    # S2 两个门将同色（绿）—— 旧实现会读成 7v5
    case("S2 5v5 + 两个绿门将", lambda: line([
        (60, 100, RED, "A1"), (200, 160, RED, "A2"), (340, 220, RED, "A3"),
        (480, 280, RED, "A4"), (620, 340, RED, "A5"),
        (60, 400, BLUE, "B1"), (200, 460, BLUE, "B2"), (340, 520, BLUE, "B3"),
        (480, 560, BLUE, "B4"), (620, 560, BLUE, "B5"),
        (860, 20, GREEN, "GK-A"), (860, 540, GREEN, "GK-B"),
    ], expect_counts=(5, 5), expect_excluded=["GK-A", "GK-B"]))

    # S3 混入黑衣裁判 —— 旧实现会把他算进红队
    case("S3 5v5 + 黑衣裁判", lambda: line([
        (60, 100, RED, "A1"), (200, 160, RED, "A2"), (340, 220, RED, "A3"),
        (480, 280, RED, "A4"), (620, 340, RED, "A5"),
        (60, 400, BLUE, "B1"), (200, 460, BLUE, "B2"), (340, 520, BLUE, "B3"),
        (480, 560, BLUE, "B4"), (620, 560, BLUE, "B5"),
        (860, 300, BLACK, "裁判"),
    ], expect_counts=(5, 5), expect_excluded=["裁判"], expect_team={"A5": 0, "B5": 1}))

    # S4 只识别出 3 人 + 一名异色门将（局部特写）
    case("S4 局部特写 2v1 + 绿门将", lambda: line([
        (60, 120, RED, "A1"), (860, 460, RED, "A2"),
        (620, 200, BLUE, "B1"),
        (480, 20, GREEN, "GK"),
    ], expect_counts=(2, 1), expect_excluded=["GK"], expect_team={"A1": 0, "B1": 1}))

    # S5 一队白色球衣（无彩色）→ 走亮度通道
    case("S5 红 vs 白（一队无彩）", lambda: line([
        (60, 100, RED, "R1"), (200, 160, RED, "R2"), (340, 220, RED, "R3"),
        (480, 280, RED, "R4"), (620, 340, RED, "R5"),
        (60, 400, WHITE, "W1"), (200, 460, WHITE, "W2"), (340, 520, WHITE, "W3"),
        (480, 560, WHITE, "W4"), (620, 560, WHITE, "W5"),
    ], expect_counts=(5, 5), expect_excluded=[]))

    # S6 两队球衣同色 → 不该硬分
    case("S6 红 vs 红（分不开）", lambda: line([
        (60, 100, RED, "A1"), (200, 160, RED, "A2"), (340, 220, RED, "A3"),
        (60, 400, RED, "B1"), (200, 460, RED, "B2"), (340, 520, RED, "B3"),
    ], expect_counts=(6, 0)))

    # ---- 边界 ----
    def zero():
        groups, roles = team_split.split(build([])[0], [])
        return ((len(groups.get(0, {}).get("members", [])),
                 len(groups.get(1, {}).get("members", []))), [], [])
    case("E1 零球员", zero)

    def one():
        img, players, tags = build([(60, 100, RED, "A1")])
        groups, roles = team_split.split(img, players)
        return ((len(groups[0]["members"]), len(groups[1]["members"])), [], [])
    case("E2 单球员", one)

    def tiny():
        img = build([])[0]
        players = [{"xyxy": [10, 10, 12, 14]}, {"xyxy": [100, 100, 102, 104]}]
        groups, roles = team_split.split(img, players)
        return ((len(groups[0]["members"]), len(groups[1]["members"])), [], [])
    case("E3 超小框（<10px）", tiny)

    def nopitch():
        """确认 team=-1 的球员不会让 pitch 崩，且不计入人数。"""
        ps = [{"team": 0, "xyxy": [0, 0, 40, 100]},
              {"team": 1, "xyxy": [0, 500, 40, 600]},
              {"team": -1, "xyxy": [500, 20, 540, 130]}]
        geo = pitch.analyze(ps, {0: {}, 1: {}}, None, (W, H))
        assert geo["counts"]["team0"] == 1 and geo["counts"]["team1"] == 1
        assert geo["unassigned"] == 1, geo["unassigned"]
        return (geo["counts"]["team0"], geo["counts"]["team1"]), ["1 人未计入"], []
    case("E4 pitch 跳过 team=-1", nopitch)

    print(f"{'用例':<28} {'结果':<6} 明细")
    print("-" * 92)
    npass = 0
    for name, ok, detail, err in results:
        npass += ok
        print(f"{name:<28} {'通过' if ok else '失败':<6} {detail}" + (f"   <- {err}" if err else ""))
    print("-" * 92)
    print(f"结果：{npass} / {len(results)} 通过")
    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
