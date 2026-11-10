"""Prompt 工程：AI 玩家角色提示词、兜底台词、AI 教练评分提示词。"""

from __future__ import annotations

import hashlib
from typing import Iterable

from ..config import GAME_NAME
from ..content.levels import LEVELS_BY_ID
from ..content.personas import PERSONAS

TRAINEE_ROLE_LABEL = "客服"
PLAYER_ROLE_LABEL = "玩家"


def emotion_band(emotion: int) -> str:
    if emotion <= 3:
        return "calm"
    if emotion <= 6:
        return "mid"
    return "hot"


def emotion_guidance(emotion: int) -> str:
    if emotion <= 3:
        return "你现在的情绪已经基本平复，愿意配合客服解决问题，语气放松。"
    if emotion <= 5:
        return "你仍然有些不快，但愿意听客服解释，需要对方给出明确动作才能安心。"
    if emotion <= 7:
        return "你明显不耐烦，语气开始变硬，会追问、会质疑客服是否在敷衍。"
    if emotion <= 9:
        return "你很生气，语气强硬，会用反问和施压表达不满；只有具体的方案和时间点能让你缓和。"
    return "你处于爆发边缘，随时可能公开投诉或直接退游，除非客服立刻展现出认真处理的态度。"


def build_player_system(level_id: str, emotion: int) -> str:
    level = LEVELS_BY_ID[level_id]
    persona = PERSONAS[level["persona_id"]]
    return f"""你是「{persona['name']}」，{persona['title']}，正在与游戏 {GAME_NAME} 的在线客服沟通。

【情景】
{level['scene']}

【你的身份与处境】
{persona['background']}

【你的性格】
{persona['personality']}
说话风格：{persona['speech_style']}

【当前情绪】{emotion}/10
{emotion_guidance(emotion)}

【你会如何反应】
- 如果客服敷衍、推诿、复制模板、把责任推给你：{persona['escalation']} 你的情绪会上升。
- 如果客服真诚回应、核实信息、给出具体动作和时间点：{persona['deescalation']} 你的情绪会下降。

【扮演规则（必须遵守）】
1. 你就是玩家本人，绝不承认自己是 AI、模型、机器人，也不要提到“演练”“培训”“评分”。
2. 用 1-3 句中文口语回复，像真实玩家在客服窗口打字；可以有语气词，不要写括号动作或旁白。
3. 不要主动替客服解决问题，不要突然变得通情达理；你的态度必须由客服的话决定。
4. 可以质疑、追问、施压，但不要辱骂、不要脏话。
5. 一次只推进一个诉求，像个真实玩家一样抓住你在意的点不放。
6. 只输出你要说的话，不要任何前缀、标题或解释。
"""


def build_player_messages(level_id: str, emotion: int, history: list[dict]) -> list[dict[str, str]]:
    """history 为数据库消息（role=trainee/player），映射为 Ollama 的 user/assistant。"""
    messages: list[dict[str, str]] = [{"role": "system", "content": build_player_system(level_id, emotion)}]
    for msg in history:
        if msg["role"] == "trainee":
            messages.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "player":
            messages.append({"role": "assistant", "content": msg["content"]})
    return messages


def build_opening_messages(level_id: str) -> list[dict[str, str]]:
    """以客服标准问候开局，让 AI 玩家先说话。"""
    return [
        {"role": "system", "content": build_player_system(level_id, _emotion_start(level_id))},
        {"role": "user", "content": "您好，很高兴为您服务，请问有什么可以帮您？"},
    ]


def _emotion_start(level_id: str) -> int:
    persona = PERSONAS[LEVELS_BY_ID[level_id]["persona_id"]]
    return int(persona["emotion_start"])


def fallback_opening(level_id: str, seed: str = "") -> str:
    persona = PERSONAS[LEVELS_BY_ID[level_id]["persona_id"]]
    openers: list[str] = persona["openers"]
    idx = _stable_index(seed, len(openers))
    return openers[idx]


