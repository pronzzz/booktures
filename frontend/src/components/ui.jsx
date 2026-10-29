import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { CircleCheck, CircleX, LoaderCircle, X } from 'lucide-react'

export function cx(...parts) {
  return parts.filter(Boolean).join(' ')
}

const BUTTON = {
  primary: 'bg-ember text-ink-950 hover:bg-ember-bright shadow-[0_8px_30px_-12px_rgb(229_165_91/0.7)]',
  secondary: 'bg-ink-800 text-paper hover:bg-ink-700 border border-ink-600/70',
  ghost: 'text-paper-dim hover:text-paper hover:bg-ink-800/80',
  danger: 'text-rose hover:bg-rose/10 border border-rose/30',
}

export function Button({ variant = 'secondary', size = 'md', busy, icon: Icon, children, className, ...props }) {
  const sizes = { sm: 'h-8 px-3 text-[13px] gap-1.5', md: 'h-10 px-4 text-sm gap-2', lg: 'h-12 px-6 text-[15px] gap-2.5' }
  return (
    <button
      {...props}
      disabled={props.disabled || busy}
      className={cx(
        'inline-flex items-center justify-center rounded-full font-medium transition-all duration-150',
        'disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98] whitespace-nowrap',
        sizes[size],
        BUTTON[variant],
        className,
      )}
    >
      {busy ? <LoaderCircle className="size-4 animate-spin" /> : Icon ? <Icon className="size-4" /> : null}
      {children}
    </button>
  )
}

export function IconButton({ icon: Icon, label, active, className, ...props }) {
  return (
    <button
      {...props}
      aria-label={label}
      title={label}
      className={cx(
        'inline-flex size-9 items-center justify-center rounded-full transition-colors',
        active ? 'bg-ink-700 text-ember' : 'text-paper-dim hover:text-paper hover:bg-ink-800',
        className,
      )}
    >
      <Icon className="size-[18px]" />
    </button>
  )
}

const STATUS = {
  queued: ['Queued', 'bg-ink-700 text-paper-dim'],
  analyzing: ['Reading', 'bg-sea/15 text-sea'],
  illustrating: ['Painting', 'bg-ember/15 text-ember'],
  done: ['Illustrated', 'bg-sea/15 text-sea'],
  failed: ['Needs attention', 'bg-rose/15 text-rose'],
  cancelled: ['Paused', 'bg-ink-700 text-paper-dim'],
  interrupted: ['Interrupted', 'bg-ink-700 text-paper-dim'],
}

export function StatusPill({ status, className }) {
  const [label, tone] = STATUS[status] || [status, 'bg-ink-700 text-paper-dim']
  const live = ['analyzing', 'illustrating', 'queued'].includes(status)
  return (
    <span className={cx('inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider', tone, className)}>
      {live && <span className="size-1.5 rounded-full bg-current animate-pulse" />}
      {label}
    </span>
  )
}

export function Progress({ value, className }) {
  return (
    <div className={cx('h-1 w-full overflow-hidden rounded-full bg-ink-700', className)}>
      <div
        className="h-full rounded-full bg-gradient-to-r from-ember to-ember-bright transition-[width] duration-700 ease-out"
        style={{ width: `${Math.max(2, Math.min(100, value * 100))}%` }}
      />
    </div>
  )
}

export function Badge({ children, tone = 'default', className }) {
  const tones = {
    default: 'bg-ink-700/80 text-paper-dim',
    local: 'bg-sea/12 text-sea',
    cloud: 'bg-ember/12 text-ember',
    warn: 'bg-rose/12 text-rose',
  }
  return (
    <span className={cx('inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide', tones[tone], className)}>
      {children}
    </span>
  )
}

export function Field({ label, help, children }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[13px] font-medium text-paper">{label}</span>
      {children}
      {help && <span className="mt-1.5 block text-xs leading-relaxed text-muted">{help}</span>}
    </label>
  )
}

export const inputClass =
  'w-full rounded-xl border border-ink-600/80 bg-ink-900 px-3.5 py-2.5 text-sm text-paper placeholder:text-muted/70 ' +
  'outline-none transition focus:border-ember/70 focus:ring-2 focus:ring-ember/20'

export function Drawer({ open, onClose, title, children, width = 'max-w-md' }) {
  useEffect(() => {
    if (!open) return
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])
  return (
    <div className={cx('fixed inset-0 z-50 transition', open ? 'pointer-events-auto' : 'pointer-events-none')} aria-hidden={!open}>
      <div className={cx('absolute inset-0 bg-black/50 backdrop-blur-[2px] transition-opacity', open ? 'opacity-100' : 'opacity-0')} onClick={onClose} />
      <aside
        role="dialog"
        aria-label={title}
        className={cx(
          'absolute right-0 top-0 flex h-full w-full flex-col border-l border-ink-700 bg-ink-900 shadow-2xl transition-transform duration-300',
          width,
          open ? 'translate-x-0' : 'translate-x-full',
        )}
      >
        <div className="flex items-center justify-between border-b border-ink-700 px-5 py-4">
          <h2 className="font-display text-lg">{title}</h2>
          <IconButton icon={X} label="Close" onClick={onClose} />
        </div>
        <div className="thin-scroll flex-1 overflow-y-auto">{children}</div>
      </aside>
    </div>
  )
}

const ToastCtx = createContext(() => {})

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const id = useRef(0)
  const push = useCallback((message, tone = 'ok') => {
    const t = { id: ++id.current, message, tone }
    setToasts((all) => [...all, t])
    setTimeout(() => setToasts((all) => all.filter((x) => x.id !== t.id)), tone === 'error' ? 6500 : 3200)
  }, [])
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed bottom-5 left-1/2 z-[60] flex w-[min(92vw,26rem)] -translate-x-1/2 flex-col gap-2" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className="pointer-events-auto flex items-start gap-2.5 rounded-2xl border border-ink-600 bg-ink-800/95 px-4 py-3 text-sm shadow-xl backdrop-blur">
            {t.tone === 'error' ? <CircleX className="mt-0.5 size-4 shrink-0 text-rose" /> : <CircleCheck className="mt-0.5 size-4 shrink-0 text-sea" />}
            <span className="leading-snug">{t.message}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

export const useToast = () => useContext(ToastCtx)
