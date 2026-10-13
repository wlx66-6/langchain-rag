# 质量门禁（gate）使用说明

本项目的提交被一道自建的「质量门禁」把关：**单元测试 + 质量检查都通过，才允许提交**。
本文说明它怎么工作、怎么用、出问题怎么办。设计动机见 [ADR-0005](./adr/0005-claude-quality-gate.md)。

---

## 1. 它由什么组成

| 文件 | 作用 |
|---|---|
| `.claude/agents/gitcommit-agent.md` | 编排者：**并行**派出下面两个子代理，都通过后才提交 |
| `.claude/agents/tester.md` | 跑后端 pytest + 前端 Vitest，全绿后写「单元测试通过票」 |
| `.claude/agents/quality-engineer.md` | 安全审计 / 注释检查 / 其它质量检查，无严重问题写「质量通过票」 |
| `scripts/gate.mjs` | 写票 / 验票 / 销票 / 安装钩子 |
| `.githooks/pre-commit` | 提交前调 `gate.mjs check` 验票，不过就**拦截提交** |
| `.githooks/post-commit` | 提交成功后调 `gate.mjs reset` **销票**（一提交一票，防止复用） |

---

## 2. 核心概念：代码指纹

`gate.mjs` 会对仓库内所有「正式文件」（已跟踪 + 未跟踪但未被忽略的内容）做一次 SHA256，
得到一个**代码指纹**，并把它写进「通过票」里。

验票时会**重新计算指纹并与票上的比对**：

- 指纹一致 → 票有效，代码自检查后没被动过，放行；
- 指纹不一致 → 票**过期作废**，必须重新检查。

这条机制专门堵一个漏洞：**测试通过之后又偷偷改了代码**。

> 生成物（`test-report.md`、覆盖率目录等）不计入指纹——否则「跑个测试」就把票顶掉了。

---

## 3. 日常怎么用

### 首次使用：安装钩子（只需一次）

```bash
node scripts/gate.mjs install      # 等价于 git config core.hooksPath .githooks
```

`core.hooksPath` 指向仓库内的 `.githooks/`，所以**换台电脑克隆后要再执行一次**
（`.git/` 目录不入库，钩子若不这样设置就会丢）。

### 正常提交

不用手动跑脚本，直接把「提交」交给 `gitcommit-agent` 即可，它会：

1. 并行跑 tester 与 quality-engineer；
2. `node scripts/gate.mjs check` 验票；
3. 通过 → 按 Conventional Commits 规范提交；不通过 → 拦住并说明原因。

### 手动查看 / 调试

```bash
node scripts/gate.mjs fingerprint        # 打印当前代码指纹
node scripts/gate.mjs mark test "129 个用例全部通过"   # 手动写票（一般由子代理调用）
node scripts/gate.mjs mark quality "无严重问题"
node scripts/gate.mjs check              # 验票（退出码 0 = 通过，1 = 拦截）
node scripts/gate.mjs reset              # 清空所有票
```

退出码约定：`0` 通过、`1` 被拦截、`2` 用法错误。

---

## 4. 出问题怎么办

| 现象 | 原因 | 处理 |
|---|---|---|
| 提交被拦，提示「缺少通过票」 | 没跑检查，或票已被上一笔提交销掉 | 让 `gitcommit-agent` 重跑，或先跑 tester/quality-engineer |
| 提示「通过票已过期」 | 检查之后代码又改了 | 重新跑检查生成新票 |
| 提示「结果未通过」 | tester 有失败用例 / quality 报了 🔴 严重问题 | 先修问题，别想着绕过 |
| 钩子完全没生效（改了代码也能直接提交） | `.githooks` 没启用 | `node scripts/gate.mjs install` |
| 紧急必须提交 | —— | `git commit --no-verify`（**慎用**，属于例外） |

---

## 5. 与业务代码的关系

**门禁是辅助工具链，与业务代码解耦。** 删除 `.claude/`、`.githooks/`、`scripts/gate.mjs`
之后，项目依然可以正常安装、测试、构建、运行——因为真正的质量证据来自
`pytest` / `vitest` / `ruff` / `eslint` 这些标准工具（见 `scripts/ci.sh` 与
`.github/workflows/ci.yml`）。

门禁的价值在于**把「跑检查」这件事和「提交」这个动作绑定**，而不是替代标准工具。