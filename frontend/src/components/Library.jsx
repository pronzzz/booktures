import { useCallback, useEffect, useRef, useState } from 'react'
import { BookMarked, FileText, Sparkles, Trash2, Upload } from 'lucide-react'
import { ACTIVE, api } from '../api'
import { go } from '../hooks'
import { Button, cx, IconButton, Progress, StatusPill, useToast } from './ui'

const ACCEPT = '.pdf,.epub,.txt,.md,.markdown'
const PAGE_LIMITS = [
  [0, 'Whole book'],
  [5, 'First 5 pages'],
  [10, 'First 10 pages'],
  [25, 'First 25 pages'],
  [50, 'First 50 pages'],
]

// Small painted swatches so style chips are recognisable at a glance.
const SWATCH = {
  auto: 'conic-gradient(from 200deg, #e5a55b, #7fb8a8, #b07cc6, #e27a66, #e5a55b)',
  watercolor: 'radial-gradient(circle at 30% 30%, #b9d7e8, #8fb4c9 40%, #e8d9c2 75%)',
  ink: 'linear-gradient(135deg, #e9dcc0 0%, #8a6a44 55%, #2b2117 100%)',
  oil: 'radial-gradient(circle at 70% 30%, #e7b45c, #7a3d1f 55%, #1f130c)',
  gouache: 'linear-gradient(160deg, #f2c46d 0 40%, #5c9a8a 40% 70%, #2f5560 70%)',
  anime: 'linear-gradient(160deg, #7ec8ff 0 45%, #ffb3c7 45% 70%, #4a6cd4 70%)',
  noir: 'linear-gradient(135deg, #f2f2f2 0 30%, #111 30% 65%, #6b6b6b 65%)',
  cinematic: 'linear-gradient(180deg, #0f2a3a, #d58b4b 60%, #2a1a12)',
  woodcut: 'repeating-linear-gradient(45deg, #2a1d14 0 3px, #e9dcc3 3px 7px)',
  pixel: 'conic-gradient(#5aa1e3 0 25%, #f4d35e 0 50%, #3d8a5a 0 75%, #d1495b 0)',
}

export function StylePicker({ styles, value, onChange }) {
  return (
    <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Art style">
      {styles.map((s) => (
        <button
          key={s.id}
          type="button"
          role="radio"
          aria-checked={value === s.id}
          title={s.blurb}
          onClick={() => onChange(s.id)}
          className={cx(
            'inline-flex items-center gap-2 rounded-full border py-1.5 pl-1.5 pr-3 text-[13px] transition-all',
            value === s.id
              ? 'border-ember/70 bg-ember/10 text-paper'
              : 'border-ink-600/70 text-paper-dim hover:border-ink-600 hover:text-paper',
          )}
        >
          <span className="size-5 rounded-full ring-1 ring-white/10" style={{ background: SWATCH[s.id] || SWATCH.auto }} />
          {s.name}
        </button>
      ))}
    </div>
  )
}

