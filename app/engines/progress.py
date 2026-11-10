"""段位、关卡解锁、徽章与个人成长数据。"""

from __future__ import annotations

import json
from typing import Any

from ..config import RANK_TIERS, SCORE_DIMENSIONS
from ..db import db
from ..content.levels import LEVELS, level_public

BADGE_DEFS = [
    {"key": "first_pass", "icon": "🚩", "name": "首战告捷", "desc": "第一次通过任意关卡"},
    {"key": "bronze_clear", "icon": "🥉", "name": "青出于蓝", "desc": "通关青铜训练营全部关卡"},
    {"key": "empathy_master", "icon": "💗", "name": "共情大师", "desc": "任意一局共情维度 ≥ 95"},
    {"key": "speed_demon", "icon": "⚡", "name": "疾风之刃", "desc": "平均首响 ≤ 8 秒并通过关卡"},
    {"key": "perfect", "icon": "💎", "name": "满分教官", "desc": "任意一局总分 ≥ 95"},
    {"key": "all_clear", "icon": "👑", "name": "通关王者", "desc": "通关全部 8 个关卡"},
]


def rank_info(xp: int) -> dict[str, Any]:
    idx = 0
    for i, tier in enumerate(RANK_TIERS):
        if xp >= tier["min_xp"]:
            idx = i
    current = RANK_TIERS[idx]
    nxt = RANK_TIERS[idx + 1] if idx + 1 < len(RANK_TIERS) else None
    if nxt:
        span = max(1, nxt["min_xp"] - current["min_xp"])
        progress = (xp - current["min_xp"]) / span
        next_xp = nxt["min_xp"]
        next_name = nxt["name"]
    else:
        progress = 1.0
        next_xp = None
        next_name = None
    return {
        "key": current["key"],
        "name": current["name"],
        "color": current["color"],
        "min_xp": current["min_xp"],
        "xp": xp,
        "next_name": next_name,
        "next_xp": next_xp,
        "progress": round(max(0.0, min(1.0, progress)) * 100),
        "tier_index": idx + 1,
        "tier_total": len(RANK_TIERS),
    }


def xp_award(level: dict, total: int, passed: bool) -> int:
    base = level["xp"]
    if passed:
        return int(round(base * (total / 100) * 1.5))
    return int(round(base * 0.25))


def _finish_rows(trainee_id: str, tenant_id: str) -> list[dict]:
    return db.all(
        "SELECT * FROM runs WHERE trainee_id=? AND tenant_id=? "
        "AND status IN ('passed','failed') ORDER BY finished_at ASC",
        (trainee_id, tenant_id),
    )


def _parse_scores(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw) or {}
    except (json.JSONDecodeError, TypeError):
        return {}


def level_states(trainee_id: str, tenant_id: str) -> list[dict[str, Any]]:
    rows = db.all(
        "SELECT level_id, COUNT(*) AS attempts, "
        "SUM(CASE WHEN status='passed' THEN 1 ELSE 0 END) AS passes, "
        "MAX(total_score) AS best_score, "
        "MAX(CASE WHEN status='passed' THEN total_score END) AS best_pass_score "
        "FROM runs WHERE trainee_id=? AND tenant_id=? AND status IN ('passed','failed') "
        "GROUP BY level_id",
        (trainee_id, tenant_id),
    )
    by_level = {r["level_id"]: r for r in rows}

    states: list[dict[str, Any]] = []
    prev_passed = True
    for level in LEVELS:
        row = by_level.get(level["id"], {})
        attempts = int(row.get("attempts") or 0)
        passes = int(row.get("passes") or 0)
        best = row.get("best_score")
        passed = passes > 0
        unlocked = prev_passed
        public = level_public(level)
        states.append({
            **public,
            "unlocked": unlocked,
            "passed": passed,
            "attempts": attempts,
            "passes": passes,
            "best_score": int(round(best)) if best is not None else None,
            "persona_public": None,  # 由 API 层补充
        })
        prev_passed = passed
    return states


def earned_badges(finished_runs: list[dict], states: list[dict]) -> list[dict[str, Any]]:
    earned: dict[str, bool] = {b["key"]: False for b in BADGE_DEFS}
    for run in finished_runs:
        scores = _parse_scores(run.get("scores_json"))
        if run["status"] == "passed":
            earned["first_pass"] = True
            if (run.get("avg_latency_ms") or 999999) <= 8000:
                earned["speed_demon"] = True
            if (run.get("total_score") or 0) >= 95:
                earned["perfect"] = True
        for dim in scores.get("dimensions", []):
            if dim.get("key") == "empathy" and dim.get("score", 0) >= 95:
                earned["empathy_master"] = True
    bronze_ids = {"bronze-1", "bronze-2"}
    bronze_passed = {s["id"] for s in states if s["passed"]} & bronze_ids
    if len(bronze_passed) == len(bronze_ids):
        earned["bronze_clear"] = True
    if all(s["passed"] for s in states):
        earned["all_clear"] = True
    return [{**b, "earned": earned[b["key"]]} for b in BADGE_DEFS]


def trainee_stats(finished_runs: list[dict], states: list[dict]) -> dict[str, Any]:
    scored = [r for r in finished_runs if r.get("total_score") is not None]
    latencies = [r["avg_latency_ms"] for r in finished_runs if r.get("avg_latency_ms")]
    return {
        "attempts": len(finished_runs),
        "passed_runs": sum(1 for r in finished_runs if r["status"] == "passed"),
        "levels_passed": sum(1 for s in states if s["passed"]),
        "levels_total": len(states),
        "avg_score": round(sum(r["total_score"] for r in scored) / len(scored), 1) if scored else 0,
        "best_score": max([r["total_score"] for r in scored], default=0),
        "avg_latency_s": round(sum(latencies) / len(latencies) / 1000, 1) if latencies else 0,
        "best_latency_s": round(min(latencies) / 1000, 1) if latencies else 0,
        "hints_used": sum(int(r.get("hints_used") or 0) for r in finished_runs),
    }


def build_progress(trainee: dict) -> dict[str, Any]:
    tenant_id = trainee["tenant_id"]
    finished = _finish_rows(trainee["id"], tenant_id)
    states = level_states(trainee["id"], tenant_id)
    for state in states:
        from ..content.personas import persona_public
        state["persona_public"] = persona_public(state["persona_id"])
        state.pop("persona_id", None)
    xp = int(trainee.get("xp") or 0)
    return {
        "trainee": {
            "id": trainee["id"],
            "name": trainee["name"],
            "avatar": trainee["avatar"],
            "xp": xp,
            "tenant_id": tenant_id,
        },
        "rank": rank_info(xp),
        "levels": states,
        "badges": earned_badges(finished, states),
        "stats": trainee_stats(finished, states),
        "recent_runs": _recent_runs(trainee["id"], tenant_id),
    }


def _recent_runs(trainee_id: str, tenant_id: str, limit: int = 6) -> list[dict[str, Any]]:
    rows = db.all(
        "SELECT * FROM runs WHERE trainee_id=? AND tenant_id=? "
        "AND status IN ('passed','failed') ORDER BY finished_at DESC LIMIT ?",
        (trainee_id, tenant_id, limit),
    )
    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "level_id": r["level_id"],
            "status": r["status"],
            "total_score": int(round(r["total_score"])) if r["total_score"] is not None else None,
            "finished_at": r["finished_at"],
            "avg_latency_s": round((r.get("avg_latency_ms") or 0) / 1000, 1),
        })
    return out
