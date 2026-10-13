# -*- coding: utf-8 -*-
"""football/app.py 全接口自测 —— 用 Flask test_client，不起真实端口。

用法（必须用装了 flask/cv2 的那个 venv）：
    D:\\envs\\yolo\\Scripts\\python.exe test_api.py

设计说明：
  · 生涯库默认指向临时文件（FOOTBALL_CAREER_DB），**不碰真实的 career.db**，跑完自动删除。
  · 负向用例（缺参数 -> 400、查无此 id -> 404）显式声明期望值，与正向用例分开统计。
  · 摄像头分支不测（需要真实设备权限），图像分析走仓库里的一张本地图。
  · /api/advise、/api/ask 需要本机 Ollama 在跑；不在跑会 500，属正常。
"""
import base64
import glob
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def _find_root():
    """从脚本所在位置向上找带 football/ 的目录；找不到就用环境变量或默认路径。"""
    p = HERE
    for _ in range(6):
        if os.path.isdir(os.path.join(p, "football")):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    return os.environ.get("FOOTBALL_ROOT", r"C:\Users\FU\Desktop\ai-interview")


ROOT = _find_root()

# —— 隔离：生涯库写临时文件 ——
TMP_DB = os.path.join(tempfile.gettempdir(), "career_api_test.db")
if os.path.exists(TMP_DB):
    os.remove(TMP_DB)
os.environ["FOOTBALL_CAREER_DB"] = TMP_DB

sys.path.insert(0, os.path.join(ROOT, "football"))

t0 = time.time()
from app import app          # noqa: E402
print(f"[载入 app] {time.time() - t0:.2f}s\n")

c = app.test_client()
rows = []


def check(method, path, expect=200, ok_field=True, **kw):
    """发一个请求并记录结果。

    expect=200 时：状态码要对，且 JSON 里 ok 不能是 false。
    expect!=200 时：只比状态码（负向用例本来就该 ok=false）。
    """
    t = time.time()
    r = getattr(c, method)(path, **kw)
    dt = (time.time() - t) * 1000
    j = None
    try:
        j = r.get_json()
    except Exception:
        pass

    good = (r.status_code == expect)
    note = ""
    if isinstance(j, dict):
        if expect == 200:
            if ok_field and "ok" in j and not j.get("ok"):
                good = False
                note = f"ok=false: {j.get('error')}"
            else:
                keep = {k: v for k, v in j.items()
                        if k in ("count", "has_analysis", "attacking_team",
                                 "overall", "best_position")
                        and not isinstance(v, (list, dict))}
                if keep:
                    note = " ".join(f"{k}={v}" for k, v in keep.items())
        else:
            note = "预期错误分支：" + str(j.get("error") or "")[:38]

    if not good and not note:                    # 失败时至少把响应体带出来，否则只剩一个 500
        note = r.data[:160].decode("utf-8", "replace").replace("\n", " ").strip()

    rows.append((good, method.upper(), path, r.status_code, expect, dt, note))
    print(f"[{'OK' if good else '!!'}] {method.upper():6s} {path:46s} "
          f"{r.status_code:3d} (期望 {expect}) {dt:7.1f}ms  {note}")
    return r, j


def section(title):
    print()
    print("=" * 104)
    print(title)
    print("=" * 104)


section("① 页面与静态接口")
check("get", "/")
check("get", "/api/state")
check("get", "/api/tactics/meta")

section("② 球员库（online=0 强制离线，避免联网等待）")
check("get", "/api/player/stats")
r, j = check("get", "/api/player/search?q=messi&online=0")
sid = (j or {}).get("players", [{}])[0].get("id")
check("get", "/api/player/search", expect=400)                        # 缺 q
check("get", "/api/player/rank?by=overall&limit=5&online=0")
check("get", "/api/player/rank?by=pace&pos=ST&limit=3&online=0")
if sid:
    check("get", f"/api/player/{sid}?online=0")
check("get", "/api/player/99999999?online=0", expect=404)             # 查无此人

section("③ 战术板（不依赖 torch / 网络）")
SLOTS = [{"team": 0, "x": 300, "y": 200}, {"team": 0, "x": 400, "y": 220},
         {"team": 0, "x": 500, "y": 300}, {"team": 1, "x": 600, "y": 200},
         {"team": 1, "x": 700, "y": 260}]
check("post", "/api/tactics/analyze", json={}, expect=400)            # 空板
check("post", "/api/tactics/analyze",
      json={"slots": SLOTS, "ball": {"x": 520, "y": 300},
            "my_label": "计算机学院", "opp_label": "外语学院"})
check("post", "/api/tactics/analyze", json={"slots": [{"team": 0, "x": 500, "y": 340}]})

section("④ 我的生涯 —— 完整 CRUD（写临时库）")
check("get", "/api/career/meta")
check("post", "/api/career/rate", json={})                            # 空表单 → 全 60 也照算
check("post", "/api/career/rate",
      json={"position": "ST", "pace": 88, "shooting": 84, "passing": 70,
            "dribbling": 80, "defending": 35, "physical": 76})
check("get", "/api/career/squad")
check("post", "/api/career/squad", json={}, expect=400)               # 无名
r, j = check("post", "/api/career/squad",
             json={"name": "测试球员", "position": "ST", "age": 23,
                   "pace": 88, "shooting": 84, "passing": 70,
                   "dribbling": 80, "defending": 35, "physical": 76, "potential": 91})
