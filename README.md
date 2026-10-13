# 电商知识库问答系统（LangChain RAG）

一个基于 **LangChain** 的检索增强生成（RAG）问答系统，面向电商商品/售后场景。
管理员上传商品资料构建知识库，用户像和客服聊天一样提问——系统**先检索知识库、再交给大模型生成答案，
并在回答下方标注引用了哪些原文片段**，做到有据可查、可溯源。

> 一句话：**一个「先翻资料、再回答、还标注出处」的智能客服。**

![backend coverage](https://img.shields.io/badge/backend%20coverage-89%25-brightgreen)
![frontend coverage](https://img.shields.io/badge/frontend%20coverage-97%25-brightgreen)
![tests](https://img.shields.io/badge/tests-214%20passed-brightgreen)
![license](https://img.shields.io/badge/license-MIT-blue)

> 徽章里的数字对应实测值，改代码后请同步更新（见「测试与质量」）。

---

## 一、功能特性

| 能力 | 说明 |
|---|---|
| **知识库管理** | 管理员上传/删除/查看 PDF、Word、Excel、TXT、Markdown、CSV 文档，自动解析、切块、向量化入库 |
| **可溯源问答** | 回答下方展示「引用资料」（来源文件名 + 原文片段），回答可核对 |
| **流式输出** | 基于 SSE 边生成边显示；支持客户端断开检测与失败兜底 |
| **多轮上下文** | 追问自动改写为可独立检索的问题（如「它多少钱」→ 补全商品名） |
| **两阶段检索** | 向量召回（bge-m3 + Chroma）→ 远程重排（gte-rerank-v2）精排 |
| **多用户多会话** | 每个用户多个会话，数据严格隔离（访问他人会话返回 404） |
| **鉴权** | bcrypt 存密码 + JWT 双令牌（access/refresh），令牌过期无感刷新 |
| **权限隔离** | 仅管理员可管理知识库，前端隐藏入口 + 后端依赖强制校验 |

---

## 二、系统架构

```
┌─────────────────────────────┐         ┌──────────────────────────────────────────┐
│  前端 React 18 + TS + Vite  │         │  后端 FastAPI（分层单体）                 │
│  http://localhost:5173      │         │  http://127.0.0.1:8000                    │
│                             │         │                                           │
│  pages/   登录/注册/对话/    │  HTTP   │  routers/   auth · chat · knowledge       │
│           知识库/个人中心    │ ──────► │      │                                    │
│  lib/     api · auth · sse  │  + SSE  │  services/  rag · loader · splitter ·     │
│           errors · ui       │ ◄────── │             embeddings · vectorstore       │
│  styles/  base/comp/pages   │         │  core/      security · deps               │
└─────────────────────────────┘         │  models/ schemas/ config.py               │
                                        └───────┬──────────────┬───────────────────┘
                                                │              │
                        ┌───────────────────────┘              └──────────────────┐
                        ▼                                                          ▼
              ┌───────────────────┐                                  ┌──────────────────────┐
              │ SQLite (业务数据)  │                                  │ Chroma (向量)         │
              │ 用户/会话/消息/文档 │                                  │ 文本块向量             │
              └───────────────────┘                                  └──────────────────────┘
                                                                              ▲
                        ┌─────────────────────────────────────────────────────┘
                        │
                 bge-m3（本地向量化） ──► gte-rerank-v2（远程重排） ──► qwen-plus（远程生成）
```

问答链路：

```
用户提问
  └─► 多轮追问改写（依赖上文的追问 → 独立完整问题）
        └─► 向量检索（bge-m3 编码 → Chroma 取 top_k 候选）
              └─► 重排打分（gte-rerank-v2 精排，低于及格线剔除；全不达标则兜底保留第一名）
                    └─► 拼装上下文（按 [1][2] 编号 + 来源标注）
                          └─► qwen-plus 流式生成（要求标注 [编号] 出处）
                                └─► SSE 推送前端 → 渲染答案 + 引用卡片
```

---

## 三、技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 后端框架 | Python 3.10+ · FastAPI · uvicorn | 异步 Web 框架，自带 OpenAPI 文档 |
| RAG 编排 | LangChain 1.4 | 检索-生成链编排 |
| 大模型 | 阿里云百炼 通义千问 `qwen-plus` | 可切换 `qwen-turbo` / `qwen-max` |
| 向量化 | 本地 `bge-m3`（sentence-transformers） | 本地推理，无外部向量 API 依赖 |
| 重排 | 百炼 `gte-rerank-v2` | 两次排序，提升引用精度 |
| 向量库 | ChromaDB | 本地持久化，进程内缓存实例 |
| 关系库 | SQLite + SQLAlchemy 2.x | WAL 模式 + busy_timeout + pool_pre_ping |
| 鉴权 | PyJWT + bcrypt | JWT 双令牌；bcrypt 前做 SHA256 预哈希 |
| 前端 | React 18 · TypeScript · Vite | 无组件库，自建轻量 toast/确认框 |
| 后端测试 | pytest · pytest-cov · httpx | 129 用例 + 8 集成例（默认跳过） |
| 前端测试 | Vitest · Testing Library · jsdom | 85 用例，覆盖率阈值 60% |
| 代码规范 | ruff（lint + format）· ESLint · Prettier | 见 `backend/pyproject.toml`、`frontend/eslint.config.js` |
| 压测 | Locust | 支持 mock / real 两模式 |

---

## 四、接口清单

后端启动后可在 **http://127.0.0.1:8000/docs** 查看交互式接口文档（FastAPI 自动生成，含请求/响应模型）。

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | `/api/auth/register` | 注册 | 公开 |
| POST | `/api/auth/login` | 登录，返回双令牌 | 公开 |
| POST | `/api/auth/refresh` | 用 refresh token 换新令牌 | 公开 |
| GET | `/api/auth/me` | 当前用户信息 | 登录 |
| POST | `/api/auth/change-password` | 修改密码 | 登录 |
| POST | `/api/conversations` | 新建会话 | 登录 |
| GET | `/api/conversations` | 会话列表（分页） | 登录 |
| PATCH | `/api/conversations/{id}` | 重命名会话 | 本人 |
| DELETE | `/api/conversations/{id}` | 删除会话 | 本人 |
| GET | `/api/conversations/{id}/messages` | 某会话的消息（分页） | 本人 |
| POST | `/api/chat` | **问答（SSE 流式返回）** | 登录 |
| GET | `/api/knowledge/documents` | 知识文档列表（分页） | 管理员 |
| POST | `/api/knowledge/upload` | 上传文档入库 | 管理员 |
| DELETE | `/api/knowledge/documents/{id}` | 删除文档（级联删向量与物理文件） | 管理员 |
| GET | `/api/health` | 健康检查 | 公开 |

共 **15 个接口**（14 个业务接口 + 1 个健康检查）。

---

## 五、快速开始（Windows）

### 0. 准备

1. [Python 3.10+](https://www.python.org/)（安装时勾选 *Add to PATH*）
2. [Node.js](https://nodejs.org/)
3. 注册[阿里云百炼](https://bailian.console.aliyun.com/)并开通通义千问，获取 **API Key**

### 1. 配置环境变量

复制 `backend/.env.example` 为 `backend/.env`，至少填两项：

```ini
DASHSCOPE_API_KEY=你的百炼API密钥
JWT_SECRET=用 python -c "import secrets; print(secrets.token_urlsafe(48))" 生成的随机串
```

> `JWT_SECRET` **缺失时后端会拒绝启动并有明确提示**——这是刻意设计，杜绝使用可预测的默认密钥。
> 全部可配置项见 `backend/.env.example` 的注释。

### 2. 一键安装

双击 **`setup.bat`**（创建虚拟环境 + 安装前后端依赖）。

### 3. 一键启动

双击 **`start.bat`**，拉起后端（8000）与前端（5173）并自动打开浏览器。

访问 **http://localhost:5173**。首次使用请先注册账号；若要使用知识库管理，
需在 `.env` 中配置 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 后再启动（后端会自动创建该管理员）。

### 手动启动（可选）

```bash
# 后端（在 backend/ 目录）
../venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 前端（在 frontend/ 目录，另开终端）
npm run dev
```

### 常见问题

- **首次提问/上传很慢**：首次会自动下载 bge-m3 模型（约 2.3GB）。默认走 `HF_ENDPOINT` 镜像加速；
  若镜像不通（实测 `hf-mirror.com` 在部分网络下会超时），改用 **ModelScope（魔搭）** 下载后
  把 `EMBEDDING_MODEL` 指向本地目录，见下。

  ```bash
  # 1) 从魔搭下载（国内可达）
  venv\Scripts\python.exe -m pip install modelscope
  venv\Scripts\python.exe -c "from modelscope import snapshot_download; print(snapshot_download('BAAI/bge-m3', cache_dir=r'D:\models\bge-m3'))"

  # 2) 把打印出的路径填进 backend/.env（注意用正斜杠或双反斜杠）
  #    EMBEDDING_MODEL=D:/models/bge-m3/models/BAAI--bge-m3/snapshots/master
  ```
- **提示 API Key 无效**：检查 `backend/.env` 的密钥与百炼平台开通情况。
- **端口被占用**：改 `start.bat` 的 `--port` 与 `frontend/vite.config.ts`。
- **换更便宜/更强的模型**：改 `.env` 的 `QWEN_MODEL`（`qwen-turbo` / `qwen-plus` / `qwen-max`）。
- **后端报「缺少必填配置 JWT_SECRET」**：按提示生成随机串写入 `backend/.env`。
- **报错提示某列不存在（如 `no such column: stored_path`）**：本项目**没有引入数据库迁移工具**，
  ORM 模型加字段后，旧库不会被自动改造。删除 **旧的开发库** 让其按新模型重建即可
  （会丢失已有的会话/文档记录，开发期数据可重灌）：

  ```bash
  # 从仓库根目录执行；务必先确认这是你自己的开发库
  rm backend/data/app.db
  ```

  相关取舍见 [ADR-0002](docs/adr/0002-sqlite-and-vector-store.md)。

---

## 六、测试与质量

### 实测数据

| 项目 | 数值 | 复现命令 |
|---|---|---|
| 后端单元测试 | **129 passed**（另 8 个集成/e2e 用例默认跳过） | `pytest -q` |
| 后端覆盖率 | **89%**（关键模块：`core/security` 100%、`routers/auth` 100%、`services/rag` 92%） | `pytest --cov=app --cov-report=term-missing` |
| 前端单元测试 | **85 passed**（13 个测试文件） | `npm test` |
| 前端覆盖率 | **语句 97.5% / 分支 87%** | `npm run test:coverage` |
| 后端静态检查 | `ruff check` 0 error、`ruff format --check` 通过 | `ruff check .` |
| 前端静态检查 | `eslint` 0 error、`prettier --check` 通过 | `npm run lint` |
| 生产构建 | `tsc && vite build` 通过 | `npm run build` |

### 一键跑全套检查

```bash
bash scripts/ci.sh        # 与 .github/workflows/ci.yml 完全一致的检查步骤
```

> **关于托管 CI 的实情**：本仓库托管在 **Gitee**，而 `.github/workflows/ci.yml` 是
> **GitHub Actions** 语法——Gitee 不会执行它。也就是说那份配置目前是「可移植的检查定义」，
> 而非正在运行的流水线。**实际的质量门禁是本地的 `scripts/ci.sh`**（上面那条命令），
> 它跑的就是同一套步骤。若要真在托管平台上自动化，需补一份 Gitee Go（`.workflow/`）配置。

### 关于集成测试

需要真实向量库 / 真实大模型调用（会联网、产生费用）的用例被标记为 `integration` / `e2e`，
**默认跳过、也不进 CI**，保证 CI 快且稳定。按需运行：

```bash
pytest -m integration    # 仅集成测试（需本地已准备数据）
pytest -m e2e            # 端到端（真实调用百炼，产生费用）
```

### 质量门禁（加分项）

项目自建了一套**提交前质量门禁**：提交前并行跑「单元测试」与「质量检查」两个子代理，
都通过才放行，且通过票与**代码指纹**绑定——检查后代码若再被改动，票自动作废。
详见 [docs/gate.md](docs/gate.md) 与 [ADR-0005](docs/adr/0005-claude-quality-gate.md)。

---

## 七、性能

> **重要：以下数据区分「真实模式」与「mock 模式」，请勿混用。**
> mock 模式下问答使用假大模型并跳过远程重排，只测「SQLite + bge-m3 向量化 + Chroma 检索」这层本地骨架。

### 单请求延迟（串行，含大模型与远程重排）

「首字延迟」拆成三个数，因为它们回答的是不同问题：服务端要先完成「追问改写 → 向量检索 → 重排」
才会发出首个 SSE 事件，所以**到首个事件的时间**衡量检索链路，**到首个 `token` 的时间**才是
用户感知的「等多久开始出字」。

| 场景 | 检索链路耗时 | **首字延迟** | 总时长 |
|---|---:|---:|---:|
| 首轮提问（新会话、无历史） | 0.20 s | **0.60 s** | 2.4–5.2 s |
| 同会话追问（有历史，多一次改写调用） | 0.91 s | **1.28 s** | 1.7–4.4 s |

追问比首轮慢近一倍：有历史时「追问改写」会真实调用一次大模型。复现：

```bash
# 后端已启动且 bge-m3 就位；脚本会自动上传示例文档并在结束时清理
venv\Scripts\python.exe loadtest\measure_latency.py --doc loadtest\sample_doc.md
```

> 以上为单机、CPU 推理、串行单请求的数字。**并发下会显著恶化**，见下方压测。

### 真实端到端（8 并发用户，含大模型与远程重排）

| 接口 | 请求数 | 错误率 | 平均 | P95 | P99 |
|---|---:|---:|---:|---:|---:|
| POST `/api/chat` | 181 | 0% | **2.9 s** | 5.7 s | 7.7 s |

### mock 骨架（100 并发用户，压系统自身承载）

| 接口 | 请求数 | 错误率 | 平均 | P95 | P99 |
|---|---:|---:|---:|---:|---:|
| POST `/api/chat` | 827 | 0.12% | **14.4 s** | 34 s | 37 s |

**结论（如实陈述）**：系统在 100 并发下不崩溃、总错误率 0.19%；
但延迟随并发显著恶化，瓶颈在**共享线程池 + 单实例 CPU 向量化 + SQLite 单写者**。

完整压测环境、方法与瓶颈分析见 **[loadtest/report.md](loadtest/report.md)**；
按 [loadtest/README.md](loadtest/README.md) 可自行复现两轮测试。

---

## 八、关键设计决策

每个「为什么不那样做」都记录成 ADR（架构决策记录），便于回溯：

| 决策 | ADR |
|---|---|
| 分层单体架构与技术选型（含为何不用组件库、为何本地向量模型） | [ADR-0001](docs/adr/0001-architecture-and-tech-stack.md) |
| 保留 SQLite + Chroma（含为何不引 Alembic、schema 变更如何处理） | [ADR-0002](docs/adr/0002-sqlite-and-vector-store.md) |
| JWT 双令牌鉴权（含 bcrypt 72 字节限制的 SHA256 预哈希） | [ADR-0003](docs/adr/0003-jwt-dual-token-auth.md) |
| SSE 流式输出（断开检测 / 失败兜底落库 / 错误脱敏） | [ADR-0004](docs/adr/0004-sse-streaming-and-error-handling.md) |
| 自建 Claude 质量门禁（代码指纹 + githooks） | [ADR-0005](docs/adr/0005-claude-quality-gate.md) |

几个值得单独说的点：

- **回答必须可溯源**：检索不到合格片段时，宁可回答「知识库中没有相关内容」，也不编造。
- **重排及格线兜底**：重排把所有候选都筛空时，强制保留相关度最高的第一名——
  这道逻辑来自压测中发现的一个真实 bug（详见压测报告附录）。
- **删除级联**：删除知识文档同时清理向量库中的块与磁盘上的物理文件，不留孤儿数据。
- **错误脱敏**：SSE 异常只回传统一文案 + 错误码，真实堆栈仅落服务端日志。
- **配置不写死**：密钥、管理员密码、CORS 来源全部走环境变量，代码内无任何硬编码凭据。

---

## 九、项目结构

```
vibecoding_langchain/
├── backend/
│   ├── app/
│   │   ├── routers/        # HTTP 层：auth / chat(含 SSE) / knowledge
│   │   ├── services/       # 业务层：rag / loader / splitter / embeddings / vectorstore
│   │   ├── core/           # 基础设施：security(JWT+bcrypt) / deps(鉴权依赖)
│   │   ├── models.py       # ORM 模型
│   │   ├── schemas.py      # 出入参校验
│   │   ├── config.py       # 集中配置（读 .env）
│   │   ├── database.py     # 引擎与会话（SQLite WAL）
│   │   ├── logging_config.py
│   │   └── main.py         # 入口
│   ├── tests/              # pytest 用例（单测 + 集成/e2e，默认跳过后两者）
│   ├── requirements.txt    # 运行依赖（版本锁定）
│   ├── requirements-dev.txt# 开发/测试依赖
│   └── pyproject.toml      # ruff 配置
├── frontend/
│   └── src/
│       ├── pages/          # 页面：Chat / Knowledge / Login / Register / Profile
│       ├── components/     # RequireAuth 路由守卫
│       ├── lib/            # api / auth / sse / errors / ui / types
│       └── styles/         # base(设计变量) / components / pages
├── loadtest/               # Locust 压测脚本与报告、首字延迟测量脚本
├── scripts/                # ci.sh（质量总检）、gate.mjs（提交门禁）
├── docs/                   # ADR、门禁说明、改造规划（历史存档）
├── .claude/                # Claude 子代理与技能（质量门禁工具链）
├── CONTEXT.md              # 领域术语表
├── setup.bat / start.bat   # Windows 一键安装 / 启动
└── .github/workflows/ci.yml# CI 定义
```

---

## 十、局限与展望

诚实说明当前边界（这些不是 bug，是有意识的取舍）：

1. **单机部署，未容器化**：无 Docker / docker-compose，横向扩展能力有限。
2. **SQLite 不适合高并发写**：已开 WAL 缓解，但定位仍是单机演示/个人项目；
   要上生产应换 PostgreSQL + 连接池。
3. **无数据库迁移工具**：ORM 模型变更需删除本地 `app.db` 重建（开发期数据可重灌），
   引入 Alembic 的成本对当前规模不划算。见 [ADR-0002](docs/adr/0002-sqlite-and-vector-store.md)。
4. **向量化是单实例 CPU 推理**：并发下是主要瓶颈；可改进程池或 GPU 推理。
5. **外部 API 无超时/重试/限流**：百炼变慢时会连锁拖慢整体，可加信号量与退避重试。
6. **未实现 refresh token 服务端吊销**：登出为前端丢弃令牌，服务端无法主动使令牌失效。
7. **无 i18n / 深色模式 / 细粒度权限模型**：有意不做，避免范围蔓延。

性能瓶颈的完整分析与优化优先级见 [loadtest/report.md](loadtest/report.md) 第 5、6 节。

---

## 十一、相关文档

| 文档 | 内容 |
|---|---|
| [CONTEXT.md](CONTEXT.md) | 领域术语表与关键边界（改代码前先读） |
| [docs/adr/](docs/adr/) | 架构决策记录 |
| [docs/gate.md](docs/gate.md) | 质量门禁使用说明 |
| [loadtest/report.md](loadtest/report.md) | 压测报告 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 开发与提交约定 |
| [CHANGELOG.md](CHANGELOG.md) | 变更记录 |
| [docs/改造规划书.md](docs/改造规划书.md) | 项目质量改造的规划（历史存档） |

---

## 十二、License

[MIT](LICENSE)