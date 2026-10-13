"""football/career/ratings.py — 自建球员的能力评分规则

职责：定义「六维能力 + 位置」怎么算出一个总评（overall）。
      这是本模块唯一对外提供评分口径的地方 —— 前端画滑块时也读它，
      保证「界面上显示的总评」与「后端存下来的总评」永远是同一个公式。

为什么用位置加权：
  同一个能力组合，打不同位置价值完全不同 ——
  速度 90 / 防守 40 的球员，在边锋位是快马，在中卫位是漏勺。
  所以总评 = 该位置各项能力的加权平均，权重按位置分配（每行权重和为 1）。

门将说明：
  本项目只有六维，没有单独的扑救/手型维度。门将沿用同一套六维，
  但把 defending 解释为「门线技术/站位」、physical 解释为「弹跳与对抗」，
  这样前端不必为门将单开一组滑块。
"""

import math

# 六维能力（与 EA FC 数据集、前端滑块、球员库保持一致）
ATTRS = ("pace", "shooting", "passing", "dribbling", "defending", "physical")

ATTR_CN = {
    "pace": "速度", "shooting": "射门", "passing": "传球",
    "dribbling": "盘带", "defending": "防守", "physical": "身体",
}

# 可选位置（前端下拉直接读这份列表）
POSITIONS = ["GK", "LB", "CB", "RB", "LWB", "RWB",
             "CDM", "CM", "CAM", "LM", "RM", "LW", "RW", "CF", "ST"]

# 位置权重：每行 6 个数，顺序与 ATTRS 一致，和为 1
POS_WEIGHTS = {
    "GK":  (0.08, 0.02, 0.10, 0.05, 0.45, 0.30),
    "CB":  (0.10, 0.02, 0.10, 0.06, 0.47, 0.25),
    "LB":  (0.30, 0.04, 0.16, 0.14, 0.26, 0.10),
    "RB":  (0.30, 0.04, 0.16, 0.14, 0.26, 0.10),
    "LWB": (0.32, 0.05, 0.18, 0.16, 0.22, 0.07),
    "RWB": (0.32, 0.05, 0.18, 0.16, 0.22, 0.07),
    "CDM": (0.10, 0.05, 0.24, 0.11, 0.35, 0.15),
    "CM":  (0.12, 0.10, 0.32, 0.20, 0.16, 0.10),
    "CAM": (0.14, 0.20, 0.30, 0.26, 0.04, 0.06),
    "LM":  (0.28, 0.10, 0.22, 0.24, 0.10, 0.06),
    "RM":  (0.28, 0.10, 0.22, 0.24, 0.10, 0.06),
    "LW":  (0.32, 0.20, 0.14, 0.28, 0.02, 0.04),
    "RW":  (0.32, 0.20, 0.14, 0.28, 0.02, 0.04),
    "CF":  (0.22, 0.34, 0.12, 0.22, 0.02, 0.08),
    "ST":  (0.24, 0.38, 0.08, 0.20, 0.02, 0.08),
}

# 位置分组：用于「建议位置」时只在该组内比，避免把中卫拿去踢边锋
FALLBACK_WEIGHTS = POS_WEIGHTS["CM"]     # 位置填了不认识的字符串时按中场算


def _clamp(v, lo=1, hi=99) -> int:
    """把能力值夹到合法区间（1~99，与 EA FC 的取值习惯一致）。

    ★ 用 floor(x+0.5) 而不是 round()：Python 的 round() 是「银行家舍入」
      （round(84.5)=84），而前端 JS 的 Math.round 是四舍五入（84.5→85）。
      两边口径不一，会出现「拖动滑块时显示 84、一保存变 85」的鬼影。
      统一成四舍五入，前端实时预览与后端落库结果永远一致。
    """
    try:
        v = math.floor(float(v) + 0.5)
    except (TypeError, ValueError):
        v = lo
    return max(lo, min(hi, v))


def normalize_attrs(raw: dict) -> dict:
    """把任意输入整理成合法的六维字典（缺项按 60 补，越界夹紧）。"""
    out = {}
    for k in ATTRS:
        out[k] = _clamp(raw.get(k, 60))
    return out


def _weights_of(position: str):
    """取某位置的权重向量；不认识的位置退回中场。"""
    key = (position or "").strip().upper()
    return POS_WEIGHTS.get(key, FALLBACK_WEIGHTS)


def compute_overall(attrs: dict, position: str = "CM") -> int:
    """按位置加权算出总评。

    Args:
        attrs: 六维字典（会自动 normalize）。
        position: 位置代码，如 "ST"。

    Returns:
        1~99 的整数总评。
    """
    a = normalize_attrs(attrs)
    w = _weights_of(position)
    total = sum(a[k] * w[i] for i, k in enumerate(ATTRS))
    return _clamp(total)


def all_overalls(attrs: dict) -> dict:
    """同一套能力在全部位置上的总评 —— 用于「他最适合踢哪」。"""
    a = normalize_attrs(attrs)
    return {p: _clamp(sum(a[k] * w[i] for i, k in enumerate(ATTRS)))
            for p, w in POS_WEIGHTS.items()}


# 场上位置（不含门将）——「建议位置」只在这些人里比
FIELD_POSITIONS = tuple(p for p in POSITIONS if p != "GK")


def best_position(attrs: dict, current: str = "") -> tuple:
    """返回 (最佳位置, 该位置的总评)。

    两条规则，都是踩过坑补上的：
      1. **门将不参与跨位置比较**：门将和中卫的能力画像高度重合
         （都靠 defending + physical），放开比会把中卫算成门将，很外行。
         所以当前是门将就只认门将，不是门将就只在场上位置里找。
      2. 其余位置放开比 —— 速度型边卫被算成边前卫是有信息量的，
         前端标成「建议」而不是「改位置」。
    """
    a = normalize_attrs(attrs)
    keys = ("GK",) if (current or "").strip().upper() == "GK" else FIELD_POSITIONS
    m = {p: _clamp(sum(a[k] * POS_WEIGHTS[p][i] for i, k in enumerate(ATTRS)))
         for p in keys}
    best = max(m, key=m.get)
    return best, m[best]


def weights_table() -> dict:
    """导出完整的权重表（描述评分规则，便于公开口径与排查）。"""
    return {
        "attrs": list(ATTRS),
        "attrs_cn": ATTR_CN,
        "positions": POSITIONS,
        "weights": {p: {k: w[i] for i, k in enumerate(ATTRS)}
                    for p, w in POS_WEIGHTS.items()},
    }


def rate(attrs: dict, position: str = "") -> dict:
    """一次算好「当前位置总评 + 建议位置」。

    这是「求解总评」唯一该走的入口 —— 公式只存在本模块一份，
    前端拖滑块时问后端，不再在浏览器里复制一套（规范第 4 条：后端只负责计算）。

    Args:
        attrs: 六维字典；**可以直接传前端表单**（多出的 position 等字段不影响，
               只取 ATTRS 里的六项）。
        position: 位置代码；留空则从 attrs["position"] 取，再退回 CM。
    """
    pos = position or attrs.get("position") or "CM"
    best, best_ovr = best_position(attrs, pos)
    return {"overall": compute_overall(attrs, pos),
            "best_position": best, "best_overall": best_ovr}
