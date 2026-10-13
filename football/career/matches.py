"""football/career/matches.py — 比赛记录与出场明细

职责：比赛的增删改查，以及每场比赛的「出场明细」（谁上了、踢哪、进球、助攻、评分）。

一场比赛 = matches 一行 + appearance 若干行。
出场明细的 side 字段区分我方（me）与对手（opp）：
  我方球员可以从「我的球队」里选（带 player_id，会进生涯统计）；
  对手球员只记名字（player_id 为空，不进我的生涯统计）。

写入时整场替换出场明细（先删后插），比 diff 简单且不会留下孤儿行。
"""
from . import db

_APPEARANCE_FIELDS = ("position", "minutes", "goals", "assists", "rating")


def _int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _float(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if 0 < f <= 10 else None      # 评分按 10 分制，越界当没填


def _clean_appearances(items) -> list:
    """把前端传来的出场数组整理成可入库的形状，丢掉无名条目。"""
    out = []
    for it in (items or []):
        name = str(it.get("player_name") or "").strip()
        if not name:
            continue
        out.append({
            "player_id": _int(it.get("player_id"), None) if it.get("player_id") else None,
            "player_name": name,
            "side": "opp" if str(it.get("side") or "me").lower() == "opp" else "me",
            "position": (str(it.get("position") or "").strip().upper() or None),
            "minutes": max(0, min(120, _int(it.get("minutes"), 0))),
            "goals": max(0, _int(it.get("goals"), 0)),
            "assists": max(0, _int(it.get("assists"), 0)),
            "rating": _float(it.get("rating")),
            "note": str(it.get("note") or "").strip(),
        })
    return out


def _load_appearances(c, match_id: int) -> list:
    rows = c.execute(
        "SELECT * FROM appearance WHERE match_id=? ORDER BY (side='opp'), id",
        (match_id,)).fetchall()
    return db.rows_to_dicts(rows)


def list_matches(limit: int = 100) -> list:
    """比赛列表（新的在前），每场带出场明细。"""
    with db.conn() as c:
        rows = c.execute(
            "SELECT * FROM matches ORDER BY played_on DESC, id DESC LIMIT ?",
            (max(1, int(limit)),)).fetchall()
        out = []
        for r in rows:
            m = dict(r)
            m["appearances"] = _load_appearances(c, m["id"])
            out.append(m)
    return out


def get_match(mid: int):
    with db.conn() as c:
        r = c.execute("SELECT * FROM matches WHERE id=?", (mid,)).fetchone()
        if not r:
            return None
        m = dict(r)
        m["appearances"] = _load_appearances(c, mid)
        return m


def _match_cols(data: dict) -> dict:
    my_team = str(data.get("my_team") or "").strip()
    opp = str(data.get("opponent") or "").strip()
    if not my_team or not opp:
        raise ValueError("我方队名与对手队名都不能为空")
    return {
        "played_on": str(data.get("played_on") or "").strip() or db.now()[:10],
        "competition": str(data.get("competition") or "").strip(),
        "my_team": my_team,
        "opponent": opp,
        "goals_for": max(0, _int(data.get("goals_for"), 0)),
        "goals_against": max(0, _int(data.get("goals_against"), 0)),
        "formation_id": _int(data.get("formation_id"), None) if data.get("formation_id") else None,
        "note": str(data.get("note") or "").strip(),
    }


def _insert_appearances(c, match_id: int, items: list) -> None:
    for a in items:
        c.execute(
            "INSERT INTO appearance (match_id, player_id, player_name, side, position,"
            " minutes, goals, assists, rating, note) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (match_id, a["player_id"], a["player_name"], a["side"], a["position"],
             a["minutes"], a["goals"], a["assists"], a["rating"], a["note"]),
        )


def create_match(data: dict) -> dict:
    cols = _match_cols(data)
    cols["created_at"] = db.now()
    apps = _clean_appearances(data.get("appearances"))

    with db.conn() as c:
        keys = ", ".join(cols)
        marks = ", ".join("?" * len(cols))
        cur = c.execute(f"INSERT INTO matches ({keys}) VALUES ({marks})",
                        tuple(cols.values()))
        mid = cur.lastrowid
        _insert_appearances(c, mid, apps)
    return get_match(mid)


def update_match(mid: int, data: dict) -> dict:
    if not get_match(mid):
        raise ValueError(f"比赛不存在（id={mid}）")
    cols = _match_cols(data)
    sets = ", ".join(f"{k}=?" for k in cols)

    with db.conn() as c:
        c.execute(f"UPDATE matches SET {sets} WHERE id=?", (*cols.values(), mid))
        if "appearances" in data:
            c.execute("DELETE FROM appearance WHERE match_id=?", (mid,))
            _insert_appearances(c, mid, _clean_appearances(data["appearances"]))
    return get_match(mid)


def delete_match(mid: int) -> bool:
    with db.conn() as c:
        cur = c.execute("DELETE FROM matches WHERE id=?", (mid,))
        return cur.rowcount > 0
