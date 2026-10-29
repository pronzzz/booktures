import { useEffect, useState } from 'react'
import { BookOpen, Library as LibraryIcon, Settings as SettingsIcon } from 'lucide-react'
import { api } from './api'
import { go, useRoute } from './hooks'
import { cx, ToastProvider } from './components/ui'
import Library from './components/Library'
import Reader from './components/Reader'
import Settings from './components/Settings'

export function Logo({ className }) {
  return (
    <a href="#/" className={cx('group inline-flex items-center gap-2.5', className)}>
      <img src="/favicon.svg" alt="" className="size-8 rounded-lg transition-transform group-hover:-rotate-6" />
      <span className="font-display text-[22px] font-semibold tracking-tight">
        Book<span className="text-ember">tures</span>
      </span>
    </a>
  )
}

function NavLink({ href, active, icon: Icon, children }) {
  return (
    <a
      href={href}
      className={cx(
        'inline-flex items-center gap-2 rounded-full px-3.5 py-2 text-sm transition-colors',
        active ? 'bg-ink-800 text-paper' : 'text-paper-dim hover:text-paper',
      )}
    >
      <Icon className="size-4" />
      <span className="hidden sm:inline">{children}</span>
    </a>
  )
}

function Shell({ route, children, active }) {
  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-30 border-b border-ink-800/80 bg-ink-950/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
          <Logo />
          <nav className="flex items-center gap-1">
            <NavLink href="#/" active={route[0] !== 'settings'} icon={LibraryIcon}>Library</NavLink>
            <NavLink href="#/settings" active={route[0] === 'settings'} icon={SettingsIcon}>Models &amp; plugins</NavLink>
            {active && (
              <a
                href="#/settings"
                className="ml-2 hidden items-center gap-2 rounded-full border border-ink-700 px-3 py-1.5 text-xs text-paper-dim hover:border-ink-600 lg:inline-flex"
                title="Active story model and illustrator"
              >
                <BookOpen className="size-3.5 text-ember" />
                {active.text} <span className="text-muted">+</span> {active.image}
              </a>
            )}
          </nav>
        </div>
      </header>
      {children}
    </div>
  )
}

export default function App() {
  const route = useRoute()
  const [active, setActive] = useState(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (route[0] === 'book') return
    api
      .providers()
      .then((cat) => {
        const name = (kind) => cat[kind].find((p) => p.id === cat.active[kind])?.name || cat.active[kind]
        setActive({ text: name('text'), image: name('image') })
      })
      .catch(() => {})
  }, [route, tick])

  let page
  if (route[0] === 'book' && route[1]) page = <Reader id={route[1]} onBack={() => go('/')} />
  else if (route[0] === 'settings') page = <Shell route={route} active={active}><Settings onSaved={() => setTick((t) => t + 1)} /></Shell>
  else page = <Shell route={route} active={active}><Library /></Shell>

  return <ToastProvider>{page}</ToastProvider>
}
