"""本地大模型适配层（Ollama）。

设计要点：
- 只依赖 Ollama 的 /api/chat 与 /api/tags，可直接换成任何 OpenAI 兼容网关；
- 模型不可用时返回 ok=False，由上层降级到模板引擎，保证演示永不“白屏”；
- keep_alive 让 27B 模型在演示期间常驻显存，首响可稳定在 2 秒内。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_PREFERRED, LLM_TIMEOUT_S


@dataclass
class LLMResult:
    text: str
    ok: bool
    model: str = ""
    latency_ms: int = 0
    prompt_tokens: int = 0
    eval_tokens: int = 0
    error: str = ""


@dataclass
class LLMService:
    base_url: str = OLLAMA_BASE_URL
    model: str = ""
    available: bool = False
    last_error: str = ""
    models: list[str] = field(default_factory=list)
    _client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url.rstrip("/"),
                timeout=httpx.Timeout(LLM_TIMEOUT_S, connect=5.0),
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def probe(self) -> dict[str, Any]:
        """读取本地模型列表并选定对话模型。"""
        try:
            client = await self._get_client()
            resp = await client.get("/api/tags", timeout=5.0)
            resp.raise_for_status()
            tags = resp.json().get("models", [])
            names = [m.get("name", "") for m in tags if m.get("name")]
            self.models = names
            picked = ""
            if OLLAMA_MODEL:
                picked = OLLAMA_MODEL
            else:
                for pref in OLLAMA_PREFERRED:
                    if pref in names:
                        picked = pref
                        break
                if not picked:
                    for name in names:
                        low = name.lower()
                        if "embed" not in low and "rerank" not in low:
                            picked = name
                            break
            if not picked:
                self.available = False
                self.last_error = "未发现可用本地模型，请先执行 `ollama pull qwen2.5:7b`"
                return self.health()
            self.model = picked
            self.available = True
            self.last_error = ""
        except Exception as exc:  # 网络异常 / 服务未启动
            self.available = False
            self.last_error = f"无法连接 Ollama：{exc.__class__.__name__}"
        return self.health()

    def health(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "model": self.model,
            "base_url": self.base_url,
            "models": self.models,
            "error": self.last_error,
        }

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.85,
        num_predict: int = 220,
        json_mode: bool = False,
        think: bool = False,
    ) -> LLMResult:
        started = time.perf_counter()
        if not self.available:
            await self.probe()
            if not self.available:
                return LLMResult(text="", ok=False, error=self.last_error)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": think,
            "keep_alive": "30m",
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
                "top_p": 0.9,
                "repeat_penalty": 1.08,
            },
        }
        if json_mode:
            payload["format"] = "json"

        try:
            client = await self._get_client()
            resp = await client.post("/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            text = (data.get("message", {}) or {}).get("content", "") or ""
            latency_ms = int((time.perf_counter() - started) * 1000)
            self.last_error = "" if text.strip() else "模型返回空内容"
            return LLMResult(
                text=text.strip(),
                ok=bool(text.strip()),
                model=self.model,
                latency_ms=latency_ms,
                prompt_tokens=int(data.get("prompt_eval_count") or 0),
                eval_tokens=int(data.get("eval_count") or 0),
                error=self.last_error,
            )
        except Exception as exc:
            self.last_error = f"生成失败：{exc.__class__.__name__}"
            self.available = False
            return LLMResult(
                text="",
                ok=False,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=self.last_error,
            )


llm = LLMService()


def extract_json(raw: str) -> dict[str, Any] | None:
    """从模型输出中提取第一个 JSON 对象（兼容代码块与前后废话）。"""
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None
