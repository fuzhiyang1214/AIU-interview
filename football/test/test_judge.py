# -*- coding: utf-8 -*-
"""攻守判定（vision/pitch.py v3）与预处理（vision/locate.py）自测。

为什么单独给「判定」写一份用例：
  v2 的判定把攻守判反过 —— 球明明在浅蓝队 11 号脚下，却报红队在进攻。
  根因有两条，正是本文件要钉死的两条：
    ① 球没检出来，判定只能靠站位猜；
    ② 「谁占哪半场」是拿质心反推的，两队挤在同一侧时整体翻过来。
  所以这里的用例是**回归测试**：结论必须跟「球在谁脚下」走，跟站位无关。

用法（纯 CPU，不需要 torch / 摄像头）：
    D:\\envs\\yolo\\Scripts\\python.exe test_judge.py
"""
import json
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
from vision import locate, pitch          # noqa: E402

W, H = 1050, 680          # 战术板逻辑画布（y = 纵深）
IW, IH = 1400, 660        # 模拟真实画面：x = 纵深（转播机位）


def person(x, y, team, w=44, h=110, role="outfield"):
    """造一个球员（带 role = 图像路径）。"""
    return {"team": team, "role": role, "conf": 0.9,
            "xyxy": [x, y, x + w, y + h]}


def live_frame(team0, team1, ball_xy=None, roles=None):
    """造一份「图像路径」的输入：坐标按 IW×IH 的真实画面口径。"""
    ps = [person(x, y, 0) for x, y in team0] + [person(x, y, 1) for x, y in team1]
    for (x, y), r in (roles or []):
        ps.append(person(x, y, -1, role=r))
    ball = {"xyxy": [ball_xy[0] - 6, ball_xy[1] - 6, ball_xy[0] + 6, ball_xy[1] + 6]} \
        if ball_xy else None
    return pitch.analyze(ps, {}, ball, (IW, IH))


def board_frame(team0, team1, ball=None):
    """造一份「战术板」输入：无 role 字段 = 走画布约定。"""
    ps = [{"team": 0, "xyxy": [x - 13, y - 13, x + 13, y + 13]} for x, y in team0] + \
         [{"team": 1, "xyxy": [x - 13, y - 13, x + 13, y + 13]} for x, y in team1]
    ball_obj = {"xyxy": [ball[0] - 8, ball[1] - 8, ball[0] + 8, ball[1] + 8]} if ball else None
    return pitch.analyze(ps, {}, ball_obj, (W, H))


