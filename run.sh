#!/usr/bin/env bash
# 一键启动：自动创建虚拟环境、安装依赖、拉起本地服务
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "→ 创建 Python 3.12 虚拟环境"
  uv venv --python 3.12 .venv
fi

if ! .venv/bin/python -c "import fastapi, uvicorn, httpx" >/dev/null 2>&1; then
  echo "→ 安装依赖"
  uv pip install --python .venv/bin/python -r requirements.txt
fi

echo "→ GameMaster AI 启动中： http://127.0.0.1:8787"
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8787
