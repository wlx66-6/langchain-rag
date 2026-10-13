"""假大模型：压力测试时替换通义千问，返回固定文本、支持流式输出，不联网、不花钱。

用法：启动后端前设环境变量 MOCK_LLM=1（对应 app/config.py 的 mock_llm 开关）。
问答接口就会改用这个假模型生成回答，从而只压「SQLite + 词向量 + Chroma 检索」这条本地骨架，
不调用百炼（qwen 改写/生成、重排），既省钱，又不会被百炼的速率限制干扰压测结果。
"""

from collections.abc import Iterator
from typing import Any

from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

# 固定回答 + 每块吐几个字（模拟真模型一个字一个字蹦的流式效果）
_MOCK_ANSWER = "这是压测用的假回答，不经过真实大模型。知识库检索与数据库读写已正常走通。"
_CHUNK_SIZE = 6


class MockChatModel(BaseChatModel):
    """一个行为像真大模型、但只会按固定文本流式吐字的「假客服」。"""

    # 可配字段（压测脚本若要换回答内容/吐字速度，可自行覆盖）
    answer: str = _MOCK_ANSWER
    chunk_size: int = _CHUNK_SIZE

    @property
    def _llm_type(self) -> str:
        return "mock-chat"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        # 非流式路径：一次性返回完整固定回答（本项目假模式里基本用不到，但保证接口完整）
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.answer))])

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        # 流式路径：把固定回答切成若干小块逐块吐出，模拟真模型的 token 流
        for i in range(0, len(self.answer), self.chunk_size):
            yield ChatGenerationChunk(
                message=AIMessageChunk(content=self.answer[i : i + self.chunk_size])
            )
