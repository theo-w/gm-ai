"""FastAPI 入口：挂载 API 与前端静态资源。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import router
from .config import WEB_DIR
from .engines.llm import llm
from .seed import ensure_seeded


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_seeded()
    await llm.probe()
    yield
    await llm.close()


app = FastAPI(
    title="GameMaster AI",
    description="AI 游戏化企业培训与实战陪练系统",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# 前端为免构建的单页应用，直接由服务端托管
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
