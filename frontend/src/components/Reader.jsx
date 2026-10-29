import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowLeft, ChevronLeft, ChevronRight, Columns2, Download, Film, Info, LoaderCircle, Minimize2, Moon,
  Palette, Pencil, Play, Plus, RefreshCw, Repeat, ScrollText, Square, Sun, Trash2, TriangleAlert, Users,
} from 'lucide-react'
import { ACTIVE, api } from '../api'
import { useLiveBook, useLocalSetting } from '../hooks'
import { StylePicker } from './Library'
import { Badge, Button, cx, Drawer, IconButton, inputClass, Progress, StatusPill, useToast } from './ui'

const THEMES = ['night', 'sepia', 'paper']
const SIZES = [16, 18, 20, 22, 25]

function ImageStage({ src, alt, kenburns, className }) {
  const [layers, setLayers] = useState(src ? [src] : [])
  useEffect(() => {
    if (src) setLayers((l) => (l[l.length - 1] === src ? l : [...l.slice(-1), src]))
  }, [src])
  return (
    <div className={cx('absolute inset-0 overflow-hidden', className)}>
      {layers.map((u, i) => (
        <img
          key={u}
          src={u}
          alt={i === layers.length - 1 ? alt : ''}
          className={cx(
            'absolute inset-0 size-full object-cover transition-opacity duration-700',
            i === layers.length - 1 ? 'opacity-100 animate-[fadein_.8s_ease]' : 'opacity-0',
            kenburns && 'kenburns',
          )}
        />
      ))}
      <style>{'@keyframes fadein{from{opacity:0}to{opacity:1}}'}</style>
    </div>
  )
}

function PagePlaceholder({ page, book }) {
  const painting = page?.image_status === 'painting'
  const failed = page?.image_status === 'failed'
  return (
    <div className={cx('absolute inset-0 grid place-items-center p-8 text-center', !failed && 'shimmer')}>
      <div className="max-w-sm">
        {failed ? (
          <>
            <TriangleAlert className="mx-auto mb-3 size-7 text-rose" />
            <p className="font-medium text-paper">This page could not be painted</p>
            <p className="mt-2 text-sm leading-relaxed text-paper-dim">{page.error}</p>
          </>
        ) : (
          <>
            <LoaderCircle className={cx('mx-auto mb-3 size-7 text-ember', painting && 'animate-spin')} />
            <p className="font-display text-xl text-paper">{painting ? `Painting page ${page.number}…` : 'Waiting for its turn'}</p>
            <p className="mt-2 text-sm text-paper-dim">{book?.message}</p>
          </>
        )}
      </div>
    </div>
  )
}

function StatusDot({ status }) {
  const tone = {
    done: 'bg-sea', reused: 'bg-sea/50', painting: 'bg-ember animate-pulse', failed: 'bg-rose', pending: 'bg-ink-600',
  }[status]
  return <span className={cx('inline-block size-1.5 rounded-full', tone)} title={status} />
}

function Paragraphs({ text }) {
  return text.split('\n\n').map((p, i) => (
    <p key={i} className="mb-[1.1em]">
      {p}
    </p>
  ))
}

/* ---------------------------------------------------------------- split view */

