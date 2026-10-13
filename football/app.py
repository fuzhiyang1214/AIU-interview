"""football/app.py — 全栈后端（Flask）

职责：只做「组装」——把视觉层、战术板、战术推理层、球员库、生涯数据层接起来，
     暴露 HTTP 接口。本文件不含任何检测算法、判定逻辑、提示词或 SQL，
     连图像的解码与摄像头采集都在 vision/ 里（见 vision/frames.py），
     所以这里既不 import cv2 也不 import numpy。
     （按要求：不做球队识别，只判攻防态势 + 推演球的发展）

接口：
  GET  /                          前端页面
  -- 图像分析（AI 看图）------------------------------------------------
  POST /api/analyze               上传截图（或抓摄像头）→ 分析 + 标注图
  GET  /api/state                 当前缓存的局面（调试用）
  -- 战术板（手动排兵布阵）--------------------------------------------
  GET  /api/tactics/meta          位置列表 / 起点模板 / 画布尺寸
  POST /api/tactics/analyze       手动站位 → 与图像分析同构的结论
  -- 战术推理（两条输入路径共用）--------------------------------------
  POST /api/advise                基于当前局面 → 「当前态势 + 球可能的发展」
  POST /api/ask                   基于当前局面 → 战术问答
  -- 球员库（世界球员数据）--------------------------------------------
  GET  /api/player/stats          库规模与可用排序维度
  GET  /api/player/search         球员搜索
  GET  /api/player/rank           球员榜单
  GET  /api/player/<sid>          球员详情卡
  -- 我的生涯（自建数据，SQLite）--------------------------------------
  GET  /api/career/meta           评分规则的描述（位置列表 / 六维名），前端据此建表单
  POST /api/career/rate           六维 + 位置 → 总评（**评分只在后端算**）
  GET/POST        /api/career/squad           我的球员：列表 / 新建
  PUT/DELETE      /api/career/squad/<pid>     我的球员：修改 / 删除
  GET             /api/career/squad/<pid>/snapshots   能力成长快照
  GET/POST        /api/career/formations      阵容存档：列表 / 新建
  PUT/DELETE      /api/career/formations/<fid>
  GET/POST        /api/career/matches         比赛记录：列表 / 新建
  PUT/DELETE      /api/career/matches/<mid>
  GET  /api/career/summary        生涯总览（战绩 / 球员榜 / 时间线）

运行（必须用装了 torch 的 venv；战术板与图像分析共用同一进程）：
  D:\\envs\\yolo\\Scripts\\python.exe app.py --port 8100

对应出题人规范：
  第 1 条 主程序只负责组装；第 3 条 顶部有注释；第 4 条 前后端解耦（后端只算与推，前端只显示）。
"""
import argparse
import os
from functools import wraps

from flask import Flask, jsonify, request, send_from_directory
from flask.json.provider import DefaultJSONProvider

import career
from brain import advise as brain_advise, answer as brain_answer
from players import (player_card, rank_players, search_players)
from players import stats as player_stats
from players import warmup as players_warmup
from tactics import analyze_board, catalog as tactics_catalog, summarize as board_summary
from vision import analyze_image, decode_data_url, grab_camera, to_base64_jpeg

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = Flask(__name__, static_folder=None)


class _NumpySafeJSON(DefaultJSONProvider):
    """兜底：把 numpy 标量 / 数组降级成原生类型再序列化。

    为什么要有：Flask 默认的 jsonify 不认 numpy 类型 —— 曾经
    `cv2.connectedComponentsWithStats` 的 **int32** 从视觉层漏出来，接口直接抛
    `TypeError: Object of type int32 is not JSON serializable`。
    根因已在 `vision/locate.py` 修掉（返回值统一 int），这里只做**框架层兜底**，
    让将来任何一处漏网不至于打成 500。

    刻意用鸭子类型（`.item()` / `.tolist()`）判断，**不 import numpy** ——
    否则会破坏「主程序不 import cv2 / numpy」这条解耦约定。
    """

    @staticmethod
    def default(o):
        # 先试 .tolist()：它对 np 标量（int32/float32…）和 ndarray **都成立**
        # （标量会得到原生标量，数组会递归还原成嵌套 list）。
        # 顺序不能反 —— ndarray 也有 .item()，多元素时 .item() 会直接抛 ValueError。
        tolist = getattr(o, "tolist", None)
        if callable(tolist):
            return tolist()
        item = getattr(o, "item", None)
        if callable(item):
            return item()
        return DefaultJSONProvider.default(o)


app.json = _NumpySafeJSON(app)

# 单用户本地应用：只缓存「当前局面」。
# ★ 图像分析和战术板**写的是同一个 STATE** —— 于是 /advise 与 /ask 不用改一行，
#   就同时支持「看图说话」和「摆阵推演」两条路。labels 记录队伍称呼。
STATE = {"analysis": None, "chat": [], "labels": None}

# imgsz = 0 → 自动：先裁出球场区域，再按长边 2.4 倍换算推理尺寸（1280~3200）
ARGS = {"conf": 0.35, "imgsz": 0, "device": "cuda:0"}

