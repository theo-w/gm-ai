"""HTTP API：训练、对练、结算与管理看板。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from . import __version__
from .config import (
    PASS_SCORE, MAX_TURNS, GAME_NAME, DEFAULT_TENANT, SCORE_DIMENSIONS,
    RANK_TIERS, MENTOR_HOURLY_CNY, OJT_MINUTES_PER_RUN,
)
from .content.levels import LEVELS, LEVELS_BY_ID, level_public, next_level_of
from .content.personas import PERSONAS, persona_public
from .db import db, new_id, now_iso
from .engines import prompts, scorer
from .engines.llm import llm
from .engines.progress import (
    build_progress, level_states, rank_info, xp_award,
)
from .engines.retriever import docs_for_ids, search_docs

router = APIRouter(prefix="/api")


# ---------- 请求体 ----------

class TraineeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=20)


class RunCreate(BaseModel):
    trainee_id: str
    level_id: str


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=500)


# ---------- 工具 ----------

AVATARS = ["🦊", "🐰", "🐯", "🐼", "🦉", "🐱", "🐸", "🐨", "🦄", "🐺", "🐧", "🦖"]


def _tenant(x_tenant: str | None) -> dict:
    tenant_id = (x_tenant or DEFAULT_TENANT).strip()
    row = db.one("SELECT * FROM tenants WHERE id=?", (tenant_id,))
    if not row:
        raise HTTPException(status_code=404, detail="租户不存在")
    return row


def _trainee_or_404(trainee_id: str, tenant_id: str) -> dict:
    row = db.one(
        "SELECT * FROM trainees WHERE id=? AND tenant_id=?",
        (trainee_id, tenant_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="学员不存在")
    return row


def _level_or_404(level_id: str) -> dict:
    level = LEVELS_BY_ID.get(level_id)
    if not level:
        raise HTTPException(status_code=404, detail="关卡不存在")
    return level


def _run_or_404(run_id: str, tenant_id: str) -> dict:
    row = db.one("SELECT * FROM runs WHERE id=? AND tenant_id=?", (run_id, tenant_id))
    if not row:
        raise HTTPException(status_code=404, detail="训练记录不存在")
    return row


def _parse_json(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _transcript(run_id: str) -> list[dict]:
    rows = db.all(
        "SELECT id, role, content, created_at, latency_ms, analysis_json, seq "
        "FROM messages WHERE run_id=? ORDER BY seq ASC",
        (run_id,),
    )
    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "role": r["role"],
            "content": r["content"],
            "created_at": r["created_at"],
            "latency_ms": r["latency_ms"],
            "analysis": _parse_json(r["analysis_json"]),
            "seq": r["seq"],
        })
    return out


def _matched_keys(transcript: list[dict]) -> set[str]:
    keys: set[str] = set()
    for msg in transcript:
        analysis = msg.get("analysis") or {}
        keys.update(analysis.get("new_objectives") or [])
    return keys


def _live_objectives(level: dict, transcript: list[dict]) -> list[dict]:
    matched = _matched_keys(transcript)
    return [
        {
            "key": o["key"],
            "label": o["label"],
            "weight": o["weight"],
            "met": o["key"] in matched,
        }
        for o in level["objectives"]
    ]


def _next_seq(run_id: str) -> int:
    row = db.one("SELECT COALESCE(MAX(seq),0)+1 AS n FROM messages WHERE run_id=?", (run_id,))
    return int(row["n"]) if row else 1


def _next_hint(level: dict, transcript: list[dict]) -> dict | None:
    matched = _matched_keys(transcript)
    for obj in level["objectives"]:
        if obj["key"] not in matched:
            return {"key": obj["key"], "label": obj["label"], "hint": obj["hint"]}
    return None


def _clean_player_text(text: str) -> str:
    text = text.strip()
    for prefix in ("玩家：", "玩家:", "用户：", "用户:", "顾客：", "顾客:"):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    if len(text) >= 2 and text[0] in "“\"「" and text[-1] in "”\"」":
        text = text[1:-1].strip()
    return text[:400].strip()


def _run_payload(run: dict) -> dict:
    level = _level_or_404(run["level_id"])
    trainee = _trainee_or_404(run["trainee_id"], run["tenant_id"])
    persona = PERSONAS[level["persona_id"]]
    transcript = _transcript(run["id"])
    result = _parse_json(run.get("scores_json"))
    return {
        "run": {
            "id": run["id"],
            "level_id": run["level_id"],
            "trainee_id": run["trainee_id"],
            "status": run["status"],
            "started_at": run["started_at"],
            "finished_at": run["finished_at"],
            "turn_count": run["turn_count"],
            "emotion": run["emotion"],
            "emotion_max": 10,
            "hints_used": run["hints_used"],
            "avg_latency_ms": run["avg_latency_ms"],
            "is_seed": bool(run.get("is_seed")),
        },
        "trainee": {
            "id": trainee["id"], "name": trainee["name"],
            "avatar": trainee["avatar"], "xp": trainee["xp"],
        },
        "level": {
            **level_public(level),
            "knowledge": docs_for_ids(level["knowledge_ids"]),
            "max_turns": MAX_TURNS,
        },
        "persona": persona_public(persona["id"]),
        "transcript": transcript,
        "objectives": _live_objectives(level, transcript),
        "result": result,
        "ai": llm.health(),
    }


# ---------- 基础信息 ----------

@router.get("/health")
async def health() -> dict:
    return {
        "ok": True,
        "version": __version__,
        "llm": llm.health(),
        "db": str(db.path),
        "pass_score": PASS_SCORE,
        "max_turns": MAX_TURNS,
    }


@router.get("/meta")
async def meta(x_tenant: str | None = Header(default=None, alias="X-Tenant")) -> dict:
    tenant = _tenant(x_tenant)
    return {
        "product": {
            "name": "GameMaster AI",
            "tagline": "AI 游戏化企业培训与实战陪练系统",
            "game": GAME_NAME,
            "version": __version__,
        },
        "tenant": {"id": tenant["id"], "name": tenant["name"], "plan": tenant["plan"]},
        "tenants": db.all("SELECT id, name, plan FROM tenants ORDER BY created_at ASC"),
        "personas": [persona_public(pid) for pid in PERSONAS],
        "levels": [
            {**level_public(lv), "knowledge": docs_for_ids(lv["knowledge_ids"])}
            for lv in LEVELS
        ],
        "ranks": RANK_TIERS,
        "dimensions": SCORE_DIMENSIONS,
        "pass_score": PASS_SCORE,
        "max_turns": MAX_TURNS,
        "llm": llm.health(),
    }


# ---------- 学员 ----------

@router.get("/trainees")
async def list_trainees(x_tenant: str | None = Header(default=None, alias="X-Tenant")) -> dict:
    tenant = _tenant(x_tenant)
    rows = db.all(
        "SELECT * FROM trainees WHERE tenant_id=? ORDER BY xp DESC, created_at ASC",
        (tenant["id"],),
    )
    out = []
    for row in rows:
        rank = rank_info(int(row["xp"] or 0))
        out.append({
            "id": row["id"], "name": row["name"], "avatar": row["avatar"],
            "xp": row["xp"], "rank": rank["name"], "rank_color": rank["color"],
            "is_seed": bool(row["is_seed"]),
        })
    return {"trainees": out}


@router.post("/trainees")
async def create_trainee(
    body: TraineeCreate,
    x_tenant: str | None = Header(default=None, alias="X-Tenant"),
) -> dict:
    tenant = _tenant(x_tenant)
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="请输入学员昵称")
    count = db.count("SELECT COUNT(*) FROM trainees WHERE tenant_id=?", (tenant["id"],))
    trainee_id = new_id("t_")
    avatar = AVATARS[count % len(AVATARS)]
    db.execute(
        "INSERT INTO trainees (id, tenant_id, name, avatar, created_at, xp, is_seed) "
        "VALUES (?,?,?,?,?,0,0)",
        (trainee_id, tenant["id"], name, avatar, now_iso()),
    )
    row = _trainee_or_404(trainee_id, tenant["id"])
    return {
        "trainee": {
            "id": row["id"], "name": row["name"], "avatar": row["avatar"],
            "xp": 0, "tenant_id": tenant["id"],
        },
        "progress": build_progress(row),
    }


@router.get("/trainees/{trainee_id}/progress")
async def trainee_progress(
    trainee_id: str,
    x_tenant: str | None = Header(default=None, alias="X-Tenant"),
) -> dict:
    tenant = _tenant(x_tenant)
    trainee = _trainee_or_404(trainee_id, tenant["id"])
    return build_progress(trainee)


# ---------- 知识库 ----------

@router.get("/knowledge/search")
async def knowledge_search(q: str = "", limit: int = 3) -> dict:
    q = q.strip()
    if not q:
        return {"results": []}
    return {"query": q, "results": search_docs(q, limit=min(6, max(1, limit)))}


# ---------- 对练 ----------

@router.post("/runs")
async def create_run(
    body: RunCreate,
    x_tenant: str | None = Header(default=None, alias="X-Tenant"),
) -> dict:
    tenant = _tenant(x_tenant)
    _trainee_or_404(body.trainee_id, tenant["id"])
    level = _level_or_404(body.level_id)

    state = next(
        (s for s in level_states(body.trainee_id, tenant["id"]) if s["id"] == level["id"]),
        None,
    )
    if state is None or not state["unlocked"]:
        raise HTTPException(status_code=403, detail="请先通过前置关卡，再挑战本关")

    run_id = new_id("r_")
    persona = PERSONAS[level["persona_id"]]
    started_at = now_iso()
    db.execute(
        "INSERT INTO runs (id, tenant_id, trainee_id, level_id, status, started_at, "
        "turn_count, hints_used, emotion, is_seed) VALUES (?,?,?,?,?,?,0,0,?,0)",
        (run_id, tenant["id"], body.trainee_id, level["id"], "active", started_at, persona["emotion_start"]),
    )

    seq = 1
    db.execute(
        "INSERT INTO messages (run_id, role, content, created_at, seq) VALUES (?,?,?,?,?)",
        (run_id, "system", "客服通道已接入 · 演练开始", started_at, seq),
    )
    seq += 1

    opening = await llm.chat(
        prompts.build_opening_messages(level["id"]),
        temperature=0.9,
        num_predict=120,
    )
    if opening.ok:
        player_text = _clean_player_text(opening.text)
        fallback = False
    else:
        player_text = ""
    if not player_text:
        player_text = prompts.fallback_opening(level["id"], seed=run_id)
        fallback = True

    player_at = now_iso()
    db.execute(
        "INSERT INTO messages (run_id, role, content, created_at, seq) VALUES (?,?,?,?,?)",
        (run_id, "player", player_text, player_at, seq),
    )
    db.execute("UPDATE runs SET last_player_at=? WHERE id=?", (player_at, run_id))

    run = _run_or_404(run_id, tenant["id"])
    payload = _run_payload(run)
    payload["ai_fallback"] = fallback
    payload["ai_latency_ms"] = opening.latency_ms
    return payload


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    x_tenant: str | None = Header(default=None, alias="X-Tenant"),
) -> dict:
    tenant = _tenant(x_tenant)
    run = _run_or_404(run_id, tenant["id"])
    return _run_payload(run)


@router.post("/runs/{run_id}/messages")
async def send_message(
    run_id: str,
    body: MessageIn,
    x_tenant: str | None = Header(default=None, alias="X-Tenant"),
) -> dict:
    tenant = _tenant(x_tenant)
    run = _run_or_404(run_id, tenant["id"])
    if run["status"] != "active":
        raise HTTPException(status_code=400, detail="本局已结束，请开始新的对练")
    if run["turn_count"] >= MAX_TURNS:
        raise HTTPException(status_code=400, detail=f"本局已达 {MAX_TURNS} 回合上限，请结束对练结算")

    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="回复不能为空")

    level = _level_or_404(run["level_id"])
    transcript = _transcript(run_id)
    matched = _matched_keys(transcript)
    analysis = scorer.analyze_turn(content, level, matched)

    last_player = db.one(
        "SELECT created_at FROM messages WHERE run_id=? AND role='player' "
        "ORDER BY seq DESC LIMIT 1",
        (run_id,),
    )
    ref_time = last_player["created_at"] if last_player else run["started_at"]
    try:
        ref_dt = datetime.fromisoformat(ref_time)
        latency_ms = max(0, int((datetime.now(timezone.utc) - ref_dt).total_seconds() * 1000))
    except (ValueError, TypeError):
        latency_ms = None

    seq = _next_seq(run_id)
    db.execute(
        "INSERT INTO messages (run_id, role, content, created_at, latency_ms, analysis_json, seq) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            run_id, "trainee", content, now_iso(), latency_ms,
            json.dumps(analysis, ensure_ascii=False), seq,
        ),
    )

    current_emotion = int(run["emotion"] or PERSONAS[level["persona_id"]]["emotion_start"])
    new_emotion = scorer.next_emotion(current_emotion, analysis, int(run["turn_count"]) + 1)

    history = _transcript(run_id)
    ai_result = await llm.chat(
        prompts.build_player_messages(level["id"], new_emotion, history),
        temperature=0.85,
        num_predict=180,
    )
    reply = _clean_player_text(ai_result.text) if ai_result.ok else ""
    if not reply:
        reply = prompts.fallback_player_reply(
            level["id"], new_emotion, content, int(run["turn_count"]) + 1
        )
        ai_fallback = True
    else:
        ai_fallback = False

    player_at = now_iso()
    db.execute(
        "INSERT INTO messages (run_id, role, content, created_at, seq) VALUES (?,?,?,?,?)",
        (run_id, "player", reply, player_at, seq + 1),
    )
    db.execute(
        "UPDATE runs SET turn_count=turn_count+1, emotion=?, last_player_at=? WHERE id=?",
        (new_emotion, player_at, run_id),
    )

    new_run = _run_or_404(run_id, tenant["id"])
    payload = _run_payload(new_run)
    new_labels = [
        o["label"] for o in level["objectives"] if o["key"] in analysis["new_objectives"]
    ]
    payload["turn"] = {
        "analysis": analysis,
        "new_objectives": [
            {"key": k, "label": next(o["label"] for o in level["objectives"] if o["key"] == k)}
            for k in analysis["new_objectives"]
        ],
        "new_labels": new_labels,
        "emotion": new_emotion,
        "emotion_delta": new_emotion - current_emotion,
        "latency_ms": latency_ms,
        "ai_latency_ms": ai_result.latency_ms,
        "ai_fallback": ai_fallback,
        "turn_count": int(new_run["turn_count"]),
    }
    return payload


@router.post("/runs/{run_id}/hint")
async def request_hint(
    run_id: str,
    x_tenant: str | None = Header(default=None, alias="X-Tenant"),
) -> dict:
    tenant = _tenant(x_tenant)
    run = _run_or_404(run_id, tenant["id"])
    if run["status"] != "active":
        raise HTTPException(status_code=400, detail="本局已结束")
    level = _level_or_404(run["level_id"])
    transcript = _transcript(run_id)
    hint = _next_hint(level, transcript)
    if hint is None:
        return {
            "hint": None,
            "message": "全部 SOP 目标已完成，可以结束对练查看评分。",
            "hints_used": run["hints_used"],
        }
    if int(run["hints_used"]) >= 5:
        return {
            "hint": None,
            "message": "本局提示次数已用完，试着自己复盘一下。",
            "hints_used": run["hints_used"],
        }
    db.execute("UPDATE runs SET hints_used=hints_used+1 WHERE id=?", (run_id,))
    updated = _run_or_404(run_id, tenant["id"])
    return {
        "hint": hint,
        "message": f"下一个目标：{hint['label']}",
        "hints_used": updated["hints_used"],
        "penalty_per_hint": 2,
    }


@router.post("/runs/{run_id}/finish")
async def finish_run(
    run_id: str,
    x_tenant: str | None = Header(default=None, alias="X-Tenant"),
) -> dict:
    tenant = _tenant(x_tenant)
    run = _run_or_404(run_id, tenant["id"])
    if run["status"] != "active":
        raise HTTPException(status_code=400, detail="本局已结算，无需重复提交")
    level = _level_or_404(run["level_id"])
    trainee = _trainee_or_404(run["trainee_id"], tenant["id"])
    transcript = _transcript(run_id)

    trainee_msgs = [m for m in transcript if m["role"] == "trainee"]
    if not trainee_msgs:
        raise HTTPException(status_code=400, detail="至少完成一次回复后才能结算")

    analyses = [m["analysis"] for m in trainee_msgs if m["analysis"]]
    latencies = [m["latency_ms"] for m in trainee_msgs if m["latency_ms"] is not None]
    rule_report = scorer.build_rule_report(
        level, analyses, latencies, hints_used=int(run["hints_used"] or 0)
    )

    knowledge = docs_for_ids(level["knowledge_ids"])
    judge = None
    judge_error = ""
    judge_result = await llm.chat(
        prompts.build_judge_messages(level["id"], transcript, rule_report, knowledge),
        temperature=0.15,
        num_predict=500,
        json_mode=True,
    )
    if judge_result.ok:
        judge = scorer.parse_judge(judge_result.text)
        if judge is None:
            judge_error = "AI 教练返回格式异常，已使用纯规则评分"
    else:
        judge_error = judge_result.error or "AI 教练不可用，已使用纯规则评分"

    blended = scorer.blend_scores(rule_report, judge)
    feedback, strengths, summary = scorer.compose_feedback(
        level, rule_report, judge, blended["total"], blended["passed"]
    )

    awarded = xp_award(level, blended["total"], blended["passed"])
    before_progress = build_progress(trainee)
    rank_before = before_progress["rank"]

    finished_at = now_iso()
    avg_latency_ms = (sum(latencies) / len(latencies)) if latencies else None
    try:
        duration_s = int(
            (datetime.fromisoformat(finished_at) - datetime.fromisoformat(run["started_at"])).total_seconds()
        )
    except (ValueError, TypeError):
        duration_s = 0

    scores: dict[str, Any] = {
        "total": blended["total"],
        "passed": blended["passed"],
        "grade": blended["grade"],
        "dimensions": blended["dimensions"],
        "objectives": rule_report["objectives"],
        "feedback": feedback,
        "strengths": strengths,
        "summary": summary,
        "judge_available": blended["judge_available"],
        "judge_error": judge_error,
        "judge_summary": (judge or {}).get("summary", ""),
        "avg_latency_s": rule_report["avg_latency_s"],
        "max_latency_s": rule_report["max_latency_s"],
        "turns": rule_report["messages"],
        "hints_used": rule_report["hints_used"],
        "hint_penalty": rule_report["hint_penalty"],
        "forbidden_hits": rule_report["forbidden_hits"],
        "over_promise_hits": rule_report["over_promise_hits"],
        "duration_s": duration_s,
        "rule_total": rule_report["total"],
        "xp_awarded": awarded,
        "seeded": False,
    }

    db.execute(
        "UPDATE runs SET status=?, finished_at=?, total_score=?, passed=?, scores_json=?, "
        "judge_json=?, avg_latency_ms=? WHERE id=?",
        (
            "passed" if blended["passed"] else "failed",
            finished_at, blended["total"], 1 if blended["passed"] else 0,
            json.dumps(scores, ensure_ascii=False),
            json.dumps(judge, ensure_ascii=False) if judge else None,
            avg_latency_ms, run_id,
        ),
    )
    db.execute("UPDATE trainees SET xp=xp+? WHERE id=?", (awarded, trainee["id"]))

    updated_trainee = _trainee_or_404(trainee["id"], tenant["id"])
    after_progress = build_progress(updated_trainee)
    rank_after = after_progress["rank"]
    rank_up = rank_after["key"] != rank_before["key"]

    earned_before = {b["key"] for b in before_progress["badges"] if b["earned"]}
    earned_after = [b for b in after_progress["badges"] if b["earned"]]
    badges_new = [b for b in earned_after if b["key"] not in earned_before]

    next_level = next_level_of(level["id"]) if blended["passed"] else None
    before_states = {s["id"]: s for s in before_progress["levels"]}
    newly_unlocked = None
    if next_level and not before_states.get(next_level["id"], {}).get("unlocked"):
        newly_unlocked = next_level
    scores["rank_before"] = rank_before
    scores["rank_after"] = rank_after
    scores["rank_up"] = rank_up
    scores["badges_new"] = badges_new
    scores["unlocked_level"] = level_public(newly_unlocked) if newly_unlocked else None
    scores["next_level"] = level_public(next_level) if next_level else None
    scores["trainee"] = {
        "id": updated_trainee["id"], "name": updated_trainee["name"],
        "avatar": updated_trainee["avatar"], "xp": updated_trainee["xp"],
    }
    db.execute(
        "UPDATE runs SET scores_json=? WHERE id=?",
        (json.dumps(scores, ensure_ascii=False), run_id),
    )

    new_run = _run_or_404(run_id, tenant["id"])
    payload = _run_payload(new_run)
    payload["meta"] = {
        "xp_awarded": awarded,
        "rank_before": rank_before,
        "rank_after": rank_after,
        "rank_up": rank_up,
        "badges_new": badges_new,
        "unlocked_level": level_public(newly_unlocked) if newly_unlocked else None,
        "next_level": level_public(next_level) if next_level else None,
    }
    return payload


# ---------- 管理后台 ----------

@router.get("/admin/overview")
async def admin_overview(x_tenant: str | None = Header(default=None, alias="X-Tenant")) -> dict:
    tenant = _tenant(x_tenant)
    tid = tenant["id"]

    trainees = db.all(
        "SELECT * FROM trainees WHERE tenant_id=? ORDER BY xp DESC", (tid,)
    )
    runs = db.all(
        "SELECT r.*, t.name AS trainee_name, t.avatar AS trainee_avatar "
        "FROM runs r JOIN trainees t ON t.id=r.trainee_id "
        "WHERE r.tenant_id=? AND r.status IN ('passed','failed') "
        "ORDER BY r.finished_at DESC",
        (tid,),
    )

    finished = len(runs)
    passed = sum(1 for r in runs if r["status"] == "passed")
    scores = [r["total_score"] for r in runs if r["total_score"] is not None]
    latencies = [r["avg_latency_ms"] for r in runs if r["avg_latency_ms"]]
    seeded = sum(1 for r in runs if r.get("is_seed"))

    dim_accum: dict[str, list[float]] = {d["key"]: [] for d in SCORE_DIMENSIONS}
    for r in runs:
        scores_json = _parse_json(r.get("scores_json")) or {}
        for dim in scores_json.get("dimensions", []):
            if dim.get("key") in dim_accum and dim.get("score") is not None:
                dim_accum[dim["key"]].append(float(dim["score"]))

    radar = [
        {
            "key": spec["key"],
            "label": spec["label"],
            "weight": spec["weight"],
            "value": round(sum(dim_accum[spec["key"]]) / len(dim_accum[spec["key"]]), 1)
            if dim_accum[spec["key"]] else 0,
        }
        for spec in SCORE_DIMENSIONS
    ]
    weak = sorted(radar, key=lambda d: d["value"])[:3]
    for w in weak:
        w["gap"] = round(100 - w["value"], 1)

    # 14 天趋势
    today = datetime.now(timezone.utc).date()
    buckets: dict[str, dict] = {}
    for i in range(13, -1, -1):
        day = (today - timedelta(days=i)).isoformat()
        buckets[day] = {"date": day, "runs": 0, "passed": 0, "avg_score": 0, "sum": 0}
    for r in runs:
        if not r.get("finished_at"):
            continue
        day = r["finished_at"][:10]
        if day in buckets:
            b = buckets[day]
            b["runs"] += 1
            b["passed"] += 1 if r["status"] == "passed" else 0
            if r["total_score"] is not None:
                b["sum"] += r["total_score"]
    trend = []
    for day in sorted(buckets):
        b = buckets[day]
        trend.append({
            "date": day,
            "runs": b["runs"],
            "passed": b["passed"],
            "avg_score": round(b["sum"] / b["runs"], 1) if b["runs"] else 0,
            "pass_rate": round(b["passed"] / b["runs"], 3) if b["runs"] else 0,
        })

    # 关卡分布
    level_dist = []
    for level in LEVELS:
        subset = [r for r in runs if r["level_id"] == level["id"]]
        lv_scores = [r["total_score"] for r in subset if r["total_score"] is not None]
        lv_passed = sum(1 for r in subset if r["status"] == "passed")
        level_dist.append({
            "level_id": level["id"],
            "name": level["name"],
            "tier": level["tier"],
            "difficulty": level["difficulty"],
            "attempts": len(subset),
            "passes": lv_passed,
            "pass_rate": round(lv_passed / len(subset), 3) if subset else 0,
            "avg_score": round(sum(lv_scores) / len(lv_scores), 1) if lv_scores else 0,
        })

    # 学员榜
    leaderboard = []
    for t in trainees:
        t_runs = [r for r in runs if r["trainee_id"] == t["id"]]
        t_scores = [r["total_score"] for r in t_runs if r["total_score"] is not None]
        states = level_states(t["id"], tid)
        leaderboard.append({
            "id": t["id"],
            "name": t["name"],
            "avatar": t["avatar"],
            "xp": t["xp"],
            "rank": rank_info(int(t["xp"] or 0))["name"],
            "rank_color": rank_info(int(t["xp"] or 0))["color"],
            "runs": len(t_runs),
            "passed_levels": sum(1 for s in states if s["passed"]),
            "avg_score": round(sum(t_scores) / len(t_scores), 1) if t_scores else 0,
        })

    recent = []
    for r in runs[:12]:
        recent.append({
            "id": r["id"],
            "trainee_name": r["trainee_name"],
            "trainee_avatar": r["trainee_avatar"],
            "level_id": r["level_id"],
            "level_name": LEVELS_BY_ID.get(r["level_id"], {}).get("name", r["level_id"]),
            "status": r["status"],
            "total_score": int(round(r["total_score"])) if r["total_score"] is not None else None,
            "avg_latency_s": round((r.get("avg_latency_ms") or 0) / 1000, 1),
            "finished_at": r["finished_at"],
            "is_seed": bool(r.get("is_seed")),
        })

    hours_saved = finished * OJT_MINUTES_PER_RUN / 60
    cost_saved = hours_saved * MENTOR_HOURLY_CNY
    return {
        "tenant": {"id": tenant["id"], "name": tenant["name"], "plan": tenant["plan"]},
        "generated_at": now_iso(),
        "kpis": {
            "trainees": len(trainees),
            "runs": finished,
            "pass_rate": round(passed / finished, 3) if finished else 0,
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "avg_latency_s": round(sum(latencies) / len(latencies) / 1000, 1) if latencies else 0,
            "hours_saved": round(hours_saved, 1),
            "cost_saved_cny": int(round(cost_saved)),
            "seeded_runs": seeded,
        },
        "radar": radar,
        "weak": weak,
        "trend": trend,
        "level_distribution": level_dist,
        "leaderboard": leaderboard,
        "recent_runs": recent,
        "roi": {
            "assumptions": {
                "mentor_hourly_cny": MENTOR_HOURLY_CNY,
                "ojt_minutes_per_run": OJT_MINUTES_PER_RUN,
                "onboarding_days_saved": 9,
                "new_hire_count": max(1, len(trainees)),
            },
            "formula": "节省金额 = 训练局数 × 每局替代带教分钟 ÷ 60 × 带教时薪",
            "hours_saved": round(hours_saved, 1),
            "cost_saved_cny": int(round(cost_saved)),
        },
    }