function SplitView({ book, current, setCurrent, theme, size, onPageTools, navRef }) {
  const scroller = useRef(null)
  const refs = useRef([])
  const lock = useRef(false)

  useEffect(() => {
    const root = scroller.current
    if (!root) return
    const io = new IntersectionObserver(
      (entries) => {
        if (lock.current) return
        for (const e of entries) if (e.isIntersecting) setCurrent(Number(e.target.dataset.index))
      },
      { root, rootMargin: '-40% 0px -55% 0px' },
    )
    refs.current.forEach((el) => el && io.observe(el))
    return () => io.disconnect()
  }, [book.pages.length, setCurrent])

  // Keyboard and toolbar navigation scroll the text to the chosen page.
  useEffect(() => {
    const el = refs.current[current]
    const root = scroller.current
    if (!el || !root) return
    const top = el.offsetTop - root.offsetTop
    const visible = root.scrollTop <= top && top < root.scrollTop + root.clientHeight * 0.6
    if (!visible && lock.current) root.scrollTo({ top: top - 24, behavior: 'smooth' })
  }, [current])

  const jump = (i) => {
    lock.current = true
    setCurrent(i)
    setTimeout(() => (lock.current = false), 700)
  }
  if (navRef) navRef.current = jump

  const page = book.pages[current]
  const reusedFrom = page?.image_status === 'reused' ? page.reused_from : null

  return (
    <div className="flex h-[calc(100dvh-57px)] flex-col-reverse lg:flex-row">
      <div
        ref={scroller}
        className={cx('thin-scroll flex-1 overflow-y-auto lg:w-1/2 lg:flex-none', `theme-${theme}`)}
        style={{ background: 'var(--r-bg)', color: 'var(--r-ink)' }}
      >
        <div className="mx-auto max-w-[40rem] px-5 pb-[45vh] pt-10 sm:px-10 lg:pt-16">
          <header className="mb-14">
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.25em]" style={{ color: 'var(--r-accent)' }}>
              {book.genre || 'An illustrated edition'}
            </p>
            <h1 className="font-display text-4xl font-medium leading-tight sm:text-5xl">{book.title}</h1>
            {book.author && <p className="mt-3 font-serif italic" style={{ color: 'var(--r-dim)' }}>{book.author}</p>}
          </header>
          {book.pages.map((p, i) => (
            <section
              key={p.number}
              data-index={i}
              ref={(el) => (refs.current[i] = el)}
              className="mb-16 scroll-mt-6"
            >
              <button
                onClick={() => {
                  jump(i)
                  onPageTools()
                }}
                className="mb-4 flex w-full items-center gap-3 text-[11px] font-semibold uppercase tracking-[0.2em] transition-opacity hover:opacity-80"
                style={{ color: i === current ? 'var(--r-accent)' : 'var(--r-dim)' }}
                title="Page details"
              >
                <StatusDot status={p.image_status} />
                Page {p.number}
                <span className="h-px flex-1" style={{ background: 'var(--r-line)' }} />
              </button>
              <div className="font-serif leading-[1.8] transition-opacity" style={{ fontSize: size, opacity: i === current ? 1 : 0.62 }}>
                <Paragraphs text={p.text} />
              </div>
            </section>
          ))}
          <p className="text-center font-display text-2xl" style={{ color: 'var(--r-dim)' }}>
            ❦
          </p>
        </div>
      </div>

      <div className="relative h-[40dvh] shrink-0 overflow-hidden border-ink-800 bg-black lg:h-auto lg:w-1/2 lg:border-l">
        {page?.image_url ? <ImageStage src={page.image_url} alt={page.scene_summary} /> : <PagePlaceholder page={page} book={book} />}
        {page?.image_url && page.image_status === 'painting' && (
          <div className="absolute right-4 top-4 inline-flex items-center gap-2 rounded-full bg-black/60 px-3 py-1.5 text-xs backdrop-blur">
            <LoaderCircle className="size-3.5 animate-spin text-ember" /> Repainting…
          </div>
        )}
        {page && (
          <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 via-black/55 to-transparent px-6 pb-6 pt-20 sm:px-8">
            <div className="mb-2.5 flex flex-wrap items-center gap-1.5">
              {page.characters.map((c) => (
                <span key={c} className="rounded-full bg-white/10 px-2.5 py-0.5 text-[11px] font-medium text-paper backdrop-blur">
                  {c}
                </span>
              ))}
              {reusedFrom && (
                <span className="inline-flex items-center gap-1 rounded-full bg-sea/20 px-2.5 py-0.5 text-[11px] text-sea">
                  <Repeat className="size-3" /> Same scene as page {reusedFrom}
                </span>
              )}
              {page.censored && <Badge tone="warn">Placeholder</Badge>}
            </div>
            <p className="line-clamp-3 max-w-2xl font-serif text-[15px] italic leading-relaxed text-paper/90">
              {page.scene_summary || 'Scene to come…'}
            </p>
          </div>
        )}
        <div className="absolute left-4 top-4 rounded-full bg-black/55 px-3 py-1.5 text-xs text-paper-dim backdrop-blur">
          {current + 1} / {book.pages.length}
        </div>
      </div>
    </div>
  )
}

/* -------------------------------------------------------------- cinema view */

