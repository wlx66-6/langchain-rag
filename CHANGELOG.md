# 变更记录

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 与
[语义化版本](https://semver.org/lang/zh-CN/)。

> 说明：以下版本号是按开发阶段**回溯整理**的（项目未打 git tag），
> 用于描述各阶段的能力变化。每次发版前的详细提交见 `git log`。

---

## [1.1.0] - 2026-10-13

一次面向工程质量与规范性的整体改造：修复真实缺陷、补齐测试与工具链、清理课程作业痕迹。

### Added

- **统一日志基础设施**（`app/logging_config.py`），启动时初始化，替换此前的静默吞异常。
- **后端脚本转正**：手动 `smoke_test.py` / `e2e_test.py` 改造为 pytest 用例，
  标记 `integration` / `e2e`，默认跳过、不进 CI。
- **后端路由与鉴权测试**：覆盖 200 / 400 / 401 / 403 / 404 与主路径。
- **前端测试体系**：Vitest + Testing Library，补页面、路由守卫与 `lib/` 工具测试。
- **覆盖率工具与阈值**：pytest-cov（后端 ≥70%）、@vitest/coverage-v8（前端 ≥60%）。
- **代码规范工具链**：ruff（后端，lint + format）、ESLint + Prettier（前端），
  并开启 TypeScript `noUnusedLocals` / `noUnusedParameters`。
- **CI 与工程基础**：`scripts/ci.sh`（本地一键质量总检）、`.github/workflows/ci.yml`、
  `.editorconfig`、扩展 `.gitattributes` 换行规则。
- **文档体系**：`CONTEXT.md`（领域术语表）、`docs/adr/0001~0005`（架构决策记录）、
  `docs/gate.md`（质量门禁说明）、`CONTRIBUTING.md`、`CHANGELOG.md`、`LICENSE`。
- **接口清单与交互式文档**：README 附 15 个接口说明，运行时可用 `/docs` 查阅。
- **上传大小限制**（`MAX_UPLOAD_SIZE`，默认 20MB，超限返回 413）。
- **列表接口分页**：会话、消息、知识文档列表支持 `limit` / `offset`。

### Fixed

- **安全**：移除 JWT 默认密钥与硬编码 `admin/123456`，改为从 `.env` 读取，缺失即启动报错；
  CORS 由 `*` 收敛为配置项。
- **SSE 异常信息泄露**：对外只回传统一文案 + 错误码，真实堆栈仅落日志。
- **SSE 生成失败**：补写兜底助手消息，避免会话留下「有问无答」的悬空记录。
- **SSE 无断开检测**：注入 `Request`，客户端断开时停止生成，避免无谓算力消耗。
- **知识库删除不彻底**：删除文档时级联清理向量库中的块与磁盘物理文件。
- **检索去重误删**：去重键由「内容」改为「(来源, 内容)」，
  修复不同文件中的相同句子被误删引用的问题。
- **向量库实例未缓存**：`get_vectorstore()` 加进程内缓存，避免每个请求重建 Chroma。
- **文档解析静默丢字**：编码回退（UTF-8 → GBK）与空内容均记日志告警。
- **SQLite 并发**：开启 WAL、`busy_timeout`、`synchronous=NORMAL`，引擎加 `pool_pre_ping`。
- **前端 SSE 生命周期**：抽取 `lib/sse.ts`，用 `AbortController` 支持取消，
  切换会话/卸载时中止在途流，杜绝旧流回调污染新会话。
- **前端鉴权一次性数据源**：统一到 `AuthContext`，启动时校验令牌后再渲染，消除闪烁；
  SSE 路径遇 401 走刷新流程而非直接跳登录。
- **前端交互**：`window.alert/confirm` 替换为自建轻量 toast / 确认框；
  统一 `catch (err: unknown)`，不再空吞异常。

### Changed

- README 重写：删除「答辩要点」「大白话版」「企业级承载能力」等表述，
  性能数据如实区分 mock / real 模式并标注已知局限。
- 前端样式拆分为 `styles/base.css`、`components.css`、`pages.css`，设计变量提为 CSS 变量，补基础响应式。
- 依赖版本锁定（`requirements.txt` 全部 `==`），新增 `requirements-dev.txt`。
- 依赖的代码全部经 ruff format + Prettier 统一格式化。
- 压测生成物（`report_*.html`、`results_*.csv`）与 `test-report.md` 移出 git 跟踪。

### Removed

- 仓库内被跟踪的压测/测试生成物（约 2MB）。
- 代码与数据中的课程作业痕迹（示例商品名、演示账号 `itheima`、含 `graduation-project` 的密钥等）。

---

## [1.0.1] - 2026-09-12

### Added

- Locust 压测脚本与压测报告（mock / real 两模式）。
- `MOCK_LLM` 开关：压测时使用假大模型并跳过远程重排，可离线、不产生调用费用。

### Fixed

- **重排及格线过高导致漏答**：相关度全部低于及格线时，兜底保留最相关的一条，
  修复「知识库里明明有答案却回答找不到」的问题。

---

## [1.0.0] - 2026-09-12

### Added

- 初始版本：电商知识库问答系统。
- 后端 FastAPI 分层架构；LangChain RAG 链路（bge-m3 向量化 → Chroma 检索 →
  gte-rerank-v2 重排 → qwen-plus 流式生成 → 引用溯源）。
- 前端 React 18 + TypeScript + Vite：对话页、知识库管理、登录/注册/个人中心。
- JWT 双令牌鉴权、bcrypt 密码存储、多用户多会话隔离。
- 知识库上传/删除（PDF / Word / Excel / TXT / Markdown / CSV）。
- Claude 质量门禁工具链（子代理 + `gate.mjs` + githooks）。