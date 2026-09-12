// 存档门禁脚本：计算代码指纹、写/验「通过票」、安装钩子。
// 用法：node scripts/gate.mjs <fingerprint | mark <test|quality> [摘要] | check | reset | install>

import { createHash } from 'node:crypto'
import { execSync } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

// 统一在项目根目录下操作（无论从哪运行）
const root = execSync('git rev-parse --show-toplevel', { encoding: 'utf8' }).trim()
process.chdir(root)

const GATES_DIR = '.claude/gates'

/** 计算「代码指纹」：仓库里所有「正式文件」（已跟踪 + 未跟踪但未被忽略）的内容哈希，自动排除 node_modules/dist/out 等被忽略项 */
function computeFingerprint() {
  // 列出全部「正式文件」：已跟踪 + 未跟踪但未被忽略（等价于 git add -A 会纳入的内容），
  // 并自动排除 node_modules/dist/out/.claude/gates 等被忽略项
  const files = execSync('git ls-files --cached --others --exclude-standard', { encoding: 'utf8' })
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean)
    // 测试报告是每次跑测试都会变的「生成物」，不算指纹，否则并行检查时会被它的改动干扰
    .filter((f) => f !== 'test-report.md')
    .sort()
  const hash = createHash('sha256')
  for (const f of files) {
    hash.update(f).update('\0')
    if (existsSync(f)) {
      // 统一换行符（去掉 \r），避免 Windows 上 CRLF/LF 差异导致误判「代码变了」
      hash.update(readFileSync(f, 'utf8').replace(/\r/g, ''))
    }
    hash.update('\0')
  }
  return hash.digest('hex')
}

const KIND_LABEL = { test: '单元测试', quality: '质量检查' }

/** 写一张「通过票」到 .claude/gates/<kind>.pass.json */
function mark(kind, summary) {
  if (!KIND_LABEL[kind]) {
    console.error('✗ kind 只能是 test 或 quality')
    process.exit(2)
  }
  const fingerprint = computeFingerprint()
  mkdirSync(GATES_DIR, { recursive: true })
  const file = join(GATES_DIR, `${kind}.pass.json`)
  writeFileSync(
    file,
    JSON.stringify({ kind, status: 'pass', fingerprint, at: new Date().toISOString(), summary }, null, 2) + '\n'
  )
  console.log(`✅ 已写「${KIND_LABEL[kind]}」通过票：${file}（指纹 ${fingerprint.slice(0, 8)}…）`)
}

/** 验票：两张票都在、都通过、指纹都与当前一致 → 退出码 0；否则 1 */
function check() {
  const fingerprint = computeFingerprint()
  let ok = true
  for (const kind of ['test', 'quality']) {
    const label = KIND_LABEL[kind]
    const file = join(GATES_DIR, `${kind}.pass.json`)
    if (!existsSync(file)) {
      console.error(`⛔ 缺少「${label}」通过票：${file}`)
      ok = false
      continue
    }
    let data
    try {
      data = JSON.parse(readFileSync(file, 'utf8'))
    } catch {
      console.error(`⛔ 「${label}」通过票内容损坏，请重跑检查`)
      ok = false
      continue
    }
    if (data.status !== 'pass') {
      console.error(`⛔ 「${label}」结果为未通过`)
      ok = false
      continue
    }
    if (data.fingerprint !== fingerprint) {
      console.error(`⛔ 「${label}」通过票已过期（代码在检查后又改动了），请重跑`)
      ok = false
      continue
    }
    console.log(`✅ 「${label}」通过票有效${data.summary ? `（${data.summary}）` : ''}`)
  }
  if (!ok) {
    console.error('\n请先让 gitcommit-agent 跑完 tester 与 quality-engineer 再提交。')
    process.exit(1)
  }
  console.log('\n🎉 门禁通过，允许存档。')
}

/** 销票：清空所有通过票（由 post-commit 钩子在提交成功后调用，防止旧票被下一笔提交复用） */
function reset() {
  rmSync(GATES_DIR, { recursive: true, force: true })
  console.log('🧹 通行证已清空：下次提交需重新通过单元测试 + 质量检查')
}

/** 安装钩子：把 hooks 目录指向仓库内的 .githooks/（换电脑也不会丢） */
function install() {
  execSync('git config core.hooksPath .githooks', { stdio: 'inherit' })
  console.log('✅ 已设置 core.hooksPath = .githooks')
}

const [cmd, arg1, arg2] = process.argv.slice(2)
switch (cmd) {
  case 'fingerprint':
    console.log(computeFingerprint())
    break
  case 'mark':
    mark(arg1, arg2 ?? '')
    break
  case 'check':
    check()
    break
  case 'reset':
    reset()
    break
  case 'install':
    install()
    break
  default:
    console.log('用法：node scripts/gate.mjs <fingerprint | mark <test|quality> [摘要] | check | reset | install>')
    process.exit(2)
}