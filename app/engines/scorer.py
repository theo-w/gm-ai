"""多维度智能评分引擎。

混合评分：规则引擎负责可解释的硬指标（SOP 覆盖、忌语、承诺边界、
首响时长），大模型教练负责语义层面的判断。最终分按 40% 规则 + 60% AI
加权；模型不可用时自动退化为纯规则分，并在结果页标注。

维度权重与 SDD 一致：共情 20% / SOP 35% / 情绪稳定 20% / 合规 15% / 首响 10%。
"""

from __future__ import annotations

from typing import Any, Iterable

from ..config import SCORE_DIMENSIONS, PASS_SCORE
from ..content.lexicon import (
    APOLOGY_WORDS, EMPATHY_WORDS, COURTESY_WORDS, FORBIDDEN_PHRASES,
    OVER_PROMISE_PHRASES, NEGATIVE_TONE_WORDS, SERVICE_ACTIONS, ESCALATION_WORDS,
    hits,
)
from .llm import extract_json

EMPATHY_OBJECTIVE_KEYS = {"empathy", "acknowledge", "calm"}
COMPLIANCE_OBJECTIVE_KEYS = {"boundary", "policy", "official"}


def analyze_turn(text: str, level: dict, matched_keys: set[str]) -> dict[str, Any]:
    """对单条学员回复做规则分析（不调用模型，毫秒级返回）。"""
    text = text.strip()
    new_objectives: list[str] = []
    objective_hits: dict[str, list[str]] = {}

    for obj in level["objectives"]:
        if obj["key"] in matched_keys:
            continue
        words = hits(text, obj["keywords"])
        if words:
            new_objectives.append(obj["key"])
            objective_hits[obj["key"]] = words

    return {
        "new_objectives": new_objectives,
        "objective_hits": objective_hits,
        "apology": hits(text, APOLOGY_WORDS),
        "empathy_terms": hits(text, EMPATHY_WORDS),
        "courtesy_terms": hits(text, COURTESY_WORDS),
        "service_actions": hits(text, SERVICE_ACTIONS),
        "escalation_terms": hits(text, ESCALATION_WORDS),
        "forbidden": hits(text, FORBIDDEN_PHRASES),
        "over_promise": hits(text, OVER_PROMISE_PHRASES),
        "negative_terms": hits(text, NEGATIVE_TONE_WORDS),
        "length": len(text),
    }


def next_emotion(current: int, analysis: dict[str, Any], turn: int) -> int:
    """根据学员本回合表现调整 AI 玩家情绪（1–10）。"""
    delta = 0
    if analysis["forbidden"]:
        delta += 2
    if analysis["over_promise"]:
        delta += 1
    if analysis["apology"] or analysis["empathy_terms"]:
        delta -= 1
    if analysis["service_actions"] or analysis["escalation_terms"]:
        delta -= 1
    if analysis["new_objectives"]:
        delta -= 1
    if len(analysis["new_objectives"]) >= 2:
        delta -= 1
    if analysis["length"] < 12 and not analysis["empathy_terms"]:
        delta += 1
    if (
        not analysis["new_objectives"]
        and not analysis["empathy_terms"]
        and not analysis["service_actions"]
        and analysis["length"] < 50
    ):
        delta += 1
    delta = max(-3, min(2, delta))
    return max(1, min(10, int(current) + delta))


def _latency_score(avg_seconds: float) -> int:
    if avg_seconds <= 8:
        return 100
    if avg_seconds <= 15:
        return 95
    if avg_seconds <= 25:
        return 88
    if avg_seconds <= 40:
        return 78
    if avg_seconds <= 60:
        return 66
    if avg_seconds <= 90:
        return 55
    return 45


