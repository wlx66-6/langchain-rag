---
name: unit-test
description: 为「电商知识库问答系统（LangChain RAG）」项目创建单元测试（后端 pytest + 前端 Vitest），并汇总成测试报告。当你被要求“写单元测试 / 给代码加测试 / 跑测试 / 出测试报告”时使用。
---

# unit-test：创建单元测试并出报告

本项目前后端两套代码，测试分两套：

- **后端（Python + FastAPI）**：用 **pytest**，测试统一放在 `backend/tests/`，文件名 `test_*.py`。
- **前端（React + TypeScript + Vite）**：用 **Vitest**，测试文件与被测源码放同一目录、以 `*.test.ts` / `*.test.tsx` 命名。

测试跑完后，由 Claude 汇总成一份 markdown 测试报告（保存到项目根目录 `test-report.md`）。

## 第 0 步：确认测试环境是否就绪

**安装任何新依赖、修改 `package.json` / `requirements.txt` 前，都要先向用户说明并征得同意。**

- 后端：`venv/Scripts/python.exe -m pytest --version` 看有没有 pytest；没有就 `pip install pytest`。
- 前端：看 `frontend/package.json` 的 `devDependencies` 里有没有 `vitest`、`scripts` 里有没有 `test`。
  没有就 `npm install -D vitest jsdom`；若要测 React 组件，再加 `npm install -D @testing-library/react`。

## 测什么：优先测「纯逻辑」

**后端优先测纯函数**——不联网、不查数据库、不耗大模型、不加载向量模型，快又稳：

- `app/core/security.py`：密码加密/校验（含超长中文密码）、JWT 令牌签发/解码
- `app/services/loader.py`：文件格式白名单 `check_allowed` / `allowed_ext`、纯文本解析 `load_file`
- `app/services/splitter.py`：文本切块 `split_documents`
- `app/services/rag.py`：`format_context` / `build_sources` / `_format_history` 等格式化纯函数

**不要**拿 `get_llm` / `rewrite_question` / `retrieve` 当单元测试（它们要联网、耗模型、查向量库，那是集成测试的范畴）。

**前端优先测纯函数 + 鉴权守卫**：

- `src/lib/api.ts` 的令牌存取：`getAccessToken` / `setTokens` / `clearTokens`
- `src/components/RequireAuth.tsx`：未登录时跳转登录页、已登录时放行

## 测试文件放哪、怎么命名

- 后端：统一 `backend/tests/test_*.py`（后端已有 `backend/pytest.ini`，配置好了 `pythonpath`，直接能 `import app`）。
- 前端：`*.test.ts` / `*.test.tsx` 与被测文件同目录并列。

## 写一个测试的样子（模板）

后端：

```python
def test_某某行为():
    result = 被测函数(参数)
    assert result == 期望结果
```

前端：

```ts
import { describe, it, expect } from 'vitest'

describe('功能的名称', () => {
  it('某种情况的描述', () => {
    expect(实际结果).toBe(期望结果)
  })
})
```

常用断言：`==`（后端）、`toBe`（完全相等）、`toEqual`（结构相等）、`toContain`、`pytest.raises` / `toThrow`（异常）等。

## 跑测试 + 出报告

1. 后端：`cd backend && ..\venv\Scripts\python.exe -m pytest -v`（一次性跑完）
2. 前端：`cd frontend && npm run test`（`vitest run` 跑完即退出；别用 watch）
3. 统计「通过 X 项 / 失败 Y 项」，生成 `test-report.md`，至少包含：
   - 测试时间（年月日）
   - 测了哪些文件、各自测的是啥
   - 「通过 / 失败」数量统计
   - 失败项名称与原因（全过则写「全部通过 ✅」）

## 注意事项

- **发现测试失败且确实是 bug，先报告用户**，不要偷偷改业务代码去「配合」测试通过。
- 测试要真正验证行为，别写「1+1=2」式无意义样例。
- 安装新依赖、改 `package.json` / `requirements.txt` 前，先向用户说明并征得同意。