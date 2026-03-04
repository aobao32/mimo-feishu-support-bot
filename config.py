"""MiMo 飞书 Agent 配置管理模块。

集中管理非敏感配置项（模型参数、路径、超时时间等），
敏感配置从环境变量读取。
"""

import os
from pathlib import Path

# ── 项目路径 ─────────────────────────────────────────────────────────────────

# 项目根目录（mimo-feishu-agent/）
_PROJECT_DIR = Path(__file__).parent

# ── 模型配置 ─────────────────────────────────────────────────────────────────

MIMO_BASE_URL: str = "https://api.xiaomimimo.com/v1"
MIMO_MODEL_ID: str = "mimo-v2-flash"
MIMO_MAX_TOKENS: int = 4096
MIMO_TEMPERATURE: float = 0.3

# ── 路径配置 ──────────────────────────────────────────────────────────────────

PROMPT_FILE: str = str(_PROJECT_DIR / "prompts" / "kiro_agent_prompt.md")
KB_DIR: str = str(_PROJECT_DIR / "knowledge_base")

# ── Agent 管理配置 ───────────────────────────────────────────────────────────

AGENT_TTL_SECONDS: int = 48 * 3600  # 48小时不活跃移除

# ── 日志配置 ─────────────────────────────────────────────────────────────────

ENABLE_FILE_LOG: bool = True
LOG_DIR: str = "logs"

# ── 敏感配置（从环境变量读取，不硬编码）─────────────────────────────────────

MIMO_API_KEY: str = os.environ.get("MIMO_API_KEY", "")
APP_ID: str = os.environ.get("APP_ID", "")
APP_SECRET: str = os.environ.get("APP_SECRET", "")
