"""轻量知识检索：字符 bigram + 标签加权的 lexical retriever。

真实企业接入时，把 search_docs 换成向量库（如 pgvector / Milvus）即可，
上层接口与返回结构保持不变。
"""

from __future__ import annotations

import re

from ..content.knowledge import KNOWLEDGE_DOCS, DOCS_BY_ID

_TOKEN_RE = re.compile(r"[一-鿿]+|[a-zA-Z0-9]+")
_PUNCT_RE = re.compile(r"[^一-鿿A-Za-z0-9]+")


def _normalize(text: str) -> str:
    return _PUNCT_RE.sub("", text.lower())


def _bigrams(text: str) -> set[str]:
    norm = _normalize(text)
    grams: set[str] = set()
    for token in _TOKEN_RE.findall(text):
        low = token.lower()
        if re.fullmatch(r"[a-z0-9]+", low):
            if len(low) >= 2:
                grams.add(low)
            continue
        for i in range(len(low) - 1):
            grams.add(low[i : i + 2])
    return grams


def search_docs(query: str, limit: int = 3) -> list[dict]:
    """按相关性返回知识文档，附命中说明。"""
    q = _normalize(query)
    q_grams = _bigrams(query)
    scored: list[tuple[float, dict]] = []
    for doc in KNOWLEDGE_DOCS:
        score = 0.0
        for tag in doc["tags"]:
            if tag and tag in query:
                score += 6.0
        for tag in doc["tags"]:
            if tag and tag in q:
                score += 3.0
        title_norm = _normalize(doc["title"])
        if title_norm and title_norm in q:
            score += 10.0
        doc_grams = _bigrams(doc["title"] + doc["content"])
        overlap = len(q_grams & doc_grams)
        score += overlap * 0.7
        if score > 0:
            scored.append((score, doc))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "id": doc["id"],
            "title": doc["title"],
            "content": doc["content"],
            "tags": doc["tags"],
            "score": round(score, 1),
        }
        for score, doc in scored[:limit]
    ]


def docs_for_ids(ids: list[str]) -> list[dict]:
    return [
        {
            "id": DOCS_BY_ID[i]["id"],
            "title": DOCS_BY_ID[i]["title"],
            "content": DOCS_BY_ID[i]["content"],
            "tags": DOCS_BY_ID[i]["tags"],
        }
        for i in ids
        if i in DOCS_BY_ID
    ]
