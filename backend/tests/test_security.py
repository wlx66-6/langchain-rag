"""security.py 的单元测试：密码加密/校验 + JWT 令牌签发/解码（纯逻辑，不联网）。"""
import jwt
import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPassword:
    def test_hash_returns_non_plain_string(self):
        hashed = hash_password("secret123")
        assert isinstance(hashed, str)
        assert hashed != "secret123"

    def test_verify_correct_password(self):
        hashed = hash_password("secret123")
        assert verify_password("secret123", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("secret123")
        assert verify_password("wrong-password", hashed) is False

    def test_verify_long_chinese_password(self):
        # 中文密码每字 3 字节，这里远超 bcrypt 的 72 字节上限，验证 SHA256 预哈希分支
        long_pwd = "这是一个超级长的中文密码" * 10
        hashed = hash_password(long_pwd)
        assert verify_password(long_pwd, hashed) is True
        assert verify_password(long_pwd + "错", hashed) is False

    def test_verify_invalid_hash_returns_false(self):
        # 非法哈希串不应抛异常，而是返回 False
        assert verify_password("anything", "not-a-valid-bcrypt-hash") is False


class TestTokens:
    def test_access_token_decodes_with_type(self):
        token = create_access_token(42)
        payload = decode_token(token)
        assert payload["sub"] == "42"
        assert payload["type"] == "access"

    def test_refresh_token_decodes_with_type(self):
        token = create_refresh_token(42)
        payload = decode_token(token)
        assert payload["sub"] == "42"
        assert payload["type"] == "refresh"

    def test_access_and_refresh_tokens_differ(self):
        assert create_access_token(1) != create_refresh_token(1)

    def test_decode_garbage_token_raises(self):
        with pytest.raises(jwt.InvalidTokenError):
            decode_token("not-a-real-token")