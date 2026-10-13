# 贡献指南

感谢关注本项目。本文说明开发约定，让改动保持一致的风格与质量。

> 这是一个个人学习/求职项目，主要作者即维护者。以下约定对提交 PR 或自行二次开发都适用。

---

## 一、环境准备

```bash
# 后端：在仓库根目录创建虚拟环境
python -m venv venv
venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt   # Windows
# venv/bin/python -m pip install -r backend/requirements-dev.txt          # Linux/macOS

# 前端
cd frontend && npm install
```

配置 `backend/.env`（从 `backend/.env.example` 复制），至少填写 `DASHSCOPE_API_KEY` 与 `JWT_SECRET`。

---

## 二、开发流程

1. 从 `main` 切出分支，命名建议 `feat/xxx`、`fix/xxx`、`docs/xxx`。
2. 改代码，**同步补测试**（见下）。
3. 本地跑全套检查：`bash scripts/ci.sh`（格式 + 静态检查 + 单测 + 构建）。
4. 提交（Conventional Commits，见下）。

---

## 三、代码风格

风格由工具强制，不靠人工记忆：

| 范围 | 工具 | 配置 |
|---|---|---|
| Python | ruff（lint + format） | `backend/pyproject.toml` |
| 前端 | ESLint + Prettier | `frontend/eslint.config.js`、`frontend/.prettierrc.json` |
| 通用 | EditorConfig（换行符、缩进、末尾空行） | `.editorconfig` |

```bash
# 后端
cd backend && ../venv/Scripts/ruff.exe check . && ../venv/Scripts/ruff.exe format .

# 前端
cd frontend && npm run lint && npm run format
```

其它约定：

- **注释用中文**（面向国内团队/面试场景），写「为什么」而不是「做什么」。
- Python 公共函数必须标注类型；docstring 一句话说明用途，复杂入参用 Google 风格。
- 前端 `catch (e: unknown)` + 类型守卫，**不要空吞异常**。
- 命名：Python `snake_case` / 类 `PascalCase`；前端组件 `PascalCase`、hook `useXxx`。

---

## 四、测试

- 后端：`cd backend && ../venv/Scripts/python.exe -m pytest -q`
  新增逻辑请放到 `backend/tests/test_*.py`；需要真实向量库/大模型的用例请标
  `@pytest.mark.integration` 或 `@pytest.mark.e2e`（默认跳过、不进 CI）。
- 前端：`cd frontend && npm test`，测试文件与被测源码同目录、`*.test.ts(x)`。
- **纯逻辑优先**：不联网、不查库的函数最容易测、最值得测。
- 修 bug 时**先写能复现的失败用例**，再修，最后用例转绿。

覆盖率阈值：后端 ≥ 70%（`pytest --cov-fail-under=70`）、前端 ≥ 60%（`vitest.config.ts`）。

---

## 五、提交信息规范（Conventional Commits）

格式：`<type>(<scope>): <描述>`，描述用中文、祈使语气、一句话说清「改了什么」。

| type | 用于 |
|---|---|
| `feat` | 新功能 |
| `fix` | 修 bug |
| `refactor` | 重构（不改外部行为） |
| `perf` | 性能优化 |
| `test` | 增改测试 |
| `docs` | 文档 |
| `style` | 纯格式化（不含逻辑改动） |
| `chore` | 构建/依赖/工具等杂项 |
| `ci` | CI 配置 |

示例：

```
fix(chat): SSE 生成失败时补写兜底消息，避免会话留下悬空记录
docs: 补齐 CONTEXT/ADR/gate 文档并修复失效的技能引用
```

> 约定：**大范围格式化单独一个 `style:` 提交**，便于整体 revert。

---

## 六、质量门禁（可选）

本项目内置提交门禁（单元测试 + 质量检查双通过才放行）。启用：

```bash
node scripts/gate.mjs install    # 设置 core.hooksPath，之后 pre-commit 自动验票
```

详细说明与排障见 [docs/gate.md](docs/gate.md)。紧急情况可用 `git commit --no-verify` 跳过。

---

## 七、改动文档

- 架构/技术选型的**重要决策**请新增一条 ADR（`docs/adr/NNNN-标题.md`），说明背景、决策、理由、后果。
- 面向用户的变更记入 [CHANGELOG.md](CHANGELOG.md)。
- 涉及领域概念时，遵循 [CONTEXT.md](CONTEXT.md) 的术语表，不要自造近义词。