def build_rule_report(
    level: dict,
    analyses: list[dict[str, Any]],
    latencies_ms: list[float],
    hints_used: int = 0,
) -> dict[str, Any]:
    """汇总整局规则分与证据。"""
    matched_keys: set[str] = set()
    hit_words: dict[str, list[str]] = {}
    forbidden: list[str] = []
    over_promise: list[str] = []
    negative: list[str] = []
    empathy_terms: list[str] = []
    apology: list[str] = []
    courtesy: list[str] = []
    service_actions: list[str] = []
    escalation: list[str] = []
    short_messages = 0

    for a in analyses:
        matched_keys.update(a.get("new_objectives", []))
        for key, words in (a.get("objective_hits") or {}).items():
            existing = hit_words.setdefault(key, [])
            for w in words:
                if w not in existing:
                    existing.append(w)
        for bucket, source in (
            (forbidden, "forbidden"),
            (over_promise, "over_promise"),
            (negative, "negative_terms"),
            (empathy_terms, "empathy_terms"),
            (apology, "apology"),
            (courtesy, "courtesy_terms"),
            (service_actions, "service_actions"),
            (escalation, "escalation_terms"),
        ):
            for w in a.get(source, []):
                if w not in bucket:
                    bucket.append(w)
        if a.get("length", 0) < 10:
            short_messages += 1

    objectives = []
    sop_score = 0.0
    met_labels: list[str] = []
    for obj in level["objectives"]:
        met = obj["key"] in matched_keys
        if met:
            sop_score += obj["weight"]
            met_labels.append(obj["label"])
        objectives.append({
            "key": obj["key"],
            "label": obj["label"],
            "weight": obj["weight"],
            "met": met,
            "hit_words": hit_words.get(obj["key"], [])[:6],
        })

    # 共情
    empathy_related = EMPATHY_OBJECTIVE_KEYS & matched_keys
    empathy_score = 30
    if empathy_related:
        empathy_score += 34
    if apology:
        empathy_score += 12
    if len(empathy_terms) >= 2:
        empathy_score += 10
    if len(empathy_terms) >= 4:
        empathy_score += 6
    if service_actions:
        empathy_score += 8
    if len(courtesy) >= 2:
        empathy_score += 6
    empathy_score -= 18 * len(forbidden)
    empathy_score -= 4 * len(negative)
    empathy_score = max(0, min(100, empathy_score))

    # 情绪稳定
    emotional_score = 100 - 16 * len(forbidden) - 4 * len(negative)
    if forbidden:
        emotional_score = min(emotional_score, 72)
    emotional_score = max(0, min(100, emotional_score))

    # 合规与专业
    compliance_score = 78
    if COMPLIANCE_OBJECTIVE_KEYS & matched_keys:
        compliance_score += 10
    if not forbidden and not over_promise:
        compliance_score += 10
    compliance_score -= 18 * len(over_promise)
    compliance_score -= 8 * len(forbidden)
    compliance_score = max(0, min(100, compliance_score))

    # 首响效率
    avg_ms = sum(latencies_ms) / len(latencies_ms) if latencies_ms else 0
    avg_seconds = round(avg_ms / 1000, 1)
    efficiency_score = _latency_score(avg_seconds) if latencies_ms else 0
    if short_messages:
        efficiency_score -= min(20, short_messages * 6)
    efficiency_score = max(0, min(100, efficiency_score))

    dims = {
        "empathy": int(round(empathy_score)),
        "sop": int(round(sop_score)),
        "emotional": int(round(emotional_score)),
        "compliance": int(round(compliance_score)),
        "efficiency": int(round(efficiency_score)),
    }

    hint_penalty = min(6, max(0, hints_used) * 2)
    raw_total = sum(d * next(w["weight"] for w in SCORE_DIMENSIONS if w["key"] == k) for k, d in dims.items())
    total = max(0, min(100, int(round(raw_total)) - hint_penalty))
    if len(analyses) < 2:
        total = min(total, 68)

    return {
        "dimensions": dims,
        "total": total,
        "raw_total": int(round(raw_total)),
        "hint_penalty": hint_penalty,
        "hints_used": hints_used,
        "objectives": objectives,
        "objectives_met_labels": met_labels,
        "forbidden_hits": forbidden,
        "over_promise_hits": over_promise,
        "negative_hits": negative,
        "apology_hits": apology[:4],
        "empathy_hits": empathy_terms[:6],
        "service_action_hits": service_actions[:6],
        "escalation_hits": escalation[:4],
        "avg_latency_s": avg_seconds,
        "max_latency_s": round(max(latencies_ms) / 1000, 1) if latencies_ms else 0,
        "messages": len(analyses),
        "short_messages": short_messages,
        "judge_available": False,
    }


_JUDGE_ALIASES = {
    "empathy": ["empathy", "共情", "共情能力", "empathy_score"],
    "sop": ["sop", "SOP", "SOP执行率", "sop_score", "process"],
    "emotional": ["emotional", "emotional_control", "情绪稳定", "情绪稳定度", "emotion"],
    "compliance": ["compliance", "合规", "合规与专业", "professional", "compliance_score"],
}