function UploadPanel({ onCreated }) {
  const toast = useToast()
  const [styles, setStyles] = useState([])
  const [style, setStyle] = useState('auto')
  const [limit, setLimit] = useState(0)
  const [file, setFile] = useState(null)
  const [drag, setDrag] = useState(false)
  const [busy, setBusy] = useState('')
  const input = useRef(null)

  useEffect(() => {
    api.styles().then(setStyles).catch(() => {})
  }, [])

  const pick = (f) => {
    if (!f) return
    if (!/\.(pdf|epub|txt|md|markdown)$/i.test(f.name)) {
      toast('Booktures reads PDF, EPUB, TXT and Markdown files.', 'error')
      return
    }
    setFile(f)
  }

  const start = async () => {
    if (!file) return input.current?.click()
    setBusy('upload')
    const form = new FormData()
    form.append('file', file)
    form.append('style_preset', style)
    form.append('max_pages', String(limit))
    try {
      const book = await api.upload(form)
      onCreated(book)
      go(`/book/${book.id}`)
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setBusy('')
    }
  }

  const sample = async () => {
    setBusy('sample')
    try {
      const book = await api.sample(style)
      go(`/book/${book.id}`)
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setBusy('')
    }
  }

  return (
    <div className="rounded-[28px] border border-ink-700/80 bg-ink-900/80 p-5 shadow-2xl shadow-black/40 backdrop-blur sm:p-6">
      <div
        role="button"
        tabIndex={0}
        onClick={() => input.current?.click()}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setDrag(true)
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDrag(false)
          pick(e.dataTransfer.files?.[0])
        }}
        className={cx(
          'group flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-9 text-center transition-all',
          drag ? 'border-ember bg-ember/5' : 'border-ink-600 hover:border-ink-600 hover:bg-ink-850',
        )}
      >
        <input ref={input} type="file" accept={ACCEPT} className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
        {file ? (
          <>
            <FileText className="mb-3 size-9 text-ember" />
            <p className="max-w-full truncate font-medium">{file.name}</p>
            <p className="mt-1 text-xs text-muted">{(file.size / 1024 / 1024).toFixed(1)} MB · click to choose another</p>
          </>
        ) : (
          <>
            <div className="mb-3 grid size-12 place-items-center rounded-2xl bg-ink-800 transition-transform group-hover:-translate-y-0.5">
              <Upload className="size-5 text-ember" />
            </div>
            <p className="font-medium">Drop a book here</p>
            <p className="mt-1 text-sm text-muted">PDF, EPUB, TXT or Markdown</p>
          </>
        )}
      </div>

      <div className="mt-5 space-y-2">
        <p className="text-[13px] font-medium text-paper">Art style</p>
        <StylePicker styles={styles} value={style} onChange={setStyle} />
      </div>

      <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center">
        <select
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          aria-label="How much of the book"
          className="h-12 rounded-full border border-ink-600/80 bg-ink-900 px-4 text-sm text-paper outline-none focus:border-ember/70"
        >
          {PAGE_LIMITS.map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
        <Button variant="primary" size="lg" icon={Sparkles} busy={busy === 'upload'} onClick={start} className="flex-1">
          {file ? 'Illustrate this book' : 'Choose a book'}
        </Button>
      </div>
      <p className="mt-4 text-center text-[13px] text-muted">
        No book handy?{' '}
        <button onClick={sample} disabled={!!busy} className="font-medium text-ember underline-offset-4 hover:underline">
          {busy === 'sample' ? 'Opening…' : 'Try the sample story'}
        </button>
      </p>
    </div>
  )
}

function BookCard({ book, onDelete }) {
  const live = ACTIVE.includes(book.status)
  const done = book.counts.done + book.counts.reused
  return (
    <article className="group relative overflow-hidden rounded-3xl border border-ink-700/70 bg-ink-900 transition-all hover:-translate-y-0.5 hover:border-ink-600 hover:shadow-2xl hover:shadow-black/50">
      <a href={`#/book/${book.id}`} className="block" aria-label={`Open ${book.title}`}>
        <div className="relative aspect-[3/2] overflow-hidden bg-ink-850">
          {book.cover_url ? (
            <img src={book.cover_url} alt="" className="size-full object-cover transition-transform duration-700 group-hover:scale-[1.04]" />
          ) : (
            <div className={cx('grid size-full place-items-center', live && 'shimmer')}>
              <BookMarked className="size-8 text-ink-600" />
            </div>
          )}
          <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-ink-900 to-transparent" />
          {book.status !== 'done' && (
            <span className="absolute left-3 top-3 rounded-full bg-ink-950/85 shadow-lg backdrop-blur">
              <StatusPill status={book.status} />
            </span>
          )}
        </div>
        <div className="px-5 pb-5 pt-1">
          <h3 className="line-clamp-2 font-display text-xl leading-snug">{book.title}</h3>
          <p className="mt-1 truncate text-sm text-muted">
            {[book.author, book.genre].filter(Boolean).join(' · ') || book.filename}
          </p>
          <div className="mt-4 flex items-center gap-3 text-xs text-paper-dim">
            {live ? (
              <Progress value={book.progress} className="flex-1" />
            ) : (
              <span>
                {done}/{book.page_count} pages illustrated
              </span>
            )}
            <span className="uppercase tracking-wider text-muted">{book.format}</span>
          </div>
        </div>
      </a>
      <IconButton
        icon={Trash2}
        label={`Delete ${book.title}`}
        onClick={() => onDelete(book)}
        className="absolute right-3 top-3 bg-ink-950/60 opacity-0 backdrop-blur transition-opacity hover:!text-rose group-hover:opacity-100 focus:opacity-100"
      />
    </article>
  )
}

