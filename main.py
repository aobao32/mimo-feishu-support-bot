"""MiMo 飞书 Agent 入口模块。

启动 asyncio 事件循环线程 + 飞书 WS 客户端。

架构：
- 主线程：运行飞书 WS 客户端（阻塞）
- 独立守护线程：运行 asyncio 事件循环，处理异步操作
- 定时 eviction 任务在 asyncio 循环上运行
"""

import asyncio
import threading

from agent_service import AgentService
from feishu_gateway import FeishuGateway
from logger import get_logger

logger = get_logger(__name__)

# 默认 eviction 间隔：1 小时
EVICTION_INTERVAL_SECONDS = 3600


async def _periodic_eviction(agent_service: AgentService, interval: int = EVICTION_INTERVAL_SECONDS) -> None:
    """定期清除不活跃的用户 Agent 实例。"""
    while True:
        await asyncio.sleep(interval)
        try:
            removed = await agent_service.evict_inactive()
            if removed:
                logger.info("定时清理完成，移除 %d 个不活跃 Agent", len(removed))
        except Exception:
            logger.exception("定时清理任务异常")


def _run_loop(loop: asyncio.AbstractEventLoop) -> None:
    """在独立线程中运行 asyncio 事件循环。"""
    asyncio.set_event_loop(loop)
    loop.run_forever()


def main() -> None:
    """启动 asyncio 事件循环线程 + 飞书 WS 客户端。"""
    # 1. 创建 asyncio 事件循环
    loop = asyncio.new_event_loop()

    # 2. 在守护线程中启动事件循环
    loop_thread = threading.Thread(target=_run_loop, args=(loop,), daemon=True)
    loop_thread.start()
    logger.info("asyncio 事件循环已在独立线程中启动")

    # 3. 创建 AgentService 实例
    agent_service = AgentService()

    # 4. 启动定时 eviction 任务
    asyncio.run_coroutine_threadsafe(_periodic_eviction(agent_service), loop)
    logger.info("定时 eviction 任务已启动，间隔 %d 秒", EVICTION_INTERVAL_SECONDS)

    # 5. 创建 FeishuGateway 实例
    gateway = FeishuGateway(agent_service, loop)

    # 6. 启动飞书 WS 客户端（阻塞，运行在主线程）
    logger.info("正在启动飞书 WebSocket 客户端...")
    gateway.start()


if __name__ == "__main__":
    main()
