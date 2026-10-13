"""football/career/squad.py — 自建球员（我的球队）

职责：我的球员的增删改查 + 总评计算 + 能力快照（成长曲线用）。

关键设计：
  · **总评不落库**，每次读取时按当前权重现场算 —— 这样以后调整评分口径，
    历史球员的总评会自动跟上，不会出现「库里存着旧算法结果」的脏数据。
  · 每次改动能力值，往 player_snap 写一条快照。生涯页据此画成长曲线。
"""
from . import db
from .ratings import ATTRS, all_overalls, best_position, compute_overall, normalize_attrs

# 允许前端提交的标量字段（白名单，防止把任意列名写进 SQL）
_TEXT_FIELDS = ("name", "foot", "note")          # position 单独处理（要转大写）
_INT_FIELDS = ("age", "shirt_no", "potential")


def _decorate(row: dict) -> dict:
    """给数据库行补上「算出来的字段」：总评、建议位置、各位置总评。"""
    attrs = {k: row.get(k) for k in ATTRS}
    pos = row.get("position") or "CM"
    row["overall"] = compute_overall(attrs, pos)
    best, best_ovr = best_position(attrs, pos)
    row["best_position"] = best
    row["best_overall"] = best_ovr
    row["overall_by_pos"] = all_overalls(attrs)
    return row


def list_players() -> list:
    """全部自建球员（按总评从高到低）。"""
    with db.conn() as c:
        rows = db.rows_to_dicts(c.execute("SELECT * FROM my_player").fetchall())
    players = [_decorate(r) for r in rows]
    players.sort(key=lambda p: p["overall"], reverse=True)
    return players


def get_player(pid: int):
    with db.conn() as c:
        r = c.execute("SELECT * FROM my_player WHERE id=?", (pid,)).fetchone()
    return _decorate(dict(r)) if r else None


def create_player(data: dict) -> dict:
    """新建球员。name 必填，其余字段缺省即用默认值。"""
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("球员姓名不能为空")

    attrs = normalize_attrs(data)
    cols = {
        "name": name,
        "position": (data.get("position") or "CM").strip().upper(),
        "age": data.get("age"),
        "shirt_no": data.get("shirt_no"),
        "foot": (data.get("foot") or "右脚").strip(),
        "potential": data.get("potential"),
        "note": (data.get("note") or "").strip(),
        **attrs,
    }
    ts = db.now()
    cols["created_at"] = cols["updated_at"] = ts

    with db.conn() as c:
        keys = ", ".join(cols)
        marks = ", ".join("?" * len(cols))
        cur = c.execute(f"INSERT INTO my_player ({keys}) VALUES ({marks})",
                        tuple(cols.values()))
        pid = cur.lastrowid
        _snapshot(c, pid, attrs, cols["position"])

    return get_player(pid)


def update_player(pid: int, data: dict) -> dict:
    """更新球员（只改传进来的字段）。能力值有变化时补一条快照。"""
    old = get_player(pid)
    if not old:
        raise ValueError(f"球员不存在（id={pid}）")
    if "name" in data and not str(data.get("name") or "").strip():
        raise ValueError("球员姓名不能为空")

    sets, vals = [], []
    for f in _TEXT_FIELDS:
        if f in data and data[f] is not None:
            sets.append(f"{f}=?")
            vals.append(str(data[f]).strip())
    if "position" in data and data["position"]:
        sets.append("position=?")
        vals.append(str(data["position"]).strip().upper())
    for f in _INT_FIELDS:
        if f in data:
            sets.append(f"{f}=?")
            v = data[f]
            vals.append(None if v in ("", None) else int(v))
    for k in ATTRS:
        if k in data:
            sets.append(f"{k}=?")
            vals.append(normalize_attrs({k: data[k]})[k])

    if not sets:
        return old

    sets.append("updated_at=?")
    vals.append(db.now())
    vals.append(pid)

    with db.conn() as c:
        c.execute(f"UPDATE my_player SET {', '.join(sets)} WHERE id=?", tuple(vals))
        cur = c.execute("SELECT * FROM my_player WHERE id=?", (pid,)).fetchone()
        fresh = dict(cur)
        # 只在「能力值确实变了」时记快照，避免改个备注也留下一条曲线点
        if any(fresh.get(k) != old.get(k) for k in ATTRS):
            _snapshot(c, pid, {k: fresh[k] for k in ATTRS}, fresh["position"])

    return get_player(pid)


def delete_player(pid: int) -> bool:
    """删除球员档案。

    顺带把他历次出场的 player_id **解绑**（置空，保留球员名）：
    「把人移出球队」和「把历史抹掉」是两回事 —— 否则删一个球员，
    他打过的比赛、进过的球会直接从生涯统计里消失，等于篡改了战绩。
    解绑后他会作为「历史球员」继续出现在生涯表里。
    """
    with db.conn() as c:
        c.execute("UPDATE appearance SET player_id=NULL WHERE player_id=?", (pid,))
        cur = c.execute("DELETE FROM my_player WHERE id=?", (pid,))
        return cur.rowcount > 0


def _snapshot(c, pid: int, attrs: dict, position: str) -> None:
    """写一条能力快照（调用方负责已持有连接）。"""
    c.execute(
        "INSERT INTO player_snap (player_id, overall, position, taken_at) VALUES (?,?,?,?)",
        (pid, compute_overall(attrs, position), position, db.now()),
    )


def snapshots(pid: int) -> list:
    """某球员的总评变化序列 —— 生涯页画成长曲线用。"""
    with db.conn() as c:
        rows = c.execute(
            "SELECT overall, position, taken_at FROM player_snap "
            "WHERE player_id=? ORDER BY id", (pid,)).fetchall()
    return db.rows_to_dicts(rows)
