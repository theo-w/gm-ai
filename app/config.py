"""全局配置：环境变量优先，未设置时使用适合本地演示的默认值。"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.getenv("GM_DB_PATH", str(DATA_DIR / "gamemaster.db")))

# 本地大模型（Ollama）配置
OLLAMA_BASE_URL = os.getenv("GM_OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("GM_OLLAMA_MODEL", "")  # 留空时自动从本地模型中选择
OLLAMA_PREFERRED = ["qwen3.8:27b-mlx", "qwen3:27b", "qwen2.5:14b", "qwen2.5:7b", "llama3.1:8b"]
LLM_TIMEOUT_S = float(os.getenv("GM_LLM_TIMEOUT", "120"))
LLM_TEMPERATURE = float(os.getenv("GM_LLM_TEMPERATURE", "0.85"))
JUDGE_TEMPERATURE = 0.15
JUDGE_MAX_TOKENS = 600

# 演示默认租户与产品信息
DEFAULT_TENANT = os.getenv("GM_TENANT", "starsea")
GAME_NAME = os.getenv("GM_GAME_NAME", "《星海纪元》")
PASS_SCORE = 80
MAX_TURNS = 10

# ROI 测算假设（可由看板前端调整，这里作为服务端默认基线）
MENTOR_HOURLY_CNY = float(os.getenv("GM_MENTOR_HOURLY", "120"))
OJT_MINUTES_PER_RUN = float(os.getenv("GM_OJT_MINUTES", "25"))

RANK_TIERS = [
    {"key": "bronze", "name": "青铜", "min_xp": 0, "color": "#B08D57"},
    {"key": "silver", "name": "白银", "min_xp": 300, "color": "#9FB3C8"},
    {"key": "gold", "name": "黄金", "min_xp": 700, "color": "#F3C969"},
    {"key": "platinum", "name": "铂金", "min_xp": 1200, "color": "#7FE7D5"},
    {"key": "diamond", "name": "星耀", "min_xp": 1800, "color": "#8CA7FF"},
    {"key": "king", "name": "王者", "min_xp": 2600, "color": "#FF7AC3"},
]

SCORE_DIMENSIONS = [
    {"key": "empathy", "label": "共情能力", "weight": 0.20},
    {"key": "sop", "label": "SOP 执行率", "weight": 0.35},
    {"key": "emotional", "label": "情绪稳定度", "weight": 0.20},
    {"key": "compliance", "label": "合规与专业", "weight": 0.15},
    {"key": "efficiency", "label": "首响效率", "weight": 0.10},
]
