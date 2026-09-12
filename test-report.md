# 单元测试报告

- **测试日期**：2026-09-12
- **测试框架**：后端 pytest（Python）、前端 Vitest（React + TypeScript）

## 一、总体结果

**全部通过 ✅ —— 后端 32 项 + 前端 6 项，共 38 项，0 失败。**

| 部分 | 通过 | 失败 | 耗时 |
|---|---|---|---|
| 后端 pytest | 32 | 0 | 6.61s |
| 前端 Vitest | 6 | 0 | 17.30s |

## 二、后端测试（pytest，`backend/tests/`）

### test_security.py —— 密码加密 + JWT 令牌（9 项）
- 密码加密后不再是明文、正确密码校验通过、错误密码校验失败
- 超长中文密码（远超 bcrypt 的 72 字节上限）能正确加密/校验（验证 SHA256 预哈希分支）
- 非法哈希串不抛异常、返回 False
- access / refresh 令牌签发与解码（sub、type 正确）、两者互不相同
- 伪造令牌解码时抛异常

### test_loader.py —— 文件格式白名单 + 纯文本解析（12 项）
- `allowed_ext` 扩展名大小写归一、无后缀返回空
- `check_allowed` 白名单通过（.pdf/.docx/.xlsx/.txt/.md/.csv 各一例）
- 非法扩展名（.exe）抛 ValueError
- `load_file` 解析 txt / markdown 文本，非法格式抛错

### test_splitter.py —— 文本切块（3 项）
- 短文本保持单块、长文本切成多块且每块非空、切块时元数据被保留

### test_rag.py —— 引用格式化纯逻辑（8 项）
- `format_context`：空列表、单个/多个片段按 [1][2] 编号、来源缺失回退「未知来源」
- `build_sources`：正确提取来源文件名与片段内容、缺失时回退
- `_format_history`：空历史回退、用户/客服角色正确格式化

## 三、前端测试（Vitest）

### src/lib/api.test.ts —— 令牌存取（3 项）
- 初始无令牌、`setTokens` 写入 access/refresh、`clearTokens` 清空令牌与用户信息

### src/lib/auth.test.tsx —— useAuth 用法（1 项）
- 在 AuthProvider 之外使用 useAuth 时抛错

### src/components/RequireAuth.test.tsx —— 鉴权守卫（2 项）
- 未登录时跳转到登录页（不渲染受保护内容）
- 已登录时正常渲染受保护内容

## 四、失败项

无 —— **全部通过 ✅**

## 五、如何复跑

```bash
# 后端
cd backend
..\venv\Scripts\python.exe -m pytest -v

# 前端
cd frontend
npm test
```

> 说明：后端测试只覆盖「纯逻辑」，不联网、不查数据库、不耗大模型/向量模型，秒级跑完；完整的「上传文档 → 提问 → 带引用回答」链路另有 `backend/smoke_test.py`（账号体系）和 `backend/e2e_test.py`（端到端 RAG）可单独验证。