# 生涯库建表（幂等）—— 放在模块级，保证任何入口（app / desktop / 测试）进来表都在
career.init_db()


# ---------------------------------------------------------------- 通用小工具
def _body() -> dict:
    return request.get_json(silent=True) or {}


def _fail(msg, code: int = 400):
    return jsonify({"ok": False, "error": str(msg)}), code


def api(fn):
    """统一的接口外壳：把 ValueError 当 400（用户输入问题），其余当 500。

    这样各路由里只写正常逻辑，不用每处都套 try/except。
    """
    @wraps(fn)
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except ValueError as e:
            return _fail(e, 400)
        except Exception as e:
            return _fail(f"{type(e).__name__}: {e}", 500)
    return wrapper


def _flag(name: str, default: bool = True) -> bool:
    """解析查询串里的布尔开关：?online=0 / false / no / off 都算关。"""
    v = request.args.get(name)
    if v is None:
        return default
    return v.strip().lower() not in ("0", "false", "no", "off", "")


def _int_arg(name: str, default: int, hi: int = 60) -> int:
    """取整型查询参数，非法值退回默认，并封顶防止一次拉爆。"""
    try:
        v = int(request.args.get(name, default))
    except (TypeError, ValueError):
        v = default
    return max(1, min(v, hi))


def _labels_from(body: dict):
    """战术板的队伍称呼 → {0: 我方, 1: 对手}；两边都没填就返回 None。"""
    my = str(body.get("my_label") or "").strip()
    opp = str(body.get("opp_label") or "").strip()
    if not my and not opp:
        return None
    return {0: my or "我方", 1: opp or "对手"}


# ---------------------------------------------------------------- 页面
@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


# ---------------------------------------------------------------- 图像分析
@app.route("/api/analyze", methods=["POST"])
@api
def api_analyze():
    body = _body()
    if body.get("source") == "camera":
        frame = grab_camera()                       # 采集在 vision/frames.py
    else:
        if not body.get("image"):
            raise ValueError("缺少 image 字段")
        frame = decode_data_url(body["image"])      # 解码也在 vision/frames.py
        if frame is None:
            raise ValueError("图片解码失败")

    analysis, annotated = analyze_image(
        frame, conf=ARGS["conf"], imgsz=ARGS["imgsz"], device=ARGS["device"])

    STATE.update(analysis=analysis, chat=[], labels=None)   # 图像场景两队无名
    return jsonify({"ok": True, "analysis": analysis,
                    "annotated": to_base64_jpeg(annotated)})


@app.route("/api/state")
def api_state():
    return jsonify({"ok": True, "has_analysis": STATE["analysis"] is not None,
                    "source": (STATE["analysis"] or {}).get("source", "image")})


# ---------------------------------------------------------------- 战术板
@app.route("/api/tactics/meta")
def api_tactics_meta():
    meta = tactics_catalog()
    return jsonify({"ok": True, **meta})


@app.route("/api/tactics/analyze", methods=["POST"])
@api
def api_tactics_analyze():
    """手动站位 → 结论。与 /api/analyze 输出同构，前端可复用同一套渲染。"""
    body = _body()
    slots = body.get("slots") or []
    if not slots:
        raise ValueError("战术板上还没有球员，先摆几个人再分析")

    analysis = analyze_board(slots, ball=body.get("ball"))
    labels = _labels_from(body)
    STATE.update(analysis=analysis, chat=[], labels=labels)
    return jsonify({"ok": True, "analysis": analysis,
                    "summary": board_summary(analysis, labels)})


# ---------------------------------------------------------------- 战术推理
@app.route("/api/advise", methods=["POST"])
@api
def api_advise():
    if not STATE["analysis"]:
        raise ValueError("请先分析一张截图，或在战术板上摆好站位")
    return jsonify({"ok": True, "advice": brain_advise(STATE["analysis"], STATE["labels"])})


@app.route("/api/ask", methods=["POST"])
@api
def api_ask():
    if not STATE["analysis"]:
        raise ValueError("请先分析一张截图，或在战术板上摆好站位")
    q = str(_body().get("question") or "").strip()
    if not q:
        raise ValueError("问题为空")
    a = brain_answer(q, STATE["analysis"], STATE["chat"], STATE["labels"])
    STATE["chat"] += [{"role": "user", "content": q},
                      {"role": "assistant", "content": a}]
    return jsonify({"ok": True, "answer": a})


# ---------------------------------------------------------------- 球员库
@app.route("/api/player/stats")
def api_player_stats():
    return jsonify({"ok": True, **player_stats()})


@app.route("/api/player/search")
@api
def api_player_search():
    q = (request.args.get("q") or "").strip()
    if not q:
        raise ValueError("缺少 q 参数")
    rows = search_players(q, limit=_int_arg("limit", 20),
                          pos=(request.args.get("pos") or "").strip() or None,
                          online=_flag("online", True))
    return jsonify({"ok": True, "count": len(rows), "players": rows})


