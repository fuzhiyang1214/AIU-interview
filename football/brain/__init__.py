"""football/brain/__init__.py — 战术推理层入口"""
from .analyst import advise, answer
from .llm import chat, MODEL

__all__ = ["advise", "answer", "chat", "MODEL"]