def fallback_player_reply(level_id: str, emotion: int, last_text: str, turn: int) -> str:
    persona = PERSONAS[LEVELS_BY_ID[level_id]["persona_id"]]
    pool = persona["fallback"][emotion_band(emotion)]
    idx = (_stable_index(last_text, len(pool)) + turn) % len(pool)
    return pool[idx]


def _stable_index(text: str, size: int) -> int:
    if size <= 1:
        return 0
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % size


def format_transcript(messages: Iterable[dict], max_chars: int = 6000) -> str:
    lines: list[str] = []
    for msg in messages:
        if msg["role"] not in ("trainee", "player"):
            continue
        speaker = TRAINEE_ROLE_LABEL if msg["role"] == "trainee" else PLAYER_ROLE_LABEL
        lines.append(f"{speaker}：{msg['content']}")
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = "（前文略）\n" + text[-max_chars:]
    return text


def build_judge_messages(
    level_id: str,
    messages: list[dict],
    rule_report: dict,
    knowledge: list[dict],
) -> list[dict[str, str]]:
    level = LEVELS_BY_ID[level_id]
    persona = PERSONAS[level["persona_id"]]
    objectives = level["objectives"]
    objectives_text = "\n".join(
        f"- {o['label']}（权重 {o['weight']}）：{o['hint']}" for o in objectives
    )
    knowledge_text = "\n\n".join(f"《{d['title']}》\n{d['content']}" for d in knowledge)
    rule_text = (
        f"规则引擎初判：总分 {rule_report['total']}，"
        f"共情 {rule_report['dimensions']['empathy']}，"
        f"SOP {rule_report['dimensions']['sop']}，"
        f"情绪稳定 {rule_report['dimensions']['emotional']}，"
        f"合规 {rule_report['dimensions']['compliance']}，"
        f"首响 {rule_report['dimensions']['efficiency']}；\n"
        f"已达成目标：{', '.join(rule_report.get('objectives_met_labels') or []) or '无'}；\n"
        f"触发忌语：{', '.join(rule_report.get('forbidden_hits') or []) or '无'}；\n"
        f"越权承诺：{', '.join(rule_report.get('over_promise_hits') or []) or '无'}；\n"
        f"平均首响 {rule_report.get('avg_latency_s', 0)} 秒。"
    )
    system = """你是游戏客服培训中心的资深质检教练，负责对一次客服实训进行多维度评分。

评分要求：
1. 严格但公平。分数只反映客服在本局中的表现，不受玩家情绪影响。
2. 共情不是堆砌“抱歉”，而是先承认玩家的体验损失，再给出动作。
3. SOP 执行率看是否完成了本关要求的全部关键动作，尤其不能漏掉核实与闭环。
4. 情绪稳定度看客服是否被玩家带节奏、是否出现忌语或对抗性表达。
5. 合规与专业看是否存在越权承诺（如“保证退款/百分百到账”）、是否守住规则边界、事实是否与知识库一致。
6. 参照规则引擎初判，但不要简单复读；如果你认为规则判断有偏差，可以修正。
7. 规则报告中“已达成目标”由本关关键词与流程匹配客观得出，视为已经完成。你可以指出执行深度、细节或顺序上的不足，但不得把已达成目标判定为“未完成、漏掉、缺失、跳过”。
8. 只输出一个 JSON 对象，不要 Markdown、不要额外文字。

JSON 格式：
{"empathy": 0-100 的整数, "sop": 0-100 的整数, "emotional": 0-100 的整数, "compliance": 0-100 的整数,
 "feedback": ["最多 5 条具体改进建议，中文，每条不超过 40 字"],
 "strengths": ["最多 3 条做得好的地方，中文"],
 "summary": "一句 30 字以内的总评"}
"""
    user = f"""【关卡】{level['name']} · {level['subtitle']}（{level['difficulty']}）
【场景】{level['scene']}
【玩家画像】{persona['name']}（{persona['title']}），{persona['personality']}

【本关必须完成的 SOP 目标】
{objectives_text}

【企业知识库（事实依据）】
{knowledge_text}

【完整对话记录】
{format_transcript(messages)}

【{rule_text}】

请输出评分 JSON。"""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