def _as_score(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return max(0, min(100, int(round(float(value)))))
    if isinstance(value, str):
        clean = value.strip().replace("分", "").replace("%", "")
        try:
            return max(0, min(100, int(round(float(clean)))))
        except ValueError:
            return None
    return None


def parse_judge(raw: str) -> dict[str, Any] | None:
    obj = extract_json(raw)
    if not obj:
        return None
    scores: dict[str, int] = {}
    for key, aliases in _JUDGE_ALIASES.items():
        for alias in aliases:
            if alias in obj:
                value = _as_score(obj[alias])
                if value is not None:
                    scores[key] = value
                    break
    if len(scores) < 3:
        return None

    feedback = [str(x).strip() for x in (obj.get("feedback") or []) if str(x).strip()]
    strengths = [str(x).strip() for x in (obj.get("strengths") or []) if str(x).strip()]
    summary = str(obj.get("summary") or "").strip()
    return {
        "scores": scores,
        "feedback": feedback[:5],
        "strengths": strengths[:3],
        "summary": summary[:60],
    }


def blend_scores(rule_report: dict[str, Any], judge: dict[str, Any] | None) -> dict[str, Any]:
    """规则 40% + AI 教练 60%；AI 缺席时取纯规则分。"""
    rule_dims: dict[str, int] = rule_report["dimensions"]
    judge_scores = (judge or {}).get("scores", {})
    final_dims: list[dict[str, Any]] = []
    weighted = 0.0

    for spec in SCORE_DIMENSIONS:
        key = spec["key"]
        rule_score = rule_dims[key]
        judge_score = judge_scores.get(key) if key != "efficiency" else None
        if judge_score is not None:
            score = int(round(rule_score * 0.4 + judge_score * 0.6))
        else:
            score = rule_score
        weighted += score * spec["weight"]
        final_dims.append({
            "key": key,
            "label": spec["label"],
            "weight": spec["weight"],
            "score": score,
            "rule_score": rule_score,
            "judge_score": judge_score,
        })

    total = max(0, min(100, int(round(weighted)))) - rule_report.get("hint_penalty", 0)
    total = max(0, min(100, total))
    passed = total >= PASS_SCORE and rule_report.get("messages", 0) >= 2
    return {
        "dimensions": final_dims,
        "total": total,
        "passed": passed,
        "grade": grade_for(total),
        "judge_available": judge is not None,
    }


def grade_for(total: int) -> str:
    if total >= 95:
        return "S"
    if total >= 88:
        return "A"
    if total >= 80:
        return "B"
    if total >= 65:
        return "C"
    return "D"


def compose_feedback(
    level: dict,
    rule_report: dict[str, Any],
    judge: dict[str, Any] | None,
    total: int,
    passed: bool,
) -> tuple[list[str], list[str], str]:
    feedback: list[str] = []
    strengths: list[str] = []

    for obj in rule_report["objectives"]:
        hint = next(o["hint"] for o in level["objectives"] if o["key"] == obj["key"])
        if not obj["met"]:
            feedback.append(f"未完成「{obj['label']}」：{hint}")
        else:
            strengths.append(f"「{obj['label']}」动作到位")

    if rule_report["forbidden_hits"]:
        feedback.append("出现服务忌语（" + "、".join(rule_report["forbidden_hits"][:3]) + "），情绪稳定度被明显扣分。")
    if rule_report["over_promise_hits"]:
        feedback.append("存在越权承诺（" + "、".join(rule_report["over_promise_hits"][:3]) + "），合规风险较高。")
    if rule_report["avg_latency_s"] > 40:
        feedback.append(f"平均首响 {rule_report['avg_latency_s']} 秒，超过 40 秒的回合会让玩家感觉被冷落。")
    if rule_report["short_messages"]:
        feedback.append("部分回复过短，先确认玩家诉求再给出动作，避免只有一个“好的”。")
    if rule_report["hint_penalty"]:
        feedback.append(f"本局使用了 {rule_report['hints_used']} 次提示，总分扣减 {rule_report['hint_penalty']} 分。")

    # 规则已判定完成的目标，不允许 AI 点评反向宣称“漏做/未完成”，避免自相矛盾
    all_targets_met = (
        len(rule_report["objectives_met_labels"]) == len(level["objectives"])
        and len(level["objectives"]) > 0
    )
    contradiction_words = ("未完成", "未执行", "漏掉", "遗漏", "缺失", "未覆盖", "跳过", "没有完成", "未做", "未进行")

    if judge:
        judge_feedback = judge.get("feedback", [])
        if all_targets_met:
            judge_feedback = [
                item for item in judge_feedback
                if not any(word in item for word in contradiction_words)
            ]
        feedback.extend(judge_feedback)
        strengths.extend(judge.get("strengths", []))

    # 去重并限制条数
    def _dedupe(items: Iterable[str], limit: int) -> list[str]:
        out: list[str] = []
        for item in items:
            item = item.strip()
            if item and item not in out:
                out.append(item)
        return out[:limit]

    feedback = _dedupe(feedback, 6)
    strengths = _dedupe(strengths, 4)
    if not feedback:
        feedback = ["本局表现完整，可以尝试挑战更高难度关卡。"]

    met = len(rule_report["objectives_met_labels"])
    total_obj = len(level["objectives"])
    summary = (
        f"本局 {total} 分（{grade_for(total)}），规则命中 {met}/{total_obj} 个 SOP 关键点，"
        f"平均首响 {rule_report['avg_latency_s']} 秒。"
    )
    if judge and judge.get("summary"):
        judge_summary = str(judge["summary"]).strip()
        if all_targets_met and any(word in judge_summary for word in contradiction_words):
            judge_summary = "关键 SOP 已覆盖，执行细节与颗粒度仍有提升空间。"
        summary += judge_summary
    return feedback, strengths, summary
