# 单元测试报告

- **测试日期**：2026-09-12
- **测试框架**：后端 pytest（Python）、前端 Vitest（React + TypeScript）

## 一、总体结果

**全部通过 ✅ —— 后端 55 项 + 前端 6 项，共 61 项，0 失败。**

| 部分 | 通过 | 失败 | 耗时 |
|---|---|---|---|
| 后端 pytest | 55 | 0 | 6.59s |
| 前端 Vitest | 6 | 0 | 13.64s |

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

### test_rag.py —— 引用格式化纯逻辑（11 项）
- `format_context`：空列表、单个/多个片段按 [1][2] 编号、来源缺失回退「未知来源」
- `build_sources`：正确提取来源文件名与片段内容、缺失时回退
- `_format_history`：空历史回退、用户/客服角色正确格式化
- `_dedup`：去掉内容完全相同的重复片段、保留首次出现、跳过纯空白片段

### test_mock_llm.py —— 假大模型 MockChatModel（5 项，本轮新增）
- `_llm_type` 返回 "mock-chat"
- `_generate`（非流式）一次性返回完整固定回答
- `_stream` 流式把固定回答切成多块、逐块吐字，拼起来与原文一致
- 自定义 answer 长度与 chunk_size（吐字速度）时切块边界正确

### test_rerank.py —— `_rerank` 重排打分筛选与兜底（6 项，本轮新增）
- **核心 bug 修复覆盖**：及格线 `rerank_min_score` 把候选筛空时，兜底保留最相关的第一名（不再「有答案却说找不到」）
- 及格候选按相关度从高到低返回、且最多保留 `rerank_top_n` 条
- 空候选直接返回空，不触发远程重排
- 重排返回非 200 / 无打分结果 / 抛异常时，均退回「仅去重」的原始顺序（不阻断主流程）

### test_mock_mode.py —— 压测开关 mock_llm 行为（6 项，本轮新增）
- `get_llm()`：mock 模式下返回假模型 `MockChatModel`，正常模式不返回假模型
- `rewrite_question()`：mock 模式下跳过改写、无历史时也跳过改写（均不调用大模型）
- `retrieve_with_rerank()`：mock 模式下跳过远程重排、只把去重后的候选截取前 top_k 段；正常模式正确委托给 `_rerank`

### test_config.py —— 压测开关配置字段（3 项，本轮新增）
- `mock_llm` 默认值为 False
- 环境变量 `MOCK_LLM` 为 "1"/"true"/"True"/"on" 时解析为 True
- 为 "0"/"false"/"off" 时解析为 False

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

> 说明：后端测试只覆盖「纯逻辑」，不联网、不查数据库、不耗大模型/向量模型，秒级跑完；完整的「上传文档 → 提问 → 带引用回答」链路另有 `backend/smoke_test.py`（账号体系）和 `backend/e2e_test.py`（端到端 RAG）可单独验证。本轮新增的 mock/重排测试通过 `monkeypatch` 把远程重排（dashscope）与检索替换为假实现，未触发任何真实网络调用。