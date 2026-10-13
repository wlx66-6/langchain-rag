"""/api/knowledge 路由测试：上传、列表、删除（仅管理员）与向量库交互。

向量库与上传目录由 `stub_vectorstore` 替换成内存假实现与临时目录。
"""
import pytest


def _upload(client, headers, filename="商品说明.txt", content="X1 耳机，续航 40 小时。支持 7 天无理由退货。"):
    return client.post(
        "/api/knowledge/upload",
        headers=headers,
        files={"file": (filename, content.encode("utf-8"), "text/plain")},
    )


class TestPermissions:
    def test_requires_login(self, client):
        assert client.get("/api/knowledge/documents").status_code == 401

    def test_normal_user_forbidden(self, client, normal_token, bearer):
        r = client.get("/api/knowledge/documents", headers=bearer(normal_token))
        assert r.status_code == 403

    def test_upload_forbidden_for_normal_user(self, client, normal_token, bearer):
        r = _upload(client, bearer(normal_token))
        assert r.status_code == 403


class TestUpload:
    def test_upload_success(self, client, admin_token, bearer, stub_vectorstore):
        r = _upload(client, bearer(admin_token))
        assert r.status_code == 201
        body = r.json()
        assert body["filename"] == "商品说明.txt"
        assert body["file_type"] == "txt"
        assert body["status"] == "ready"
        assert body["chunk_count"] >= 1
        # 切片确实写进了（假的）向量库
        assert len(stub_vectorstore.added) == body["chunk_count"]

    def test_upload_writes_historical_file(self, client, admin_token, bearer, stub_vectorstore, tmp_path):
        _upload(client, bearer(admin_token))
        assert list(tmp_path.glob("*.txt"))  # 原文件已落盘到上传目录

    def test_upload_unsupported_extension(self, client, admin_token, bearer, stub_vectorstore):
        # 当前实现对不支持的格式直接抛 ValueError（P3 将改为更友好的 4xx 响应）
        with pytest.raises(ValueError):
            _upload(client, bearer(admin_token), filename="virus.exe", content="x")


class TestList:
    def test_empty_list(self, client, admin_token, bearer):
        r = client.get("/api/knowledge/documents", headers=bearer(admin_token))
        assert r.status_code == 200
        assert r.json() == []

    def test_list_after_upload(self, client, admin_token, bearer, stub_vectorstore):
        _upload(client, bearer(admin_token))
        docs = client.get("/api/knowledge/documents", headers=bearer(admin_token)).json()
        assert len(docs) == 1
        assert docs[0]["filename"] == "商品说明.txt"


class TestDelete:
    def test_delete_removes_record_and_vectors(self, client, admin_token, bearer, stub_vectorstore):
        doc_id = _upload(client, bearer(admin_token)).json()["id"]

        r = client.delete(f"/api/knowledge/documents/{doc_id}", headers=bearer(admin_token))
        assert r.status_code == 200
        assert client.get("/api/knowledge/documents", headers=bearer(admin_token)).json() == []
        # 删文档时按 doc_id 清理了向量
        assert {"doc_id": doc_id} in stub_vectorstore.deleted

    def test_delete_missing_returns_404(self, client, admin_token, bearer, stub_vectorstore):
        r = client.delete("/api/knowledge/documents/999999", headers=bearer(admin_token))
        assert r.status_code == 404