pid = ((j or {}).get("player") or {}).get("id")
if pid:
    check("get", f"/api/career/squad/{pid}")
    check("put", f"/api/career/squad/{pid}", json={"pace": 93})       # 部分更新
    check("get", f"/api/career/squad/{pid}/snapshots")
check("get", "/api/career/squad/999999", expect=404)
check("delete", "/api/career/squad/999999", expect=404)

check("post", "/api/career/formations", json={}, expect=400)          # 无名
r, j = check("post", "/api/career/formations",
             json={"name": "4-4-2 测试", "my_label": "我方", "opp_label": "对手",
                   "slots": SLOTS})
fid = ((j or {}).get("formation") or {}).get("id")
check("get", "/api/career/formations")
if fid:
    check("get", f"/api/career/formations/{fid}")
    check("put", f"/api/career/formations/{fid}", json={"name": "4-4-2 改名"})
    check("delete", f"/api/career/formations/{fid}")
check("get", "/api/career/formations/999999", expect=404)

MATCH = {"played_on": "2026-10-13", "competition": "测试联赛",
         "my_team": "计科队", "opponent": "电信队",
         "goals_for": 2, "goals_against": 1,
         "appearances": [
             {"player_name": "测试球员", "player_id": pid, "side": "me",
              "position": "ST", "minutes": 90, "goals": 2, "rating": 8.0},
             {"player_name": "对方前锋", "side": "opp", "minutes": 90, "goals": 1}]}
check("post", "/api/career/matches", json={}, expect=400)             # 无队名
r, j = check("post", "/api/career/matches", json=MATCH)
mid = ((j or {}).get("match") or {}).get("id")
check("get", "/api/career/matches")
if mid:
    check("get", f"/api/career/matches/{mid}")
    check("put", f"/api/career/matches/{mid}",
          json={**MATCH, "goals_for": 3, "note": "改过比分"})          # PUT 全量
check("get", "/api/career/matches/999999", expect=404)
check("get", "/api/career/summary")
if mid:
    check("delete", f"/api/career/matches/{mid}")

section("⑤ 战术推理（需要本机 Ollama 在跑；不在跑会 500，属正常）")
check("post", "/api/ask", json={}, expect=400)                        # 空问题
r_adv, _ = check("post", "/api/advise", json={}, ok_field=False)
if r_adv.status_code != 200:
    print("     （Ollama 未启动，跳过 /api/advise 与 /api/ask 的正向用例）")
else:
    check("post", "/api/ask", json={"question": "现在谁在进攻？"}, ok_field=False)

section("⑥ 图像分析（要加载 YOLO 权重，首帧慢）")
check("post", "/api/analyze", json={}, expect=400)                    # 缺 image
imgs = sorted(glob.glob(os.path.join(ROOT, "yolo", "**", "*.jpg"), recursive=True))
if imgs:
    with open(imgs[0], "rb") as f:
        b64 = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
    print(f"     （用图：{os.path.relpath(imgs[0], ROOT)}）")
    check("post", "/api/analyze", json={"image": b64}, ok_field=False)
    check("get", "/api/state")
else:
    print("     （仓库里没找到 jpg，跳过图像分析）")

# 真实球场截图：会走「裁到球场」这条分支 —— 它是 numpy 整数漏进响应的唯一路径。
# 普通照片走的是「返回整幅」分支（纯 Python int），所以只有这张图能守住
# 「Object of type int32 is not JSON serializable」这类坑。
grass = os.path.join(ROOT, "football", "test", "11_tactic_before.png")
if os.path.isfile(grass):
    with open(grass, "rb") as f:
        b64g = "data:image/png;base64," + base64.b64encode(f.read()).decode()
    print("     （用图：football/test/11_tactic_before.png —— 触发「裁到球场」分支）")
    _, j_g = check("post", "/api/analyze", json={"image": b64g}, ok_field=False)

    # 「未计入」必须是**结构化字段**：前端靠 a.unassigned.count 才渲染那一行。
    # 它曾经被 `**geo` 里的裸 int 整个盖掉 → 界面上那一行永远不出现
    #（截图里 9 = 5 + 3 + 1，却看不到「未计入 1 人」）。顺带守住人数守恒。
    _a = (j_g or {}).get("analysis") or {}
    u = _a.get("unassigned")
    cnt = _a.get("counts") or {}
    ok_u = isinstance(u, dict) and isinstance(u.get("count"), int)
    ok_sum = bool(ok_u) and cnt.get("players") == cnt.get("on_pitch", -1) + u["count"]
    good_u = ok_u and ok_sum
    rows.append((good_u, "CHECK", "unassigned 结构化 + 人数守恒", 200, 200, 0.0,
                 f"unassigned={u} players={cnt.get('players')} on_pitch={cnt.get('on_pitch')}"))
    print(f"[{'OK' if good_u else '!!'}] CHECK  unassigned 结构化字段 + 人数守恒"
          f"   unassigned={u}  players={cnt.get('players')} on_pitch={cnt.get('on_pitch')}")
else:
    print("     （没找到球场实拍图，跳过「裁到球场」分支）")

# ---------------------------------------------------------------- 汇总
print()
print("=" * 104)
ok_n = sum(1 for r in rows if r[0])
print(f"结果：{ok_n} / {len(rows)} 通过")
bad = [r for r in rows if not r[0]]
if bad:
    print("\n未通过：")
    for _, m, p, got, exp, _, note in bad:
        print(f"  {m} {p} -> {got}（期望 {exp}）{note}")

if os.path.exists(TMP_DB):
    os.remove(TMP_DB)
print(f"\n临时生涯库已清理：{TMP_DB}")
