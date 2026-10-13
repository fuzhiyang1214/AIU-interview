"""football/career/formations.py — 战术板存档（我的阵容）

职责：把「在战术板上摆好的站位」存下来、读回来、改、删。

存的是**坐标**不是画面：
  slots = [{"team":0|1, "x":0~1, "y":0~1, "pos":"ST", "no":9, "pid":12|null}, ...]
  ball  = {"x":0~1, "y":0~1} 或 null

用 0~1 的归一化坐标而不是像素，所以换任何屏幕尺寸、任何画布大小，
读回来都摆在同一个相对位置上。
"""
import json

from . import db


def _clean_slots(items) -> list:
    """整理站位数组：坐标夹到 0~1，队号只认 0/1。"""
    out = []
    for it in (items or []):
        try:
            x = min(1.0, max(0.0, float(it.get("x"))))
            y = min(1.0, max(0.0, float(it.get("y"))))
        except (TypeError, ValueError):
            continue
        out.append({
            "team": 1 if int(it.get("team") or 0) == 1 else 0,
            "x": round(x, 4),
            "y": round(y, 4),
            "pos": str(it.get("pos") or "").strip().upper() or None,
            "no": it.get("no") if it.get("no") is not None else None,
            "pid": it.get("pid") if it.get("pid") is not None else None,
        })
    return out


def _clean_ball(ball):
    if not ball:
        return None
    try:
        return {"x": round(min(1.0, max(0.0, float(ball.get("x")))), 4),
                "y": round(min(1.0, max(0.0, float(ball.get("y")))), 4)}
    except (TypeError, ValueError):
        return None


def _load(row: dict) -> dict:
    row["slots"] = db.load_json(row.get("slots"), [])
    row["ball"] = db.load_json(row.get("ball"), None)
    return row


def list_formations() -> list:
    with db.conn() as c:
        rows = db.rows_to_dicts(
            c.execute("SELECT * FROM formation ORDER BY updated_at DESC").fetchall())
    return [_load(r) for r in rows]


def get_formation(fid: int):
    with db.conn() as c:
        r = c.execute("SELECT * FROM formation WHERE id=?", (fid,)).fetchone()
    return _load(dict(r)) if r else None


def create_formation(data: dict) -> dict:
    name = str(data.get("name") or "").strip()
    if not name:
        raise ValueError("阵容名称不能为空")
    slots = _clean_slots(data.get("slots"))
    if not slots:
        raise ValueError("阵容里一个人都没有，无法保存")

    ts = db.now()
    with db.conn() as c:
        cur = c.execute(
            "INSERT INTO formation (name, my_label, opp_label, slots, ball, note,"
            " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (name,
             str(data.get("my_label") or "我方").strip(),
             str(data.get("opp_label") or "对手").strip(),
             json.dumps(slots, ensure_ascii=False),
             json.dumps(_clean_ball(data.get("ball")), ensure_ascii=False) if data.get("ball") else None,
             str(data.get("note") or "").strip(), ts, ts))
        fid = cur.lastrowid
    return get_formation(fid)


def update_formation(fid: int, data: dict) -> dict:
    if not get_formation(fid):
        raise ValueError(f"阵容不存在（id={fid}）")
    cols = {
        "name": str(data.get("name") or "").strip() or "未命名",
        "my_label": str(data.get("my_label") or "我方").strip(),
        "opp_label": str(data.get("opp_label") or "对手").strip(),
        "slots": json.dumps(_clean_slots(data.get("slots")), ensure_ascii=False),
        "ball": (json.dumps(_clean_ball(data.get("ball")), ensure_ascii=False)
                 if data.get("ball") else None),
        "note": str(data.get("note") or "").strip(),
        "updated_at": db.now(),
    }
    sets = ", ".join(f"{k}=?" for k in cols)
    with db.conn() as c:
        c.execute(f"UPDATE formation SET {sets} WHERE id=?", (*cols.values(), fid))
    return get_formation(fid)


def delete_formation(fid: int) -> bool:
    with db.conn() as c:
        cur = c.execute("DELETE FROM formation WHERE id=?", (fid,))
        return cur.rowcount > 0
