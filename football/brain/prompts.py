"""football/brain/prompts.py — 提示词模板

职责：把结构化的分析结果翻译成给模型看的「画面简报」，并给出系统人设。
输入：analysis（vision 层输出）
输出：messages 列表

设计要点：
  1. 模型不直接看 JSON，而是看一段自然语言简报 —— 更稳、更省 token。
  2. 只让模型干两件事：判当前攻防态势、推演球可能的发展。
     不做球队识别，也不硬套 4-3-3 这类阵型名（静态单帧支撑不起）。
"""

SYSTEM = (
    "你是一名职业足球战术分析师。只依据用户给的「画面简报」说话，"
    "不要编造简报里没有的信息（例如球员号码、姓名、具体比分）。"
    "看不准时直接说不确定。语言要具体、可执行，说清「往哪条通道、用什么方式」。"
    "千万不要硬套 4-3-3、4-4-2 之类的阵型名称。"
)


def brief(analysis: dict) -> str:
    """把分析结果渲染成一段「画面简报」。"""
    counts = analysis["counts"]
    ball = analysis["ball"]
    dist = analysis.get("dist", {})
    sides = analysis.get("sides", {})

    lines = ["【画面简报】"]
    lines.append(f"- 场上球员 {counts['players']} 人：T0 队 {counts['team0']} 人，T1 队 {counts['team1']} 人")

    for t in ("0", "1"):
        z = dist.get(t)
        if z:
            lines.append(f"- T{t} 队纵向分布（上/中/下三区人数）：{z['上']} / {z['中']} / {z['下']}")

    if ball["present"]:
        lines.append(f"- 球的位置：{ball['zone']}区 · {ball['channel']}通道")
    else:
        lines.append("- 球未检出（太小或被遮挡），以下结论由球员站位推断")

    atk = sides.get("attacking")
    if atk is None:
        lines.append(f"- 攻防判定：相持（{analysis.get('reason', '')}）")
    else:
        lines.append(f"- 攻防判定：T{atk} 队进攻、T{sides.get('defending')} 队防守，"
                     f"推进方向「{analysis.get('direction')}」（{analysis.get('reason', '')}）")
        dc = analysis.get("defender_channels")
        if dc:
            lines.append(f"- 防守方通道人数：左 {dc['左']} / 中 {dc['中']} / 右 {dc['右']}，"
                         f"其中最空的是「{analysis.get('gap_channel')}」通道")

    for c in analysis.get("cues", []):
        lines.append(f"- {c}")

    return "\n".join(lines)


def advise_messages(analysis: dict) -> list:
    """生成「当前态势 + 球的发展」的 messages。"""
    body = brief(analysis)
    task = (
        "\n\n请基于以上简报，用中文输出两段，每段 3~5 句，条理清晰：\n"
        "1) 【当前进攻态势】谁在进攻、谁在防守，优势在哪条通道/哪个区域，哪块是空当；\n"
        "2) 【球可能的发展】就这张静态画面看，球接下来最可能的 2~3 种走向"
        "（往哪条通道推进、从哪里做球、哪块区域最值得利用），并说明判断依据。\n"
        "★ 简报里的「攻防判定」是系统根据球员站位算好的结论，请**直接采用**："
        "判为「相持」就按相持写，不要自己改判谁是进攻方；"
        "没有给出空当通道时，也不要凭空编一个空当。\n"
        "只依据简报里的信息；不确定就说不确定，不要编造号码或姓名，不要套阵型名。"
    )
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": body + task},
    ]


def qa_messages(question: str, analysis: dict, history: list) -> list:
    """生成「战术问答」的 messages，把简报作为固定上下文。"""
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": brief(analysis)
             + "\n\n（以上是当前画面的简报，请以此为背景回答后续提问）"},
            {"role": "assistant", "content": "收到，我已了解当前画面形势，请提问。"}]
    msgs.extend(history or [])
    msgs.append({"role": "user", "content": question})
    return msgs
