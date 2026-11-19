# -*- coding: utf-8 -*-
"""pytest 配置：把项目根目录加入 sys.path，保证能 import agent 包。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
