"""Agent 服务模块。

管理每个用户的 Strands Agent 实例，全异步接口。
使用 OpenAIModel 连接 MiMo-V2-Flash 模型。
"""

import asyncio
import sys
import time
from dataclasses import dataclass, field

from strands import Agent
from strands.agent.conversation_manager import SummarizingConversationManager
from strands.models.openai import OpenAIModel

from config import (
    AGENT_TTL_SECONDS,
    MIMO_API_KEY,
    MIMO_BASE_URL,
    MIMO_MAX_TOKENS,
    MIMO_MODEL_ID,
    MIMO_TEMPERATURE,
    PROMPT_FILE,
)
from kb_tool import read_kb_file
from web_tools import fetch_kiro_docs, search_github_issues
from logger import get_logger

logger = get_logger(__name__)


@dataclass
class UserAgentState:
    """用户 Agent 状态，包含 Agent 实例、最后活跃时间和并发锁。"""

    agent: Agent
    last_active: float
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class AgentService:
    """管理每个用户的 Strands Agent 实例，全异步接口。"""

    def __init__(self) -> None:
        # 检查 API Key
        if not MIMO_API_KEY:
            logger.error("环境变量 MIMO_API_KEY 未设置，请先配置后再启动。")
            sys.exit(1)

        # 创建 MiMo 模型提供者
        self._model = OpenAIModel(
            model_id=MIMO_MODEL_ID,
            client_args={
                "api_key": MIMO_API_KEY,
                "base_url": MIMO_BASE_URL,
            },
            params={
                "max_tokens": MIMO_MAX_TOKENS,
                "temperature": MIMO_TEMPERATURE,
                "extra_body": {"thinking": {"type": "disabled"}},
            },
        )

        # 加载 System Prompt
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            self._system_prompt = f.read()
        logger.info("System Prompt 已加载: %s", PROMPT_FILE)

        # 用户 Agent 字典
        self._agents: dict[str, UserAgentState] = {}

        # 全局锁，保护 _agents 字典的并发访问
        self._global_lock = asyncio.Lock()

        logger.info("AgentService 初始化完成，模型: %s", MIMO_MODEL_ID)

    async def get_or_create_agent(self, user_id: str) -> Agent:
        """获取或创建用户的 Agent 实例（异步锁保护）。"""
        async with self._global_lock:
            if user_id in self._agents:
                self._agents[user_id].last_active = time.time()
                logger.info("复用已有 Agent: user_id=%s", user_id)
                return self._agents[user_id].agent

            agent = Agent(
                model=self._model,
                system_prompt=self._system_prompt,
                tools=[read_kb_file, fetch_kiro_docs, search_github_issues],
                conversation_manager=SummarizingConversationManager(),
            )
            self._agents[user_id] = UserAgentState(
                agent=agent,
                last_active=time.time(),
            )
            logger.info("创建新 Agent: user_id=%s", user_id)
            return agent

    async def ask(self, user_id: str, message: str) -> str:
        """向指定用户的 Agent 发送消息并返回回复文本。"""
        start_time = time.time()
        msg_summary = message[:50]
        try:
            agent = await self.get_or_create_agent(user_id)
            user_lock = self._agents[user_id].lock

            async with user_lock:
                result = await asyncio.to_thread(agent, message)

            # 优先从 message content 中提取纯文本 block
            reply = self._extract_reply(result)
            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(
                "用户消息处理完成: user_id=%s, 消息摘要='%s', 耗时=%.1fms",
                user_id,
                msg_summary,
                elapsed_ms,
            )
            return reply
        except Exception:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.exception(
                "处理用户消息异常: user_id=%s, 消息摘要='%s', 耗时=%.1fms",
                user_id,
                msg_summary,
                elapsed_ms,
            )
            return "抱歉，处理您的消息时出现了问题，请稍后再试。"
    @staticmethod
    def _extract_reply(result) -> str:
        """从 Strands Agent 结果中提取干净的文本回复。

        过滤掉未执行的 <tool_call> 标签和 <thinking> 块，
        避免模型内部内容泄漏到最终回复中。
        """
        import re

        # 尝试从 message content 中提取 text block
        try:
            content = result.message.get("content", [])
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    t = block.get("text", "").strip()
                    if t:
                        text_parts.append(t)
            if text_parts:
                raw = "\n".join(text_parts)
            else:
                raw = str(result)
        except Exception:
            raw = str(result)

        # 过滤 <thinking>...</thinking>
        raw = re.sub(r"<thinking>.*?</thinking>", "", raw, flags=re.DOTALL)
        # 过滤未执行的 <tool_call>...</tool_call>
        raw = re.sub(r"<tool_call>.*?</tool_call>", "", raw, flags=re.DOTALL)
        # 过滤未闭合的 <tool_call>... 到末尾
        raw = re.sub(r"<tool_call>.*", "", raw, flags=re.DOTALL)

        return raw.strip() or "抱歉，我暂时无法回答这个问题，请稍后再试。"

    async def evict_inactive(self) -> list[str]:
        """移除超过 TTL 的不活跃 Agent 实例，返回被移除的 user_id 列表。"""
        async with self._global_lock:
            now = time.time()
            expired_ids = [
                uid
                for uid, state in self._agents.items()
                if (now - state.last_active) > AGENT_TTL_SECONDS
            ]
            for uid in expired_ids:
                del self._agents[uid]

            if expired_ids:
                logger.info(
                    "已清除 %d 个不活跃 Agent: %s", len(expired_ids), expired_ids
                )
            return expired_ids
