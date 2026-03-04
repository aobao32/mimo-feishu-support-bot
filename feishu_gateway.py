"""飞书 WebSocket 网关模块。

处理飞书消息收发，通过 asyncio 桥接将同步回调委托给异步事件循环。
"""

import asyncio
import json
import sys
import time

import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from agent_service import AgentService
from config import APP_ID, APP_SECRET
from logger import get_logger

logger = get_logger(__name__)


class FeishuGateway:
    """飞书 WebSocket 网关，处理消息收发。"""

    def __init__(self, agent_service: AgentService, loop: asyncio.AbstractEventLoop) -> None:
        self._agent_service = agent_service
        self._loop = loop

        # 检查飞书应用凭证
        if not APP_ID or not APP_SECRET:
            logger.error("环境变量 APP_ID 或 APP_SECRET 未设置，请先配置后再启动。")
            sys.exit(1)

        # 初始化飞书客户端
        self._client = (
            lark.Client.builder()
            .app_id(APP_ID)
            .app_secret(APP_SECRET)
            .build()
        )

        # 消息去重：set 用于 O(1) 查找，list 保持插入顺序以便清理
        self._processed_ids: set[str] = set()
        self._processed_ids_order: list[str] = []

        logger.info("FeishuGateway 初始化完成")

    # ------------------------------------------------------------------
    # 消息去重
    # ------------------------------------------------------------------

    def _is_duplicate(self, message_id: str) -> bool:
        """检查 message_id 是否已处理过。超过 1000 条时清理最早的 500 条。"""
        if message_id in self._processed_ids:
            return True

        # 记录新 message_id
        self._processed_ids.add(message_id)
        self._processed_ids_order.append(message_id)

        # 超限清理
        if len(self._processed_ids_order) > 1000:
            to_remove = self._processed_ids_order[:500]
            self._processed_ids_order = self._processed_ids_order[500:]
            for mid in to_remove:
                self._processed_ids.discard(mid)

        return False

    # ------------------------------------------------------------------
    # 消息接收回调
    # ------------------------------------------------------------------

    def handle_message(self, data: P2ImMessageReceiveV1) -> None:
        """消息事件回调（同步），桥接到异步处理。"""
        try:
            message = data.event.message
            message_id = message.message_id

            # 去重
            if self._is_duplicate(message_id):
                logger.debug("重复消息，跳过: %s", message_id)
                return

            # 添加 reaction 表示已收到
            self._send_reaction(message_id, "OK")

            # 非文本消息直接回复提示
            if message.message_type != "text":
                logger.info("收到非文本消息 (type=%s), message_id=%s", message.message_type, message_id)
                self._send_reply(data, "请发送文字消息")
                return

            # 提取文本内容
            text = json.loads(message.content)["text"]
            user_id = data.event.sender.sender_id.open_id
            logger.info("收到消息: user=%s, text=%s, message_id=%s", user_id, text[:50], message_id)

            # 通过 asyncio 桥接到异步事件循环处理
            start = time.time()
            future = asyncio.run_coroutine_threadsafe(
                self._agent_service.ask(user_id, text),
                self._loop,
            )
            reply_text = future.result()  # 阻塞等待异步结果
            elapsed_ms = (time.time() - start) * 1000
            logger.info("回复完成: user=%s, 耗时=%.0fms, message_id=%s", user_id, elapsed_ms, message_id)

            self._send_reply(data, reply_text)

        except Exception:
            logger.exception("处理消息时发生异常")

    def _send_reply(self, data: P2ImMessageReceiveV1, reply_text: str) -> None:
        """根据消息类型（p2p/群聊）发送回复。"""
        from lark_oapi.api.im.v1 import (
            CreateMessageRequest,
            CreateMessageRequestBody,
            ReplyMessageRequest,
            ReplyMessageRequestBody,
        )

        post_content = self.text_to_post(reply_text)
        content_json = json.dumps(post_content)
        message = data.event.message
        chat_type = message.chat_type
        message_id = message.message_id

        try:
            if chat_type == "p2p":
                chat_id = message.chat_id
                request = (
                    CreateMessageRequest.builder()
                    .receive_id_type("chat_id")
                    .request_body(
                        CreateMessageRequestBody.builder()
                        .receive_id(chat_id)
                        .msg_type("post")
                        .content(content_json)
                        .build()
                    )
                    .build()
                )
                response = self._client.im.v1.message.create(request)
            else:
                request = (
                    ReplyMessageRequest.builder()
                    .message_id(message_id)
                    .request_body(
                        ReplyMessageRequestBody.builder()
                        .msg_type("post")
                        .content(content_json)
                        .build()
                    )
                    .build()
                )
                response = self._client.im.v1.message.reply(request)

            if not response.success():
                logger.error(
                    "发送回复失败: code=%s, msg=%s, chat_type=%s, message_id=%s",
                    response.code,
                    response.msg,
                    chat_type,
                    message_id,
                )
        except Exception:
            logger.error("发送回复异常: message_id=%s", message_id, exc_info=True)

    def _send_reaction(self, message_id: str, emoji_type: str) -> None:
        """给消息添加 reaction。"""
        from lark_oapi.api.im.v1 import (
            CreateMessageReactionRequest,
            CreateMessageReactionRequestBody,
            Emoji,
        )

        try:
            request = (
                CreateMessageReactionRequest.builder()
                .message_id(message_id)
                .request_body(
                    CreateMessageReactionRequestBody.builder()
                    .reaction_type(Emoji.builder().emoji_type(emoji_type).build())
                    .build()
                )
                .build()
            )
            response = self._client.im.v1.message_reaction.create(request)
            if not response.success():
                logger.warning(
                    "添加 reaction 失败: code=%s, msg=%s, message_id=%s",
                    response.code,
                    response.msg,
                    message_id,
                )
        except Exception:
            logger.warning("添加 reaction 异常: message_id=%s", message_id, exc_info=True)

    def text_to_post(self, text: str) -> dict:
        """纯文本转飞书 post 富文本格式。"""
        lines = text.split("\n")
        content = [[{"tag": "text", "text": line}] for line in lines]
        return {"zh_cn": {"title": "", "content": content}}

    def start(self) -> None:
        """启动 WebSocket 客户端。"""
        # 创建事件处理器，注册消息接收回调
        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self.handle_message)
            .register_p2_im_message_reaction_created_v1(lambda data: None)
            .register_p2_im_message_message_read_v1(lambda data: None)
            .build()
        )

        # 创建 WebSocket 客户端
        ws_client = lark.ws.Client(
            APP_ID,
            APP_SECRET,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
        )

        logger.info("正在启动飞书 WebSocket 长连接...")
        # 启动 WebSocket 连接（阻塞调用）
        ws_client.start()
