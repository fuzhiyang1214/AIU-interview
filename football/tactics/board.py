"""football/tactics/board.py — 手动战术板的分析层

职责：把「在战术板上摆出来的站位」翻译成与图像分析**同构**的结果，
      然后交给 vision/pitch.py 做攻防判定。

★ 核心取舍：不重写判定逻辑。
   vision/pitch.py 只认「球员坐标 + 球坐标」，它不关心这些坐标是 YOLO 给的
   还是鼠标拖出来的。所以战术板只需要**构造出等效的坐标矩形**，
   后续的攻防判定、三区人数、空当通道全部原样复用 —— 两条输入路径共用同一个判定内核。

坐标系（pitch.py 按「有无 role 字段」区分两条路径，战术板不带 role）：
   逻辑画布 1050 × 680（10px ≈ 1 米，接近真实球场 105×68 的比例）
   x：0 = 左路，1 = 右路
   y：0 = 对方球门（进攻方向），1 = 我方球门
   ⇒ pitch.py 对战术板取「纵深 = 画布纵轴」（DEFAULT_DEPTH），朝向是约定死的，
     不靠推断。只有**没摆球**时才走「越线人数」这条兜底；摆了球就走控球判定，
     球权不明时直接报相持，不拿站位补结论。

为什么值得做：COCO 权重认不出高位/俯视画面里的球员（那是战术分析最需要的图），
自动检测在这类图上必然失效。手动摆位绕开检测，让整条分析链在**任何**输入下都能跑。
"""
from vision.pitch import analyze as _pitch_analyze

# 逻辑画布尺寸（战术板与服务端约定一致）
PITCH_W, PITCH_H = 1050, 680

# 球员标记的等效边长：pitch 只认矩形，给点位一个居中的小方框
TOKEN = 26


def _box(x: float, y: float, size: int = TOKEN) -> list:
    """点位 → 居中小矩形 [x1, y1, x2, y2]。"""
    h = size / 2.0
    return [x - h, y - h, x + h, y + h]


def _norm(v, default=0.5) -> float:
    """归一化坐标夹到 0~1（前端可能传回越界值）。"""
    try:
        return min(1.0, max(0.0, float(v)))
    except (TypeError, ValueError):
        return default


def _adapt_wording(geo: dict) -> None:
    """把判定结论里的「检测口径」措辞换成「摆放口径」（就地修改）。

    pitch.py 是两条输入路径共用的内核，文案原是按图像检测写的。
    战术板不重写判定，只在这里翻译说法 —— 结论不变，用词贴合场景：
    「画面里识别出」→「战术板上摆出」，「球未检出」→「未摆放球」，
    队号 T0 / T1 → 战术板自己的叫法「我方 / 对手」。
    """
    geo["reason"] = (geo.get("reason") or "").replace("识别出", "摆出").replace("画面里", "战术板上")
    geo["reason"] = geo["reason"].replace("T0", "我方").replace("T1", "对手")
    geo["cues"] = [
        "未摆放球，以上结论由球员站位推断。" if c.startswith("球未被检出") else c
        for c in geo.get("cues", [])
    ]



def analyze_board(slots: list, ball=None, size=None) -> dict:
    """分析战术板上的站位。

    Args:
        slots: [{"team":0|1, "x":0~1, "y":0~1, "pos":"ST", "no":9}, ...]
        ball:  {"x":0~1, "y":0~1} 或 None
        size:  (W, H)，默认逻辑画布。

    Returns:
        与 vision.analyze_image() 同构的分析字典（额外带 "source":"board"），
        因此 brain.brief() / 前端渲染 / 建议与问答接口都能直接复用。
    """
    W, H = size or (PITCH_W, PITCH_H)

    players = []
    for s in (slots or []):
        try:
            team = 1 if int(s.get("team") or 0) == 1 else 0
        except (TypeError, ValueError):
            team = 0
        x, y = _norm(s.get("x")) * W, _norm(s.get("y")) * H
        p = {"team": team, "xyxy": _box(x, y),
             "x": round(x, 1), "y": round(y, 1)}
        if s.get("pos"):
            p["pos"] = str(s["pos"]).upper()
        if s.get("no") is not None:
            p["no"] = s["no"]
        players.append(p)

    ball_obj = None
    if ball:
        ball_obj = {"xyxy": _box(_norm(ball.get("x")) * W, _norm(ball.get("y")) * H, 16)}

    # —— 交给既有的判定逻辑（这一行就是全部「复用」）——
    geo = _pitch_analyze(players, {}, ball_obj, (W, H))
    _adapt_wording(geo)
    if not players:
        geo["reason"] = "战术板上还没有球员，先摆好人再分析。"

    by_team = {0: 0, 1: 0}
    for p in players:
        by_team[p["team"]] += 1

    return {
        "source": "board",
        "image_size": [W, H],
        "objects_total": len(players) + (1 if ball_obj else 0),
        "players": players,
        "teams": {str(t): {"count": n, "color_hsv": None} for t, n in by_team.items()},
        "ball": {"present": ball_obj is not None},
        **geo,                      # 含 counts / sides / state / dist / gap_channel / cues
    }


def summarize(analysis: dict, labels: dict = None) -> str:
    """把分析结果压成一句人话（前端顶部横幅用，不走 LLM）。

    与 brain 的简报口径一致：攻防判定以 pitch 的结论为准，不做二次发挥。
    """
    labels = labels or {}
    name = lambda t: labels.get(t) or f"T{t}"      # noqa: E731

    state = analysis.get("state")
    if state != "进攻" or analysis.get("attacking_team") is None:
        return f"相持 —— {analysis.get('reason', '')}"

    atk = analysis["attacking_team"]
    dfd = analysis.get("sides", {}).get("defending")
    text = f"{name(atk)} 进攻 · {name(dfd)} 防守（{analysis.get('direction') or '—'}）"
    if analysis.get("gap_channel"):
        text += f" ｜ 空当：{analysis['gap_channel']}路"
    return text
