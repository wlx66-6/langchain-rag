/**
 * 轻量交互反馈：toast 提示 + 确认对话框，替代 window.alert / window.confirm。
 *
 * 为什么不用原生弹窗：它们是阻塞式的，会冻结整个页面渲染，样式也无法与项目统一；
 * 而这套自研组件只有几十行，不引入任何第三方依赖。
 */
import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react'

export type ToastKind = 'success' | 'error' | 'info'

interface ToastItem {
  id: number
  kind: ToastKind
  text: string
}

interface UiContextValue {
  toast: (text: string, kind?: ToastKind) => void
  /** 弹出确认框，用户点「确定」返回 true，点「取消」或按 Esc 返回 false */
  confirm: (message: string) => Promise<boolean>
}

const UiContext = createContext<UiContextValue | null>(null)

const TOAST_DURATION = 3000

export function UiProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const [pending, setPending] = useState<string | null>(null)
  const nextId = useRef(0)
  const resolver = useRef<((ok: boolean) => void) | null>(null)

  const toast = useCallback((text: string, kind: ToastKind = 'info') => {
    const id = nextId.current++
    setToasts((prev) => [...prev, { id, kind, text }])
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), TOAST_DURATION)
  }, [])

  const confirm = useCallback((message: string) => {
    setPending(message)
    return new Promise<boolean>((resolve) => {
      resolver.current = resolve
    })
  }, [])

  const settle = useCallback((ok: boolean) => {
    resolver.current?.(ok)
    resolver.current = null
    setPending(null)
  }, [])

  return (
    <UiContext.Provider value={{ toast, confirm }}>
      {children}

      <div className="toast-container" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.kind}`}>
            {t.text}
          </div>
        ))}
      </div>

      {pending !== null && (
        <div className="modal-mask" onClick={() => settle(false)}>
          <div
            className="modal-card"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.key === 'Escape' && settle(false)}
          >
            <div className="modal-text">{pending}</div>
            <div className="modal-actions">
              <button className="btn" onClick={() => settle(false)}>
                取消
              </button>
              <button className="btn btn-danger" onClick={() => settle(true)} autoFocus>
                确定
              </button>
            </div>
          </div>
        </div>
      )}
    </UiContext.Provider>
  )
}

export function useUi(): UiContextValue {
  const ctx = useContext(UiContext)
  if (!ctx) throw new Error('useUi 必须在 UiProvider 内使用')
  return ctx
}