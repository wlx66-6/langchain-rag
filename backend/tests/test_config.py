"""config.py 的单元测试：压测开关 mock_llm 的默认值与环境变量解析（纯逻辑，不联网）。"""
from app.config import Settings


class TestMockLlmFlag:
    def test_defaults_to_false(self, monkeypatch):
        monkeypatch.delenv("MOCK_LLM", raising=False)
        assert Settings(_env_file=None).mock_llm is False

    def test_env_true_values_enable(self, monkeypatch):
        for value in ("1", "true", "True", "on"):
            monkeypatch.setenv("MOCK_LLM", value)
            assert Settings(_env_file=None).mock_llm is True, f"MOCK_LLM={value!r} 应解析为 True"

    def test_env_false_values_disable(self, monkeypatch):
        for value in ("0", "false", "off"):
            monkeypatch.setenv("MOCK_LLM", value)
            assert Settings(_env_file=None).mock_llm is False, f"MOCK_LLM={value!r} 应解析为 False"