@app.route("/api/player/rank")
def api_player_rank():
    rows = rank_players(by=(request.args.get("by") or "overall").strip(),
                        limit=_int_arg("limit", 20),
                        pos=(request.args.get("pos") or "").strip() or None,
                        online=_flag("online", False))   # 榜单默认离线，避免一屏 20 次联网
    return jsonify({"ok": True, "count": len(rows), "players": rows})


@app.route("/api/player/<sid>")
@api
def api_player_detail(sid):
    card = player_card(sid, online=_flag("online", True))
    if not card:
        return _fail(f"查无此人（id={sid}）", 404)
    return jsonify({"ok": True, "player": card})


# ---------------------------------------------------------------- 我的生涯
@app.route("/api/career/meta")
def api_career_meta():
    """评分规则的描述：位置列表 + 六维名（前端据此建下拉与滑块）。"""
    return jsonify({"ok": True, **career.ratings_table()})


@app.route("/api/career/rate", methods=["POST"])
@api
def api_career_rate():
    """六维 + 位置 → 总评（含「建议位置」）。

    前端拖滑块时实时问这里，**不在浏览器里复制评分公式** ——
    否则同一套规则两份实现，还得靠人工同步才能一致（规范第 4 条）。
    """
    return jsonify({"ok": True, **career.rate(_body())})


@app.route("/api/career/squad", methods=["GET", "POST"])
@api
def api_career_squad():
    if request.method == "GET":
        return jsonify({"ok": True, "players": career.list_players()})
    p = career.create_player(_body())
    return jsonify({"ok": True, "player": p})


@app.route("/api/career/squad/<int:pid>", methods=["GET", "PUT", "DELETE"])
@api
def api_career_squad_one(pid):
    if request.method == "DELETE":
        if not career.delete_player(pid):
            return _fail(f"球员不存在（id={pid}）", 404)
        return jsonify({"ok": True})
    if request.method == "PUT":
        return jsonify({"ok": True, "player": career.update_player(pid, _body())})
    p = career.get_player(pid)
    if not p:
        return _fail(f"球员不存在（id={pid}）", 404)
    return jsonify({"ok": True, "player": p})


@app.route("/api/career/squad/<int:pid>/snapshots")
@api
def api_career_snapshots(pid):
    return jsonify({"ok": True, "snapshots": career.snapshots(pid)})


@app.route("/api/career/formations", methods=["GET", "POST"])
@api
def api_career_formations():
    if request.method == "GET":
        return jsonify({"ok": True, "formations": career.list_formations()})
    return jsonify({"ok": True, "formation": career.create_formation(_body())})


@app.route("/api/career/formations/<int:fid>", methods=["GET", "PUT", "DELETE"])
@api
def api_career_formation_one(fid):
    if request.method == "DELETE":
        if not career.delete_formation(fid):
            return _fail(f"阵容不存在（id={fid}）", 404)
        return jsonify({"ok": True})
    if request.method == "PUT":
        return jsonify({"ok": True, "formation": career.update_formation(fid, _body())})
    f = career.get_formation(fid)
    if not f:
        return _fail(f"阵容不存在（id={fid}）", 404)
    return jsonify({"ok": True, "formation": f})


@app.route("/api/career/matches", methods=["GET", "POST"])
@api
def api_career_matches():
    if request.method == "GET":
        return jsonify({"ok": True, "matches": career.list_matches(_int_arg("limit", 100, 500))})
    return jsonify({"ok": True, "match": career.create_match(_body())})


@app.route("/api/career/matches/<int:mid>", methods=["GET", "PUT", "DELETE"])
@api
def api_career_match_one(mid):
    if request.method == "DELETE":
        if not career.delete_match(mid):
            return _fail(f"比赛不存在（id={mid}）", 404)
        return jsonify({"ok": True})
    if request.method == "PUT":
        return jsonify({"ok": True, "match": career.update_match(mid, _body())})
    m = career.get_match(mid)
    if not m:
        return _fail(f"比赛不存在（id={mid}）", 404)
    return jsonify({"ok": True, "match": m})


@app.route("/api/career/summary")
def api_career_summary():
    return jsonify({"ok": True, **career.career_summary()})


def main():
    ap = argparse.ArgumentParser(description="AI 战术分析师（全栈）")
    ap.add_argument("--port", type=int, default=8100)
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--imgsz", type=int, default=0,
                    help="推理尺寸；0=自动（裁到球场后按长边 2.4 倍换算，1280~3200）")
    ap.add_argument("--device", default="cuda:0")
    args = ap.parse_args()
    ARGS.update(conf=args.conf, imgsz=args.imgsz, device=args.device)

    print(f"AI 战术分析师已启动： http://127.0.0.1:{args.port}")
    print(f"球员库已就绪：{players_warmup()} 名球员（搜索 / 榜单 / 详情均可用）")
    print(f"生涯库已就绪：{career.DB_PATH}")
    print("（Ctrl+C 停止；首次分析会自动加载 YOLO 权重）")
    app.run(host="127.0.0.1", port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
