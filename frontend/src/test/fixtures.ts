/**
 * 构造一个「像 axios 失败那样」的错误对象，让 `errorMessage()` 能识别出后端返回的 detail。
 * axios 用 `isAxiosError` 标记自己的错误，这里如实模拟，避免测试与真实链路有偏差。
 */
export function apiError(detail: string, status = 400): Error {
  return Object.assign(new Error(detail), {
    isAxiosError: true,
    response: { status, data: { detail } },
  })
}