function CinemaView({ book, current, setCurrent, onExit, size }) {
  const page = book.pages[current]
  const total = book.pages.length
  const box = useRef(null)
  useEffect(() => {
    box.current?.scrollTo(0, 0)
  }, [current])
  return (
    <div className="fixed inset-0 z-40 bg-black">
      {page?.image_url ? <ImageStage src={page.image_url} alt={page.scene_summary} kenburns /> : <PagePlaceholder page={page} book={book} />}
      <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-transparent to-black/40" />
      <button className="absolute inset-0 cursor-pointer" aria-label="Next page" onClick={() => setCurrent(Math.min(total - 1, current + 1))} />

      <div className="absolute inset-x-0 top-0 flex items-center justify-between p-4 sm:p-6">
        <div className="rounded-full bg-black/50 px-4 py-2 backdrop-blur">
          <span className="font-display">{book.title}</span>
          <span className="ml-3 text-xs text-paper-dim">
            {current + 1} / {total}
          </span>
        </div>
        <IconButton icon={Minimize2} label="Leave cinema mode (Esc)" onClick={onExit} className="bg-black/50 backdrop-blur" />
      </div>

      <IconButton
        icon={ChevronLeft}
        label="Previous page"
        onClick={() => setCurrent(Math.max(0, current - 1))}
        className="absolute left-3 top-1/2 size-12 -translate-y-1/2 bg-black/40 backdrop-blur sm:left-6"
      />
      <IconButton
        icon={ChevronRight}
        label="Next page"
        onClick={() => setCurrent(Math.min(total - 1, current + 1))}
        className="absolute right-3 top-1/2 size-12 -translate-y-1/2 bg-black/40 backdrop-blur sm:right-6"
      />

      <div className="absolute inset-x-0 bottom-0 p-3 sm:p-8">
        <div className="mx-auto max-w-3xl rounded-3xl border border-white/10 bg-black/55 shadow-2xl backdrop-blur-xl">
          <div className="flex items-center gap-2 border-b border-white/10 px-6 py-3">
            {page?.characters?.length ? (
              <span className="font-display text-[15px] text-ember">{page.characters.join(' · ')}</span>
            ) : (
              <span className="font-display text-[15px] text-paper-dim">Narrator</span>
            )}
            <span className="ml-auto text-[11px] uppercase tracking-[0.2em] text-paper-dim">Page {page?.number}</span>
          </div>
          <div ref={box} className="thin-scroll max-h-[34dvh] overflow-y-auto px-6 py-5 font-serif leading-[1.75] text-paper/95" style={{ fontSize: Math.max(16, size - 2) }}>
            {page && <Paragraphs text={page.text} />}
          </div>
        </div>
        <div className="mx-auto mt-3 flex max-w-3xl gap-1">
          {book.pages.map((p, i) => (
            <button
              key={p.number}
              aria-label={`Page ${p.number}`}
              onClick={() => setCurrent(i)}
              className={cx('h-1 flex-1 rounded-full transition-colors', i === current ? 'bg-ember' : i < current ? 'bg-white/40' : 'bg-white/15')}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

/* ----------------------------------------------------------- details drawer */

function RunTab({ book }) {
  const toast = useToast()
  const live = ACTIVE.includes(book.status)
  const remaining = book.counts.pending + book.counts.failed + book.counts.painting
  const act = async (fn, msg) => {
    try {
      await fn()
      if (msg) toast(msg)
    } catch (e) {
      toast(e.message, 'error')
    }
  }
  return (
    <div className="space-y-6 p-5">
      <div>
        <div className="mb-3 flex items-center justify-between">
          <StatusPill status={book.status} />
          <span className="text-xs text-muted">{Math.round(book.progress * 100)}%</span>
        </div>
        <Progress value={book.progress} />
        <p className="mt-3 text-sm text-paper-dim">{book.message}</p>
        {book.error && <p className="mt-3 rounded-xl border border-rose/30 bg-rose/10 p-3 text-sm text-rose">{book.error}</p>}
      </div>
      <dl className="grid grid-cols-2 gap-3 text-sm">
        {[
          ['Painted', book.counts.done],
          ['Reused scenes', book.counts.reused],
          ['Waiting', book.counts.pending + book.counts.painting],
          ['Failed', book.counts.failed],
        ].map(([k, v]) => (
          <div key={k} className="rounded-2xl border border-ink-700 bg-ink-850 p-3">
            <dt className="text-xs text-muted">{k}</dt>
            <dd className="mt-1 font-display text-2xl">{v}</dd>
          </div>
        ))}
      </dl>
      <div className="space-y-1.5 text-sm text-paper-dim">
        <p>
          Story model: <span className="text-paper">{book.text_provider || '—'}</span>
        </p>
        <p>
          Illustrator: <span className="text-paper">{book.image_provider || '—'}</span>
        </p>
      </div>
      {book.warnings?.length > 0 && (
        <ul className="space-y-2">
          {book.warnings.map((w) => (
            <li key={w} className="flex gap-2 rounded-xl bg-ink-850 p-3 text-xs leading-relaxed text-paper-dim">
              <Info className="size-4 shrink-0 text-ember" />
              {w}
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap gap-2">
        {live ? (
          <Button icon={Square} onClick={() => act(() => api.cancel(book.id), 'Pausing after this page')}>
            Pause
          </Button>
        ) : (
          remaining > 0 && (
            <Button variant="primary" icon={Play} onClick={() => act(() => api.run(book.id, 'resume'), 'Resuming')}>
              Resume ({remaining} left)
            </Button>
          )
        )}
        <Button
          icon={RefreshCw}
          disabled={live}
          onClick={() => window.confirm('Repaint every page with the current settings?') && act(() => api.run(book.id, 'repaint'), 'Repainting the whole book')}
        >
          Repaint all
        </Button>
        <Button
          icon={ScrollText}
          disabled={live}
          onClick={() =>
            window.confirm('Re-read the book from scratch? This rebuilds the character bible and style, then repaints everything.') &&
            act(() => api.run(book.id, 'reanalyze'), 'Reading the book again')
          }
        >
          Re-read book
        </Button>
        <a href={api.exportUrl(book.id)} download>
          <Button icon={Download}>Export HTML</Button>
        </a>
      </div>
    </div>
  )
}

function CastTab({ book, setBook }) {
  const toast = useToast()
  const [rows, setRows] = useState(() => Object.entries(book.character_bible))
  const [busy, setBusy] = useState(false)
  useEffect(() => setRows(Object.entries(book.character_bible)), [book.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const save = async () => {
    setBusy(true)
    try {
      const updated = await api.patchBook(book.id, { character_bible: Object.fromEntries(rows) })
      setBook(updated)
      toast('Character bible saved. New and repainted pages will use it.')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="space-y-4 p-5">
      <p className="text-sm leading-relaxed text-paper-dim">
        Every prompt that shows one of these characters gets their description, so they look the same on every page.
      </p>
      {rows.map(([name, desc], i) => (
        <div key={i} className="rounded-2xl border border-ink-700 bg-ink-850 p-3">
          <div className="mb-2 flex items-center gap-2">
            <input
              value={name}
              onChange={(e) => setRows(rows.map((r, j) => (j === i ? [e.target.value, r[1]] : r)))}
              className={cx(inputClass, 'font-display text-base')}
              aria-label="Character name"
            />
            <IconButton icon={Trash2} label="Remove character" onClick={() => setRows(rows.filter((_, j) => j !== i))} />
          </div>
          <textarea
            value={desc}
            rows={2}
            onChange={(e) => setRows(rows.map((r, j) => (j === i ? [r[0], e.target.value] : r)))}
            className={cx(inputClass, 'resize-y')}
            aria-label={`${name} description`}
          />
        </div>
      ))}
      <div className="flex gap-2">
        <Button icon={Plus} onClick={() => setRows([...rows, ['', '']])}>Add character</Button>
        <Button variant="primary" busy={busy} onClick={save}>Save</Button>
      </div>
    </div>
  )
}

function StyleTab({ book, setBook }) {
  const toast = useToast()
  const [styles, setStyles] = useState([])
  const [preset, setPreset] = useState(book.style_preset)
  const [custom, setCustom] = useState(book.custom_style)
  const [busy, setBusy] = useState('')
  useEffect(() => {
    api.styles().then(setStyles).catch(() => {})
  }, [])
  const save = async (repaint) => {
    setBusy(repaint ? 'repaint' : 'save')
    try {
      setBook(await api.patchBook(book.id, { style_preset: preset, custom_style: custom }))
      if (repaint) {
        await api.run(book.id, 'repaint')
        toast('Repainting every page in the new style')
      } else toast('Style saved')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setBusy('')
    }
  }
  return (
    <div className="space-y-5 p-5">
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">Locked style</p>
        <p className="rounded-2xl border border-ink-700 bg-ink-850 p-3 font-serif text-sm italic leading-relaxed text-paper-dim">{book.global_style || 'Decided when the book is first read.'}</p>
      </div>
      <StylePicker styles={styles} value={preset} onChange={setPreset} />
      <label className="block">
        <span className="mb-1.5 block text-[13px] font-medium">Custom style (overrides the preset)</span>
        <textarea
          rows={3}
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
          placeholder="e.g. 1950s pulp magazine cover, halftone dots, bold primaries"
          className={cx(inputClass, 'resize-y')}
        />
      </label>
      <div className="flex flex-wrap gap-2">
        <Button busy={busy === 'save'} onClick={() => save(false)}>Save</Button>
        <Button variant="primary" icon={RefreshCw} busy={busy === 'repaint'} disabled={ACTIVE.includes(book.status)} onClick={() => save(true)}>
          Save &amp; repaint all
        </Button>
      </div>
    </div>
  )
}

function PageTab({ book, current }) {
  const toast = useToast()
  const page = book.pages[current]
  const [override, setOverride] = useState(page?.prompt_override || '')
  const [busy, setBusy] = useState(false)
  useEffect(() => setOverride(page?.prompt_override || ''), [page?.number, page?.prompt_override])
  if (!page) return null
  const repaint = async (value) => {
    setBusy(true)
    try {
      await api.regenerate(book.id, page.number, value)
      toast(`Repainting page ${page.number}`)
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="space-y-5 p-5">
      <div className="flex items-center gap-2">
        <h3 className="font-display text-2xl">Page {page.number}</h3>
        <StatusDot status={page.image_status} />
        <span className="text-xs text-muted">{page.image_status}</span>
      </div>
      {page.scene_summary && (
        <div>
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted">Scene</p>
          <p className="text-sm leading-relaxed text-paper-dim">{page.scene_summary}</p>
        </div>
      )}
      {page.image_prompt && (
        <div>
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted">Prompt sent to the illustrator</p>
          <p className="rounded-2xl border border-ink-700 bg-ink-850 p-3 font-mono text-[12px] leading-relaxed text-paper-dim">{page.image_prompt}</p>
        </div>
      )}
      {page.error && <p className="rounded-xl border border-rose/30 bg-rose/10 p-3 text-sm text-rose">{page.error}</p>}
      <label className="block">
        <span className="mb-1.5 block text-[13px] font-medium">Write your own prompt for this page</span>
        <textarea
          rows={4}
          value={override}
          onChange={(e) => setOverride(e.target.value)}
          placeholder="Leave empty to let the story model write it"
          className={cx(inputClass, 'resize-y')}
        />
      </label>
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" icon={RefreshCw} busy={busy} onClick={() => repaint(override)}>
          Repaint page
        </Button>
        {page.prompt_override && (
          <Button onClick={() => repaint('')}>Back to automatic</Button>
        )}
      </div>
    </div>
  )
}

const TABS = [
  ['run', 'Progress', Play],
  ['cast', 'Cast', Users],
  ['style', 'Style', Palette],
  ['page', 'Page', Pencil],
]

/* ------------------------------------------------------------------- reader */

export default function Reader({ id, onBack }) {
  const [book, setBook, error] = useLiveBook(id)
  const [current, setCurrentRaw] = useState(0)
  const [mode, setMode] = useLocalSetting('mode', 'split')
  const [theme, setTheme] = useLocalSetting('theme', 'night')
  const [size, setSize] = useLocalSetting('size', 18)
  const [drawer, setDrawer] = useState(null)

  const setCurrent = useCallback((i) => setCurrentRaw(i), [])
  const navRef = useRef(null)
  const total = book?.pages.length || 0

  useEffect(() => {
    const onKey = (e) => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName) || drawer) return
      const goTo = (i) => (mode === 'split' && navRef.current ? navRef.current(i) : setCurrentRaw(i))
      if (e.key === 'ArrowRight' || e.key === 'j' || (mode === 'cinema' && e.key === ' ')) {
        e.preventDefault()
        goTo(Math.min(total - 1, current + 1))
      } else if (e.key === 'ArrowLeft' || e.key === 'k') {
        e.preventDefault()
        goTo(Math.max(0, current - 1))
      } else if (e.key === 'Escape' && mode === 'cinema') setMode('split')
      else if (e.key === 'c') setMode(mode === 'cinema' ? 'split' : 'cinema')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [current, total, mode, drawer, setMode])

  useEffect(() => {
    if (book) document.title = `${book.title} — Booktures`
    return () => (document.title = 'Booktures')
  }, [book?.title]) // eslint-disable-line react-hooks/exhaustive-deps

  const live = book && ACTIVE.includes(book.status)
  const header = useMemo(
    () =>
      book && (
        <header className="sticky top-0 z-30 flex h-[57px] items-center gap-2 border-b border-ink-800 bg-ink-950/90 px-2 backdrop-blur-md sm:px-4">
          <IconButton icon={ArrowLeft} label="Back to library" onClick={onBack} />
          <div className="min-w-0 flex-1">
            <p className="truncate font-display text-[17px] leading-tight">{book.title}</p>
            <div className="flex items-center gap-2 text-xs text-muted">
              {live ? (
                <>
                  <Progress value={book.progress} className="w-24 sm:w-40" />
                  <span className="truncate">{book.message}</span>
                </>
              ) : (
                <span className="truncate">
                  {book.counts.done + book.counts.reused}/{total} pages illustrated
                  {book.status === 'failed' && ' · needs attention'}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-0.5">
            <div className="mr-1 hidden rounded-full bg-ink-850 p-0.5 sm:flex">
              <IconButton icon={Columns2} label="Split view" active={mode === 'split'} onClick={() => setMode('split')} />
              <IconButton icon={Film} label="Cinema mode (C)" active={mode === 'cinema'} onClick={() => setMode('cinema')} />
            </div>
            <button
              className="hidden h-9 rounded-full px-2.5 text-sm text-paper-dim hover:bg-ink-800 hover:text-paper sm:block"
              onClick={() => setSize(SIZES[(SIZES.indexOf(size) + 1) % SIZES.length])}
              title="Text size"
            >
              A<span className="text-[11px]">A</span>
            </button>
            <IconButton
              icon={theme === 'night' ? Moon : Sun}
              label={`Reading theme: ${theme}`}
              onClick={() => setTheme(THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length])}
            />
            <IconButton icon={Info} label="Book details" onClick={() => setDrawer('run')} active={!!drawer} />
            <a
              href={api.exportUrl(book.id)}
              download
              aria-label="Export as HTML"
              title="Export as HTML"
              className="hidden size-9 items-center justify-center rounded-full text-paper-dim transition-colors hover:bg-ink-800 hover:text-paper sm:inline-flex"
            >
              <Download className="size-[18px]" />
            </a>
          </div>
        </header>
      ),
    [book, live, mode, size, theme, total, onBack, setMode, setSize, setTheme, drawer],
  )

  if (error && !book)
    return (
      <div className="grid min-h-dvh place-items-center p-6 text-center">
        <div>
          <p className="font-display text-2xl">{error}</p>
          <Button className="mt-5" onClick={onBack}>Back to library</Button>
        </div>
      </div>
    )
  if (!book) return <div className="shimmer h-dvh" />

  return (
    <div className="min-h-dvh bg-ink-950">
      {header}
      {mode === 'cinema' ? (
        <CinemaView book={book} current={current} setCurrent={setCurrent} onExit={() => setMode('split')} size={size} />
      ) : (
        <SplitView book={book} current={current} setCurrent={setCurrent} theme={theme} size={size} onPageTools={() => setDrawer('page')} navRef={navRef} />
      )}
      <Drawer open={!!drawer} onClose={() => setDrawer(null)} title={book.title}>
        <div className="sticky top-0 z-10 flex gap-1 border-b border-ink-700 bg-ink-900/95 px-3 py-2 backdrop-blur">
          {TABS.map(([key, label, Icon]) => (
            <button
              key={key}
              onClick={() => setDrawer(key)}
              className={cx(
                'inline-flex flex-1 items-center justify-center gap-1.5 rounded-full py-2 text-[13px] transition-colors',
                drawer === key ? 'bg-ink-700 text-paper' : 'text-paper-dim hover:text-paper',
              )}
            >
              <Icon className="size-3.5" />
              {label}
            </button>
          ))}
        </div>
        {drawer === 'run' && <RunTab book={book} />}
        {drawer === 'cast' && <CastTab book={book} setBook={setBook} />}
        {drawer === 'style' && <StyleTab book={book} setBook={setBook} />}
        {drawer === 'page' && <PageTab book={book} current={current} />}
      </Drawer>
    </div>
  )
}
