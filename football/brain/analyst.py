"""football/brain/analyst.py — 战术推理

职责：消费视觉层的结论，产出人话（不再涉及球队识别）。
  - advise(): 当前攻防态势 + 球可能的发展（一次性）
  - answer(): 基于当前画面上下文的战术问答
输入：analysis（vision 输出）
输出：字符串
"""
from . import llm, prompts


def advise(analysis: dict, labels: dict = None, model: str = llm.MODEL) -> str:
    """生成「当前进攻态势 + 球可能的发展」。

    labels 可选：{0: "我的球队", 1: "对手"}。图像分析不传（两队无名），
    战术板传真实队名，简报里的称呼跟着变，其余口径完全一致。
    """
    try:
        return llm.chat(prompts.advise_messages(analysis, labels), model=model)
    except Exception as e:
        return f"（战术建议生成失败：{type(e).__name__}: {e}）\n请确认本机 Ollama 已启动且已拉取 {model}。"


def answer(question: str, analysis: dict, history: list | None = None,
           labels: dict = None, model: str = llm.MODEL) -> str:
    """回答一句战术提问。"""
    try:
        return llm.chat(prompts.qa_messages(question, analysis, history or [], labels),
                        model=model, temperature=0.5)
    except Exception as e:
        return f"（回答失败：{type(e).__name__}: {e}）\n请确认本机 Ollama 已启动。"