def main():
    results = []

    def case(name, fn, expect):
        """expect = (state, attacking, basis)"""
        try:
            g = fn()
            got = (g["state"], g["attacking_team"], g["basis"])
            bad = "" if got == expect else f"实得 {got}，期望 {expect}"
            detail = f"{got[0]}·进攻方={got[1]}·依据={got[2]}"
            results.append((name, not bad, detail, bad))
        except Exception as e:                                     # noqa: BLE001
            results.append((name, False, "抛异常", f"{type(e).__name__}: {e}"))

    # ---------- 一、球权优先：结论只跟「球在谁脚下」走 ----------
    # 站位故意造得「反」：T0 人多、全在画面右半边（纵深右三分之一），
    # 球却踩在 T1 一个人脚下 —— 旧口径会按人数/越线判成 T0 进攻。
    case("J1 球在 T1 脚下（站位全部在 T0 侧）",
         lambda: live_frame([(900, 200), (950, 300), (1000, 220), (900, 400), (1050, 380)],
                            [(300, 300)], ball_xy=(322, 355)),
         ("进攻", 1, "ball"))

    case("J2 球在 T0 脚下（站位全部在 T1 侧）",
         lambda: live_frame([(300, 300)], [(900, 200), (950, 300), (1000, 220)],
                            ball_xy=(322, 355)),
         ("进攻", 0, "ball"))

    case("J3 球离所有球员都远（球权不明）",
         lambda: live_frame([(200, 300), (250, 380)], [(900, 200), (950, 300)],
                            ball_xy=(600, 600)),
         ("相持", None, "none"))

    case("J4 球没检出来 → 不硬判（图像路径）",
         lambda: live_frame([(200, 300), (250, 380)], [(900, 200), (950, 300)]),
         ("相持", None, "none"))

    # ---------- 二、坐标轴口径 ----------
    g_axis = live_frame([(200, 300)], [(900, 200)], ball_xy=(222, 355))
    ok_axis = (g_axis["axis"]["labels"]["depth"] == ["左", "中", "右"]
               and g_axis["axis"]["labels"]["channel"] == ["下", "中", "上"])
    results.append(("J5 画面口径纵深=横轴、通道=纵轴", ok_axis,
                    "纵深=" + "/".join(g_axis["axis"]["labels"]["depth"])
                    + " 通道=" + "/".join(g_axis["axis"]["labels"]["channel"]),
                    "" if ok_axis else "方向词与画面不对应"))

    g_board = board_frame([(500, 500)], [(500, 200)])
    ok_board = (g_board["axis"]["labels"]["depth"] == ["上", "中", "下"]
                and g_board["axis"]["labels"]["channel"] == ["左", "中", "右"])
    results.append(("J6 战术板口径纵深=纵轴、通道=横轴", ok_board,
                    "纵深=" + "/".join(g_board["axis"]["labels"]["depth"])
                    + " 通道=" + "/".join(g_board["axis"]["labels"]["channel"]),
                    "" if ok_board else "方向词与画布不对应"))

    # ---------- 三、通道空当：按防守方算，且方向词要能对上画面 ----------
    def gap_case():
        # 防守方 T1 全部挤在画面上段（一条边路），最空的通道应是「下」（画面下半）
        return live_frame([(300, 300), (400, 350), (500, 400), (600, 350), (700, 300)],
                          [(300, 100), (400, 150), (500, 120)],
                          ball_xy=(322, 355))

    g = gap_case()
    ok_gap = (g["gap_channel"] == "下" and g["defender_channels"][0] == 0
              and g["sides"]["defending"] == 1)
    results.append(("J7 空当按防守方统计（方向词对画面）", ok_gap,
                    f"防守方=T{g['sides']['defending']} 通道={g['defender_channels']} "
                    f"空当={g['gap_channel']}",
                    "" if ok_gap else "空当口径不对"))

    # ---------- 四、战术板：不摆球仍走「越线人数」（画布朝向是约定死的） ----------
    case("J8 战术板不摆球 → 越线人数兜底",
         lambda: board_frame([(500, 560), (300, 600), (700, 590)],
                             [(500, 120), (300, 160), (500, 420), (700, 450)]),
         ("进攻", 1, "position"))

    case("J9 战术板摆球在对手前锋脚下 → 控球判定",
         lambda: board_frame([(500, 560), (300, 600)], [(500, 120), (300, 160)],
                             ball=(500, 140)),
         ("进攻", 1, "ball"))

    # ---------- 五、预处理：球场定位 / 推理尺寸 / 清看台 / 挑球 ----------
    def roi_case():
        img = np.zeros((600, 900, 3), np.uint8)
        img[:] = (90, 90, 90)                                     # 灰色界面
        img[120:480, 100:800] = (60, 170, 120)                    # 一块草地
        box = locate.pitch_roi(img)
        inner = (box[0] <= 100 and box[1] <= 120 and box[2] >= 800 and box[3] >= 480)
        cropped = box != (0, 0, 900, 600)
        return inner and cropped, box

    ok_roi, box_roi = roi_case()
    results.append(("K1 pitch_roi 框住草地（带外扩）", ok_roi, f"box={box_roi}",
                    "" if ok_roi else "没框住或没裁剪"))

    def roi_none():
        img = np.zeros((600, 900, 3), np.uint8)
        img[:] = (120, 120, 120)
        return locate.pitch_roi(img) == (0, 0, 900, 600)

    results.append(("K2 没有草地 → 整幅画面（不裁错）", roi_none(), "返回整幅", ""))

    def imgsz_case():
        vals = [locate.auto_imgsz((1400, 660)), locate.auto_imgsz((640, 480)),
                locate.auto_imgsz((6000, 1000))]
        ok = (vals[0] == 3200 and vals[1] == 1536 and vals[2] == 3200
              and all(v % 32 == 0 for v in vals))
        return ok, vals

    ok_sz, vals = imgsz_case()
    results.append(("K3 auto_imgsz（2.4 倍、32 整数倍、封顶 3200）", ok_sz,
                    f"1400→{vals[0]} 640→{vals[1]} 6000→{vals[2]}", "" if ok_sz else "换算不对"))

    def crowd_case():
        img = np.zeros((400, 800, 3), np.uint8)
        img[:] = (60, 170, 120)                                   # 全场草地
        img[0:80, :] = (90, 90, 90)                               # 顶部一片看台灰
        img[:, 396:404] = (240, 240, 240)                         # 一条白色场地线
        on_pitch = {"label": "person", "conf": .9, "xyxy": [300, 200, 344, 310]}
        on_line = {"label": "person", "conf": .9, "xyxy": [380, 200, 424, 310]}
        in_stand = {"label": "person", "conf": .9, "xyxy": [500, 2, 544, 60]}
        kept = locate.filter_crowd(img, [on_pitch, on_line, in_stand])
        return kept == [on_pitch, on_line], len(kept)

    ok_crowd, n_kept = crowd_case()
    results.append(("K4 filter_crowd 剔看台、留球员（含踩线的）", ok_crowd,
                    f"保留 {n_kept} / 3 人",
                    "" if ok_crowd else "误伤球员或没剔看台"))

    def ball_case():
        people = [{"xyxy": [300, 200, 344, 310]}]
        # 手套式误检：置信度更高，但不在球员框里；真球在脚下
        glove = {"label": "sports ball", "conf": .48, "xyxy": [600, 100, 608, 108]}
        real = {"label": "sports ball", "conf": .45, "xyxy": [316, 288, 324, 296]}
        return locate.pick_ball([glove, real], people) is real

    results.append(("K5 pick_ball 优先「在球员身上」的候选", ball_case(),
                    "选中脚下那颗（conf 更低）", ""))

    def json_case():
        """防回归：pitch_roi 必须返回 Python int，不能是 numpy 整数。

        cv2.connectedComponentsWithStats 的 stats 是 np.int32，它进不了 Flask 的
        jsonify（报 "Object of type int32 is not JSON serializable"）。坑在于
        只有「真裁到球场」这条路才踩得到 —— 用普通照片测（走 full 分支）测不出来。
        """
        img = np.zeros((600, 900, 3), np.uint8)
        img[:] = (90, 90, 90)
        img[120:480, 100:800] = (60, 170, 120)
        box = locate.pitch_roi(img)
        types = [type(v).__name__ for v in box]
        try:
            json.dumps({"crop": {"box": list(box)}})              # 模拟 Flask jsonify
            return True, "类型=" + ",".join(types)
        except TypeError as e:                                    # noqa: BLE001
            return False, f"类型={','.join(types)}  {e}"

    ok_json, detail_json = json_case()
    results.append(("K6 pitch_roi 返回值可 JSON 序列化", ok_json, detail_json,
                    "" if ok_json else "numpy 整数泄漏到了 jsonify"))

    # ---------------------------------------------------------------- 汇总
    print(f"{'用例':<40} {'结果':<6} 明细")
    print("-" * 104)
    npass = 0
    for name, ok, detail, err in results:
        npass += ok
        print(f"{name:<40} {'通过' if ok else '失败':<6} {detail}" + (f"   <- {err}" if err else ""))
    print("-" * 104)
    print(f"结果：{npass} / {len(results)} 通过")
    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
