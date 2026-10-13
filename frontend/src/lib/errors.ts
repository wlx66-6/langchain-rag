import axios from 'axios'

/**
 * 把任意异常转成一句能给用户看的提示。
 *
 * 后端出错时会返回 `{ detail: "..." }`，优先用它；否则按网络层情况给通用文案。
 * 入参类型是 `unknown`，因为 `catch` 捕获到什么都可能，不能假设是 Error。
 */
export function errorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string' && detail) return detail
    if (!err.response) return '网络异常，请确认后端服务已启动'
    return fallback
  }
  if (err instanceof Error && err.message) return err.message
  return fallback
}