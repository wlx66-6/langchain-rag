"""端到端实测：上传商品文档 → 提问 → 流式回答 + 引用片段（真实调用 bge-m3 + 通义千问）。"""
import json
import random

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)

print("=== 1) 管理员登录 ===")
r = client.post(
    "/api/auth/login",
    json={"username": settings.admin_username, "password": settings.admin_password},
)
assert r.status_code == 200, r.text
admin_token = r.json()["access_token"]
print("admin 登录成功")

print("\n=== 2) 上传测试商品文档 ===")
doc_content = (
    "X1 无线降噪耳机 商品说明\n"
    "- 型号：X1\n"
    "- 续航：单次充电最长续航 40 小时（含充电盒）\n"
    "- 颜色：曜石黑、珍珠白、雾霾蓝三种\n"
    "- 价格：399 元\n"
    "- 售后：支持 7 天无理由退货，全国联保 1 年\n"
)
files = {"file": ("示例商品说明.txt", doc_content.encode("utf-8"), "text/plain")}
r = client.post(
    "/api/knowledge/upload",
    headers={"Authorization": f"Bearer {admin_token}"},
    files=files,
)
print("上传状态:", r.status_code, "| 返回:", r.json())
assert r.status_code == 201, r.text
doc_id = r.json()["id"]

print("\n=== 3) 知识库列表确认 ===")
r = client.get("/api/knowledge/documents", headers={"Authorization": f"Bearer {admin_token}"})
print("列表状态:", r.status_code, "| 文档数:", len(r.json()))

print("\n=== 4) 注册并登录一个普通用户 ===")
uname = f"buyer{random.randint(1000, 9999)}"
r = client.post("/api/auth/register", json={"username": uname, "password": "test123456"})
assert r.status_code in (200, 201), r.text
r = client.post("/api/auth/login", json={"username": uname, "password": "test123456"})
user_token = r.json()["access_token"]
print("普通用户:", uname, "登录成功")

print("\n=== 5) 提问（流式，真实走 RAG） ===")
question = "X1 耳机的续航是多少小时？"
tokens, sources, err = [], None, None
with client.stream(
    "POST",
    "/api/chat",
    json={"conversation_id": None, "content": question},
    headers={"Authorization": f"Bearer {user_token}"},
) as resp:
    print("问答接口状态:", resp.status_code)
    assert resp.status_code == 200, resp.text
    for line in resp.iter_lines():
        if not line or not line.startswith("data:"):
            continue
        payload = json.loads(line[5:].strip())
        t = payload["type"]
        if t == "start":
            sources = payload["data"]["sources"]
        elif t == "token":
            tokens.append(payload["data"])
        elif t == "error":
            err = payload["data"]

answer = "".join(tokens)
print("\n===== 模型回答 =====")
print(answer)
print("\n===== 引用片段 =====")
print(json.dumps(sources, ensure_ascii=False, indent=2))

print("\n===== 校验结果 =====")
if err:
    print("❌ 生成报错:", err)
else:
    print("✅ 回答了非空:", bool(answer.strip()))
    print("✅ 引用片段数量:", len(sources) if sources else 0)
    assert answer.strip(), "回答为空"
    assert sources, "没有引用片段"
    print("\n=== 端到端测试全部通过 ✅ ===")

print("\n=== 6) 清理：删除测试文档 ===")
r = client.delete(f"/api/knowledge/documents/{doc_id}", headers={"Authorization": f"Bearer {admin_token}"})
print("删除状态:", r.status_code, r.json())