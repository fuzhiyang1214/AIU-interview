"""football/data/matcher.py — 按球衣颜色反查球队

职责：拿视觉层测出的两队球衣颜色（HSV），去球队库里找最像的队伍。
输入：HSV 颜色（H:0-180, S:0-1, V:0-1，与 vision 层一致）
输出：候选球队（含得分），形如 [{"name":"利物浦","score":12.3,...}, ...]

匹配依据：以「配色」为主（球衣主色 + 副色取最近），
再叠加少量「同联赛双侧印证」的加分，让结果更稳。纯启发式，供参考。
"""
import colorsys

from . import sources


def hex_to_hsv(hex_color: str) -> tuple:
    """'#RRGGBB' → (H:0-180, S:0-1, V:0-1)。"""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    hh, ss, vv = colorsys.rgb_to_hsv(r, g, b)
    return hh * 180.0, ss, vv


def _dist(a: tuple, b: tuple) -> float:
    """两个 HSV 的颜色距离：色调为主（环形），饱和/亮度为辅。"""
    dh = min(abs(a[0] - b[0]), 180 - abs(a[0] - b[0]))
    ds = abs(a[1] - b[1])
    dv = abs(a[2] - b[2])
    return dh + 30 * ds + 15 * dv


def _team_score(color_hsv: tuple, team: dict) -> float | None:
    """一个颜色与一支球队的距离（取主/副色中最近的那个）。

    没有颜色字段的球队（如在线源带来的队伍）返回 None，表示**不参与颜色打分**。
    """
    colors = team.get("colors_hex") or []
    if not colors:
        return None
    return min(_dist(color_hsv, hex_to_hsv(c)) for c in colors)


def match_team(color_hsv, teams: list, top: int = 3) -> list:
    """给一个颜色找候选球队，按得分升序（越小越像）。

    只对有颜色的球队打分；纯在线队（无颜色）会被跳过，不污染结果。
    """
    if not color_hsv:
        return []
    scored = []
    for t in teams:
        score = _team_score(color_hsv, t)
        if score is None:
            continue
        scored.append({"name": t["name"], "en": t.get("en", t["name"]),
                       "league": t.get("league"), "formation": t.get("formation"),
                       "style": t.get("style"), "score": round(score, 1)})
    scored.sort(key=lambda d: d["score"])
    return scored[:top]


def identify(color_a, color_b, source: str = "offline") -> dict:
    """识别作战双方。

    颜色匹配始终以**本地带颜色的球队库**为准（因为在线源没有颜色字段）。
    当 source="online" 时，额外拉一次在线球队名单，用于：
      - 扩充候选池（在线队按名字去重后并入，颜色缺失不参与打分）；
      - 给识别结果附上「该队是否在真实赛程库中出现」的标记。

    Args:
        color_a / color_b: 两队球衣 HSV 颜色（vision 层输出）。
        source: 数据源名（"offline" ｜ "online"）。

    Returns:
        {"source": "offline"|"online",
         "online": bool,                       # 在线数据是否真的取到了
         "team0": {"candidates":[...], "best": {...}},
         "team1": {...}}
    """
    local = sources.OfflineSource().teams()          # 有颜色，永远是打分的底本
    online_teams, online_ok = [], False
    if source == "online":
        try:
            online_teams = sources.get_online().teams()
            online_ok = bool(online_teams)
        except Exception:
            online_ok = False

    # 打分池 = 本地库 + 在线库里「本地没有的新队」（颜色为空，不会干扰颜色匹配，
    # 但能让候选里出现更多真实存在的球队名）。
    known = {_norm(t.get("en") or t["name"]) for t in local}
    pool = local + [t for t in online_teams if _norm(t.get("en") or t["name"]) not in known]

    online_names = {_norm(t["name"]) for t in online_teams}
    return {
        "source": source,
        "online": online_ok,
        "online_team_count": len(online_teams),
        "team_count": len(pool),
        "team0": _side(color_a, pool, online_names),
        "team1": _side(color_b, pool, online_names),
    }


def _side(color_hsv, teams: list, online_names: set | None = None) -> dict:
    cands = match_team(color_hsv, teams)
    for c in cands:
        # 标记：该候选是否出现在真实赛程库里（可据此去查它的赛程）
        c["in_schedule"] = _norm(c.get("en") or c["name"]) in (online_names or set())
    return {"candidates": cands, "best": cands[0] if cands else None}


def _norm(s: str) -> str:
    """队名归一化，用于「本地库 / 在线库」之间的对齐。"""
    s = (s or "").lower()
    for suffix in (" fc", " afc", " sc", " cf", " ac"):
        s = s.replace(suffix, "")
    return s.replace(" ", "").strip()


def schedule(team_name: str, limit: int = 5) -> list:
    """查一支球队的近期赛程（走在线源）。失败返回空列表，不抛异常。"""
    try:
        return sources.get_online().schedule(team_name, limit=limit)
    except Exception:
        return []
