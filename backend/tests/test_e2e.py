"""端到端测试：真实上传文档 → 提问 → 流式回答 + 引用片段。

这条链路会**真实调用** bge-m3 向量化、百炼重排与通义千问生成，耗时较长且产生费用，
因此默认被 pytest.ini 标记跳过。按需运行（-s 以便看到模型回答）：

    cd backend
    ../venv/Scripts/python.exe -m pytest -m e2e -v -s

前置条件：backend/.env 已配置 JWT_SECRET、DASHSCOPE_API_KEY、ADMIN_PASSWORD。
"""
import json
import random

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

pytestmark = pytest.mark.e2e

_DOC = (
    "X1 无线降噪耳机 商品说明\n"
    "- 型号：X1\n"
    "- 续航：单次充电最长续航 40 小时（含充电盒）\n"
    "- 颜色：曜石黑、珍珠白、雾霾蓝三种\n"
    "- 价格：399 元\n"
    "- 售后：支持 7 天无理由退货，全国联保 1 年\n"
)


@pytest.fixture(scope="module")
def client():
    if not (settings.jwt_secret and settings.dashscope_api_key and settings.admin_password):
        pytest.skip("缺少 JWT_SECRET / DASHSCOPE_API_KEY / ADMIN_PASSWORD，跳过端到端测试")
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def admin_headers(client):
    r = client.post(
        "/api/auth/login",
        json={"username": settings.admin_username, "password": settings.admin_password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def user_headers(client):
    uname = f"buyer{random.randint(1000, 9999)}"
    assert client.post(
        "/api/auth/register", json={"username": uname, "password": "test123456"}
    ).status_code in (200, 201)
    r = client.post("/api/auth/login", json={"username": uname, "password": "test123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _ask(client, headers, question):
    """发起一次流式问答，返回 (完整回答, 引用片段列表)。"""
    tokens, sources = [], None
    with client.stream(
        "POST",
        "/api/chat",
        json={"conversation_id": None, "content": question},
        headers=headers,
    ) as resp:
        assert resp.status_code == 200, resp.text
        for line in resp.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            payload = json.loads(line[5:].strip())
            if payload["type"] == "start":
                sources = payload["data"]["sources"]
            elif payload["type"] == "token":
                tokens.append(payload["data"])
            elif payload["type"] == "error":
                pytest.fail(f"生成失败：{payload['data']}")
    return "".join(tokens), sources


def test_upload_ask_and_cleanup(client, admin_headers, user_headers):
    # 1) 上传商品文档
    r = client.post(
        "/api/knowledge/upload",
        headers=admin_headers,
        files={"file": ("示例商品说明.txt", _DOC.encode("utf-8"), "text/plain")},
    )
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]

    try:
        # 2) 属于知识库的问题：应能引用到资料
        answer, sources = _ask(client, user_headers, "X1 耳机的续航是多少小时？")
        assert answer.strip(), "回答为空"
        assert sources, "未返回任何引用片段"
        assert any("商品说明" in s["source"] for s in sources)

        # 3) 知识库外的问题：应明确表示无法回答，而不是编造
        answer2, _ = _ask(client, user_headers, "请问贵公司 CEO 的生日是哪天？")
        assert answer2.strip()
    finally:
        # 4) 清理测试文档
        assert client.delete(
            f"/api/knowledge/documents/{doc_id}", headers=admin_headers
        ).status_code == 200