#!/usr/bin/env bash
#
# 项目质量总检：本地与任意 CI 都用这一套步骤。
# 与 .github/workflows/ci.yml 中的命令保持一致，改一处要同时改另一处。
#
# 用法（在仓库根目录执行）：
#   bash scripts/ci.sh                     # 自动寻找 venv/
#   PYTHON=/path/to/python bash scripts/ci.sh   # 手动指定解释器
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 优先级：环境变量 PYTHON > 仓库内虚拟环境 > PATH 里的 python
if [[ -n "${PYTHON:-}" ]]; then
  PY="$PYTHON"
elif [[ -x "$ROOT/venv/Scripts/python.exe" ]]; then
  PY="$ROOT/venv/Scripts/python.exe"   # Windows 虚拟环境
elif [[ -x "$ROOT/venv/bin/python" ]]; then
  PY="$ROOT/venv/bin/python"           # Linux / macOS 虚拟环境
else
  PY="python"
fi

step() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

step "后端：格式检查（ruff format --check）"
(cd "$ROOT/backend" && "$PY" -m ruff format --check .)

step "后端：静态检查（ruff check）"
(cd "$ROOT/backend" && "$PY" -m ruff check .)

step "后端：单元测试 + 覆盖率（pytest，阈值 70%）"
(cd "$ROOT/backend" && "$PY" -m pytest --cov=app --cov-report=term-missing --cov-fail-under=70)

step "前端：格式检查（prettier --check）"
(cd "$ROOT/frontend" && npm run format:check)

step "前端：静态检查（eslint）"
(cd "$ROOT/frontend" && npm run lint)

step "前端：单元测试 + 覆盖率（vitest）"
(cd "$ROOT/frontend" && npm run test:coverage)

step "前端：类型检查与生产构建（tsc + vite build）"
(cd "$ROOT/frontend" && npm run build)

printf '\n\033[32m全部检查通过 ✅\033[0m\n'