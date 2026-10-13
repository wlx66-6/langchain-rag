// ESLint 扁平配置（ESLint 9+ 的默认格式）。
// 规则来源：typescript-eslint 推荐规则 + React Hooks 规则 + Vite 的 HMR 规则。
import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import prettier from 'eslint-config-prettier'

export default tseslint.config(
  // 构建产物与依赖目录不检查
  { ignores: ['dist', 'coverage', 'node_modules'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      // 用 unknown + 类型守卫代替 any，逐步收紧
      '@typescript-eslint/no-explicit-any': 'warn',
      // 未使用的变量报错（下划线前缀表示有意忽略）
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      // 该规则无法识别「在 effect 里调用异步函数拉数据」这种正常写法，
      // 会把 refresh() 里 await 之后的 setState 误判为同步调用，故关闭。
      'react-hooks/set-state-in-effect': 'off',
    },
  },
  // 测试文件里允许直接使用断言与 mock
  {
    files: ['**/*.test.{ts,tsx}', 'src/test/**'],
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
    },
  },
  // 放在最后：关掉所有与 Prettier 冲突的格式类规则
  prettier,
)