export default function Library() {
  const toast = useToast()
  const [books, setBooks] = useState(null)

  const load = useCallback(() => api.books().then(setBooks).catch((e) => toast(e.message, 'error')), [toast])
  useEffect(() => {
    load()
    // Pick up books added or changed elsewhere (another tab, the CLI) when you come back.
    const onFocus = () => document.visibilityState === 'visible' && load()
    document.addEventListener('visibilitychange', onFocus)
    window.addEventListener('focus', onFocus)
    return () => {
      document.removeEventListener('visibilitychange', onFocus)
      window.removeEventListener('focus', onFocus)
    }
  }, [load])
  useEffect(() => {
    if (!books?.some((b) => ACTIVE.includes(b.status))) return
    const t = setInterval(load, 2500)
    return () => clearInterval(t)
  }, [books, load])

  const remove = async (book) => {
    if (!window.confirm(`Delete “${book.title}” and its illustrations?`)) return
    await api.deleteBook(book.id)
    toast('Book deleted')
    load()
  }

  return (
    <main className="mx-auto max-w-7xl px-4 pb-24 sm:px-6">
      <section className="grid items-center gap-10 py-10 lg:grid-cols-[1.05fr_1fr] lg:py-16">
        <div>
          <p className="mb-5 inline-flex items-center gap-2 rounded-full border border-ink-700 bg-ink-900/60 px-3 py-1 text-xs text-paper-dim">
            <span className="size-1.5 rounded-full bg-sea" /> Runs on your machine · bring any model
          </p>
          <h1 className="font-display text-5xl font-medium leading-[1.02] tracking-tight sm:text-6xl lg:text-7xl">
            Every book
            <br />
            deserves <em className="font-normal text-ember">pictures.</em>
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-paper-dim">
            Booktures reads your book, keeps a bible of every character&rsquo;s face and clothes, and paints each page
            in one consistent style. Then you read it like a visual novel.
          </p>
          <ul className="mt-8 grid max-w-xl gap-3 text-sm text-paper-dim sm:grid-cols-3">
            {[
              ['Character bible', 'Looks stay the same on every page'],
              ['Style lock', 'One art direction for the whole book'],
              ['Your models', 'Ollama, Claude, SD, ComfyUI, plugins'],
            ].map(([t, d]) => (
              <li key={t} className="rounded-2xl border border-ink-700/70 bg-ink-900/50 p-3.5">
                <p className="font-medium text-paper">{t}</p>
                <p className="mt-1 text-xs leading-relaxed text-muted">{d}</p>
              </li>
            ))}
          </ul>
        </div>
        <UploadPanel onCreated={() => load()} />
      </section>

      <section>
        <div className="mb-5 flex items-end justify-between">
          <h2 className="font-display text-3xl">Your library</h2>
          {books?.length > 0 && <p className="text-sm text-muted">{books.length} book{books.length === 1 ? '' : 's'}</p>}
        </div>
        {books === null ? (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="shimmer aspect-[4/3] rounded-3xl" />
            ))}
          </div>
        ) : books.length === 0 ? (
          <div className="rounded-3xl border border-dashed border-ink-700 px-6 py-16 text-center text-paper-dim">
            <BookMarked className="mx-auto mb-3 size-8 text-ink-600" />
            Your illustrated books will appear here.
          </div>
        ) : (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {books.map((b) => (
              <BookCard key={b.id} book={b} onDelete={remove} />
            ))}
          </div>
        )}
      </section>
    </main>
  )
}
