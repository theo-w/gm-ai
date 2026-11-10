"""演示数据种子：一个租户、六名学员、四十条历史训练记录。

历史数据仅用于让管理驾驶舱在首次启动时就有可分析的样本，
真实训练产生的记录会与之自然叠加（`is_seed` 字段可区分）。
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone

from .config import DEFAULT_TENANT, GAME_NAME, SCORE_DIMENSIONS
from .content.levels import LEVELS, LEVELS_BY_ID
from .db import db

PROFILES = [
    {
        "id": "t_linxiaoman",
        "name": "林小满",
        "avatar": "🦊",
        "created_days_ago": 26,
        "plan": [
            ("bronze-1", True, 88, 14),
            ("bronze-2", True, 84, 18),
            ("silver-1", False, 76, 36),
            ("silver-1", True, 86, 21),
            ("silver-2", True, 85, 24),
            ("gold-1", True, 82, 22),
            ("gold-2", True, 88, 19),
            ("platinum-1", False, 78, 29),
        ],
    },
    {
        "id": "t_zhouyue",
        "name": "周玥",
        "avatar": "🐰",
        "created_days_ago": 27,
        "plan": [
            ("bronze-1", True, 92, 9),
            ("bronze-2", True, 90, 11),
            ("silver-1", True, 89, 12),
            ("silver-2", True, 88, 15),
            ("gold-1", True, 91, 10),
            ("gold-2", True, 87, 14),
            ("platinum-1", True, 90, 15),
            ("king-1", False, 79, 23),
            ("king-1", True, 93, 18),
        ],
    },
    {
        "id": "t_chenyiming",
        "name": "陈一鸣",
        "avatar": "🐯",
        "created_days_ago": 24,
        "plan": [
            ("bronze-1", True, 83, 19),
            ("bronze-2", True, 81, 23),
            ("silver-1", False, 74, 42),
            ("silver-1", True, 82, 27),
            ("silver-2", True, 83, 25),
            ("gold-1", False, 72, 48),
            ("gold-1", False, 76, 39),
        ],
    },
    {
        "id": "t_hejiashu",
        "name": "何嘉树",
        "avatar": "🐼",
        "created_days_ago": 20,
        "plan": [
            ("bronze-1", True, 82, 26),
            ("bronze-2", True, 80, 30),
            ("silver-1", True, 81, 28),
            ("silver-2", False, 71, 52),
            ("silver-2", False, 75, 44),
        ],
    },
    {
        "id": "t_shenzhiwei",
        "name": "沈知微",
        "avatar": "🦉",
        "created_days_ago": 25,
        "plan": [
            ("bronze-1", True, 86, 16),
            ("bronze-2", True, 87, 15),
            ("silver-1", True, 83, 22),
            ("silver-2", True, 81, 31),
            ("gold-1", True, 84, 24),
            ("gold-2", False, 77, 33),
        ],
    },
    {
        "id": "t_suxiao",
        "name": "苏晓",
        "avatar": "🐱",
        "created_days_ago": 18,
        "plan": [
            ("bronze-1", True, 85, 21),
            ("bronze-2", False, 72, 46),
            ("bronze-2", True, 80, 34),
            ("silver-1", False, 68, 58),
            ("silver-1", False, 74, 41),
        ],
    },
]


def _clamp(value: int, low: int = 45, high: int = 99) -> int:
    return max(low, min(high, int(value)))


def _latency_dim(seconds: float) -> int:
    if seconds <= 8:
        return 100
    if seconds <= 15:
        return 95
    if seconds <= 25:
        return 88
    if seconds <= 40:
        return 78
    if seconds <= 60:
        return 66
    return 55


def _make_dimensions(target: int, latency_s: float, passed: bool, rng: random.Random) -> tuple[dict, int]:
    dims = {
        "empathy": _clamp(target + rng.randint(-5, 6)),
        "sop": _clamp(target + rng.randint(-4, 7)),
        "emotional": _clamp(target + rng.randint(-4, 7)),
        "compliance": _clamp(target + rng.randint(-8, 4)),
        "efficiency": _latency_dim(latency_s),
    }
    weights = {d["key"]: d["weight"] for d in SCORE_DIMENSIONS}
    total = int(round(sum(dims[k] * w for k, w in weights.items())))

    # 保证历史记录的通关状态与分数自洽
    if passed and total < 82:
        bump = 82 - total
        dims["sop"] = _clamp(dims["sop"] + bump + 2)
        dims["empathy"] = _clamp(dims["empathy"] + bump)
        total = int(round(sum(dims[k] * w for k, w in weights.items())))
    if not passed and total >= 80:
        drop = total - 77
        dims["compliance"] = _clamp(dims["compliance"] - drop, 40, 99)
        dims["emotional"] = _clamp(dims["emotional"] - drop, 40, 99)
        total = int(round(sum(dims[k] * w for k, w in weights.items())))
    return dims, min(99, total)


def _grade(total: int) -> str:
    if total >= 95:
        return "S"
    if total >= 88:
        return "A"
    if total >= 80:
        return "B"
    if total >= 65:
        return "C"
    return "D"


def ensure_seeded() -> bool:
    """首次启动时写入演示租户与历史数据；已存在则跳过。"""
    existing = db.one("SELECT id FROM tenants WHERE id=?", (DEFAULT_TENANT,))
    if existing:
        return False

    now = datetime.now(timezone.utc)
    db.execute(
        "INSERT INTO tenants (id, name, plan, created_at) VALUES (?,?,?,?)",
        (DEFAULT_TENANT, "星海互娱", "enterprise-trial", (now - timedelta(days=30)).isoformat()),
    )

    rng = random.Random(20261110)

    for p_idx, profile in enumerate(PROFILES):
        trainee_xp = 0
        plan = profile["plan"]
        n = len(plan)
        for i, (level_id, passed, target, latency_s) in enumerate(plan):
            level = LEVELS_BY_ID[level_id]
            dims, total = _make_dimensions(target, latency_s, passed, rng)
            if passed:
                trainee_xp += int(round(level["xp"] * (total / 100) * 1.5))
            else:
                trainee_xp += int(round(level["xp"] * 0.25))

            day_offset = 20 - i * (19 / max(1, n - 1))
            hour = 10 + (i * 2 + p_idx * 3) % 12
            minute = (i * 7 + p_idx * 5) % 60
            started = (now - timedelta(days=day_offset)).replace(
                hour=hour, minute=minute, second=rng.randint(0, 59), microsecond=0
            )
            duration_s = rng.randint(4, 10) * 60
            finished = started + timedelta(seconds=duration_s)

            dimensions = [
                {
                    "key": spec["key"],
                    "label": spec["label"],
                    "weight": spec["weight"],
                    "score": dims[spec["key"]],
                    "rule_score": dims[spec["key"]],
                    "judge_score": None,
                }
                for spec in SCORE_DIMENSIONS
            ]
            scores = {
                "total": total,
                "passed": passed,
                "grade": _grade(total),
                "dimensions": dimensions,
                "objectives": [],
                "feedback": ["该记录为演示用的历史训练数据，仅用于看板分析。"],
                "strengths": [],
                "summary": (
                    f"历史训练：{level['name']}，{'通过' if passed else '未通过'}，"
                    f"平均首响 {latency_s} 秒。"
                ),
                "judge_available": False,
                "avg_latency_s": latency_s,
                "max_latency_s": latency_s + rng.randint(5, 20),
                "turns": rng.randint(3, 6),
                "hints_used": rng.randint(0, 2),
                "hint_penalty": 0,
                "forbidden_hits": [],
                "over_promise_hits": [],
                "duration_s": duration_s,
                "seeded": True,
            }
            run_id = f"seed-{profile['id'].replace('t_', '')}-{i + 1:02d}"
            db.execute(
                "INSERT INTO runs (id, tenant_id, trainee_id, level_id, status, started_at, finished_at, "
                "turn_count, total_score, passed, scores_json, judge_json, hints_used, xp_awarded, "
                "avg_latency_ms, emotion, last_player_at, is_seed) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
                (
                    run_id, DEFAULT_TENANT, profile["id"], level_id,
                    "passed" if passed else "failed",
                    started.isoformat(), finished.isoformat(),
                    scores["turns"], total, 1 if passed else 0,
                    json.dumps(scores, ensure_ascii=False), None,
                    scores["hints_used"], int(round(level["xp"] * 0.25)),
                    latency_s * 1000, 5, finished.isoformat(),
                ),
            )

        db.execute(
            "INSERT INTO trainees (id, tenant_id, name, avatar, created_at, xp, is_seed) "
            "VALUES (?,?,?,?,?,?,1)",
            (
                profile["id"], DEFAULT_TENANT, profile["name"], profile["avatar"],
                (now - timedelta(days=profile["created_days_ago"])).isoformat(),
                trainee_xp,
            ),
        )

    return True
