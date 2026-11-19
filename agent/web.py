# -*- coding: utf-8 -*-
"""启动 Streamlit Web 界面：python -m agent.web

端口默认 8502（可用环境变量 ABAQUS_AGENT_PORT 覆盖）。
显式打开静态资源服务：网页浮窗里的 three.js 走 /app/static/，避免每次重渲染重传 1.3 MB。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    app = Path(__file__).resolve().parent / "webapp.py"
    port = os.environ.get("ABAQUS_AGENT_PORT", "8502")
    # 用相对路径 + cwd=项目根：Streamlit 按 app 文件所在目录找 static/，
    # 传绝对路径会让它去 agent/static 找，导致 /app/static/three_bundle.js 404。
    return subprocess.run(
        [
            sys.executable, "-m", "streamlit", "run", str(app.relative_to(root)),
            "--server.headless", "true",
            "--server.port", port,
            "--server.enableStaticServing", "true",
            "--browser.gatherUsageStats", "false",
        ],
        cwd=str(root),
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
