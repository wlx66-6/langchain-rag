"""mock_llm.py 的单元测试：假大模型 MockChatModel 的串行/流式输出（纯逻辑，不联网）。"""
from app.services.mock_llm import MockChatModel


class TestMockChatModel:
    def test_llm_type(self):
        assert MockChatModel()._llm_type == "mock-chat"

    def test_generate_returns_full_fixed_answer(self):
        model = MockChatModel()
        result = model._generate([])
        assert len(result.generations) == 1
        assert result.generations[0].message.content == model.answer

    def test_stream_chunks_reassemble_to_full_answer(self):
        # 默认 answer 长度 45，chunk_size=6，切成 8 块（最后一块 3 个字）
        model = MockChatModel()
        chunks = list(model._stream([]))
        assert len(chunks) > 1  # 确实被切成了多块，不是一次性吐完
        reconstructed = "".join(c.message.content for c in chunks)
        assert reconstructed == model.answer

    def test_stream_chunk_boundaries_follow_chunk_size(self):
        model = MockChatModel(answer="abcdefghij", chunk_size=4)
        contents = [c.message.content for c in model._stream([])]
        assert contents == ["abcd", "efgh", "ij"]

    def test_custom_answer_and_chunk_size_are_honored(self):
        model = MockChatModel(answer="一二三四五六", chunk_size=3)
        contents = [c.message.content for c in model._stream([])]
        assert contents == ["一二三", "四五六"]