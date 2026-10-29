import { useEffect, useMemo, useState } from 'react'
import { Check, Cloud, Cpu, Eye, Plug, Sparkles, TriangleAlert } from 'lucide-react'
import { api } from '../api'
import { Badge, Button, cx, inputClass, useToast } from './ui'

const SIZES = [
  ['768x512', 'Landscape 3:2 (768×512)'],
  ['1024x576', 'Wide 16:9 (1024×576)'],
  ['640x640', 'Square (640×640)'],
  ['512x768', 'Portrait 2:3 (512×768)'],
  ['1216x832', 'Large landscape (1216×832)'],
]

function Toggle({ checked, onChange, label }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={!!checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={cx('relative h-6 w-11 shrink-0 rounded-full transition-colors', checked ? 'bg-ember' : 'bg-ink-600')}
    >
      <span className={cx('absolute top-0.5 size-5 rounded-full bg-paper shadow transition-transform', checked ? 'translate-x-5' : 'translate-x-0.5')} />
    </button>
  )
}

function SecretInput({ value, onChange, placeholder }) {
  const [show, setShow] = useState(false)
  return (
    <div className="relative">
      <input
        type={show ? 'text' : 'password'}
        value={value}
        autoComplete="off"
        spellCheck={false}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={cx(inputClass, 'pr-10 font-mono')}
      />
      <button type="button" onClick={() => setShow(!show)} className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-muted hover:text-paper" aria-label={show ? 'Hide' : 'Show'}>
        <Eye className="size-4" />
      </button>
    </div>
  )
}

function ConfigForm({ fields, values, onChange }) {
  if (!fields.length) return <p className="text-sm text-muted">Nothing to configure.</p>
  const set = (key, v) => onChange({ ...values, [key]: v })
  return (
    <div className="grid gap-5 md:grid-cols-2">
      {fields.map((f) => {
        const value = values[f.key] ?? (['select', 'boolean'].includes(f.type) ? f.default : '')
        const placeholder = f.placeholder || (f.default !== null && f.default !== undefined && f.default !== '' ? String(f.default) : '')
        let control
        if (f.type === 'secret') control = <SecretInput value={value} onChange={(v) => set(f.key, v)} placeholder={f.env ? `or set $${f.env}` : 'Not set'} />
        else if (f.type === 'boolean')
          control = (
            <div className="flex h-[42px] items-center">
              <Toggle checked={value} onChange={(v) => set(f.key, v)} label={f.label} />
            </div>
          )
        else if (f.type === 'select')
          control = (
            <select
              value={value ?? ''}
              onChange={(e) => {
                const v = e.target.value
                onChange({ ...values, [f.key]: v, ...(f.sets?.[v] || {}) })
              }}
              className={inputClass}
            >
              {!f.options?.includes(value) && value && <option value={value}>{value}</option>}
              {f.options?.map((o) => (
                <option key={o} value={o}>{o}</option>
              ))}
            </select>
          )
        else if (f.type === 'textarea')
          control = <textarea rows={5} value={value} placeholder={placeholder} onChange={(e) => set(f.key, e.target.value)} className={cx(inputClass, 'font-mono text-xs')} />
        else
          control = (
            <input
              type={f.type === 'number' ? 'number' : f.type === 'url' ? 'url' : 'text'}
              step="any"
              value={value}
              placeholder={placeholder}
              onChange={(e) => set(f.key, e.target.value)}
              className={inputClass}
            />
          )
        return (
          <label key={f.key} className={cx('block', f.type === 'textarea' && 'md:col-span-2')}>
            <span className="mb-1.5 block text-[13px] font-medium text-paper">{f.label}</span>
            {control}
            {f.help && <span className="mt-1.5 block text-xs leading-relaxed text-muted">{f.help}</span>}
          </label>
        )
      })}
    </div>
  )
}

function TestResult({ kind, result }) {
  if (!result) return null
  return (
    <div className={cx('mt-4 rounded-2xl border p-4 text-sm', result.ok ? 'border-sea/30 bg-sea/5' : 'border-rose/30 bg-rose/5')}>
      <p className={cx('flex items-start gap-2', result.ok ? 'text-sea' : 'text-rose')}>
        {result.ok ? <Check className="mt-0.5 size-4 shrink-0" /> : <TriangleAlert className="mt-0.5 size-4 shrink-0" />}
        <span>{result.message}</span>
      </p>
      {kind === 'text' && result.scene && (
        <dl className="mt-3 grid gap-2 text-paper-dim">
          <div><dt className="text-xs uppercase tracking-wider text-muted">Scene</dt><dd>{result.scene.scene_summary}</dd></div>
          <div><dt className="text-xs uppercase tracking-wider text-muted">Picture</dt><dd>{result.scene.visual_description}</dd></div>
          <div><dt className="text-xs uppercase tracking-wider text-muted">Characters</dt><dd>{result.scene.characters.join(', ') || '—'}</dd></div>
        </dl>
      )}
      {kind === 'image' && result.image && (
        <figure className="mt-3">
          <img src={result.image} alt="Sample painted by this illustrator" className="w-full max-w-lg rounded-xl" />
          <figcaption className="mt-2 font-mono text-[11px] leading-relaxed text-muted">{result.prompt}</figcaption>
        </figure>
      )}
    </div>
  )
}

function ProviderSection({ kind, title, intro, providers, draft, setDraft }) {
  const toast = useToast()
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState('')
  const selectedId = draft[kind].provider
  const selected = providers.find((p) => p.id === selectedId)
  const values = draft[kind].configs[selectedId] || {}

  useEffect(() => setResult(null), [selectedId])

  const choose = (id) => setDraft({ ...draft, [kind]: { ...draft[kind], provider: id } })
  const setValues = (v) => setDraft({ ...draft, [kind]: { ...draft[kind], configs: { ...draft[kind].configs, [selectedId]: v } } })

  const run = async (what) => {
    setBusy(what)
    setResult(null)
    try {
      const fn = what === 'check' ? api.checkProvider : api.testProvider
      setResult(await fn(kind, selectedId, values))
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setBusy('')
    }
  }

  return (
    <section className="rounded-[28px] border border-ink-700/80 bg-ink-900/70 p-5 sm:p-7">
      <h2 className="font-display text-2xl">{title}</h2>
      <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-paper-dim">{intro}</p>
      <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-3" role="radiogroup" aria-label={title}>
        {providers.map((p) => (
          <button
            key={p.id}
            role="radio"
            aria-checked={p.id === selectedId}
            onClick={() => choose(p.id)}
            className={cx(
              'group relative rounded-2xl border p-4 text-left transition-all',
              p.id === selectedId ? 'border-ember/70 bg-ember/[0.06] shadow-[inset_0_0_0_1px_rgb(229_165_91/0.25)]' : 'border-ink-700 hover:border-ink-600 hover:bg-ink-850',
            )}
          >
            <div className="flex items-start justify-between gap-2">
              <span className="font-medium text-paper">{p.name}</span>
              {p.id === selectedId && <Check className="size-4 shrink-0 text-ember" />}
            </div>
            <div className="mt-2 flex flex-wrap gap-1">
              {p.local ? (
                <Badge tone="local"><Cpu className="size-3" />Local</Badge>
              ) : (
                <Badge tone="cloud"><Cloud className="size-3" />Cloud</Badge>
              )}
              {p.origin !== 'built-in' && <Badge><Plug className="size-3" />Plugin</Badge>}
              {!p.available && <Badge tone="warn">Needs install</Badge>}
            </div>
            <p className="mt-2.5 line-clamp-3 text-[13px] leading-relaxed text-muted">{p.description}</p>
          </button>
        ))}
      </div>

      {selected && (
        <div className="mt-6 rounded-2xl border border-ink-700 bg-ink-950/50 p-5">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="font-display text-lg">{selected.name}</h3>
              {selected.homepage && (
                <a href={selected.homepage} target="_blank" rel="noreferrer" className="text-xs text-ember hover:underline">
                  {selected.homepage.replace(/^https?:\/\//, '')}
                </a>
              )}
            </div>
            <div className="flex gap-2">
              <Button size="sm" busy={busy === 'check'} onClick={() => run('check')}>Check connection</Button>
              <Button size="sm" variant="primary" icon={Sparkles} busy={busy === 'test'} onClick={() => run('test')}>
                Try it
              </Button>
            </div>
          </div>
          {!selected.available && (
            <div className="mb-5 rounded-xl border border-rose/30 bg-rose/5 p-3 text-sm text-paper-dim">
              {selected.unavailable_reason}
            </div>
          )}
          <ConfigForm fields={selected.fields} values={values} onChange={setValues} />
          <TestResult kind={kind} result={result} />
        </div>
      )}
    </section>
  )
}

function PipelineSection({ draft, setDraft }) {
  const pipe = draft.pipeline
  const set = (k, v) => setDraft({ ...draft, pipeline: { ...pipe, [k]: v } })
  const size = `${pipe.width}x${pipe.height}`
  return (
    <section className="rounded-[28px] border border-ink-700/80 bg-ink-900/70 p-5 sm:p-7">
      <h2 className="font-display text-2xl">Pipeline</h2>
      <p className="mt-1.5 text-sm text-paper-dim">How pages become pictures.</p>
      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <label className="block">
          <span className="mb-1.5 block text-[13px] font-medium">Picture size</span>
          <select
            className={inputClass}
            value={size}
            onChange={(e) => {
              const [w, h] = e.target.value.split('x').map(Number)
              setDraft({ ...draft, pipeline: { ...pipe, width: w, height: h } })
            }}
          >
            {!SIZES.some(([v]) => v === size) && <option value={size}>{size.replace('x', '×')}</option>}
            {SIZES.map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
          <span className="mt-1.5 block text-xs text-muted">Local models scale this to their native size.</span>
        </label>
        <label className="block">
          <span className="mb-1.5 flex justify-between text-[13px] font-medium">
            Reuse a picture when scenes match
            <span className="text-muted">{pipe.similarity_threshold > 0 ? `${Math.round(pipe.similarity_threshold * 100)}% similar` : 'Off'}</span>
          </span>
          <input
            type="range"
            min="0"
            max="0.95"
            step="0.01"
            value={pipe.similarity_threshold}
            onChange={(e) => set('similarity_threshold', Number(e.target.value))}
            className="w-full accent-[var(--color-ember)]"
          />
          <span className="mt-1.5 block text-xs text-muted">Saves time and money on long conversations in one room. 0 paints every page.</span>
        </label>
        <div className="flex items-start justify-between gap-4 rounded-2xl border border-ink-700 p-4">
          <div>
            <p className="text-[13px] font-medium">Content screening</p>
            <p className="mt-1 text-xs leading-relaxed text-muted">Swap graphic scenes for a neutral placeholder before painting.</p>
          </div>
          <Toggle checked={pipe.safety !== 'off'} onChange={(v) => set('safety', v ? 'standard' : 'off')} label="Content screening" />
        </div>
        <div className="flex items-start justify-between gap-4 rounded-2xl border border-ink-700 p-4">
          <div>
            <p className="text-[13px] font-medium">Fall back to the offline analyzer</p>
            <p className="mt-1 text-xs leading-relaxed text-muted">If the story model errors on a page, keep going instead of stopping.</p>
          </div>
          <Toggle checked={pipe.fallback_to_offline} onChange={(v) => set('fallback_to_offline', v)} label="Offline fallback" />
        </div>
      </div>
    </section>
  )
}

function PluginsSection({ catalog }) {
  const plugins = [...catalog.text, ...catalog.image].filter((p) => p.origin !== 'built-in')
  return (
    <section className="rounded-[28px] border border-ink-700/80 bg-ink-900/70 p-5 sm:p-7">
      <h2 className="flex items-center gap-2 font-display text-2xl"><Plug className="size-5 text-ember" /> Plugins</h2>
      <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-paper-dim">
        Add any LLM or image model by dropping a Python file in your plugin folder and restarting Booktures. A plugin
        is one class with a <code className="text-ember">complete_json()</code> or <code className="text-ember">generate()</code> method.
      </p>
      <div className="mt-5 rounded-2xl border border-ink-700 bg-ink-950/60 p-4 font-mono text-xs text-paper-dim">
        {catalog.plugin_dirs.map((d) => (
          <div key={d}>{d}</div>
        ))}
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-2">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">Loaded plugins</p>
          {plugins.length ? (
            <ul className="space-y-2">
              {plugins.map((p) => (
                <li key={`${p.kind}-${p.id}`} className="rounded-xl border border-ink-700 p-3 text-sm">
                  <span className="font-medium">{p.name}</span> <span className="text-muted">({p.kind === 'text' ? 'story model' : 'illustrator'})</span>
                  <p className="mt-1 truncate font-mono text-[11px] text-muted">{p.origin}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">None yet. Copy <code>plugins/hf_inference.py</code> from the repo to try one.</p>
          )}
        </div>
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">Load errors</p>
          {catalog.errors.length ? (
            <ul className="space-y-2">
              {catalog.errors.map((e) => (
                <li key={e.source} className="rounded-xl border border-rose/30 bg-rose/5 p-3 text-sm">
                  <p className="truncate font-mono text-[11px] text-paper-dim">{e.source}</p>
                  <p className="mt-1 text-rose">{e.error}</p>
                  <details className="mt-1"><summary className="cursor-pointer text-xs text-muted">Traceback</summary><pre className="mt-2 overflow-x-auto text-[10.5px] text-muted">{e.traceback}</pre></details>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">No problems.</p>
          )}
        </div>
      </div>
      <a href="https://github.com/pronzzz/booktures/blob/main/docs/PLUGINS.md" target="_blank" rel="noreferrer" className="mt-5 inline-block text-sm text-ember hover:underline">
        Read the plugin guide →
      </a>
    </section>
  )
}

export default function Settings({ onSaved }) {
  const toast = useToast()
  const [catalog, setCatalog] = useState(null)
  const [saved, setSaved] = useState(null)
  const [draft, setDraft] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    Promise.all([api.providers(), api.settings()])
      .then(([cat, s]) => {
        setCatalog(cat)
        setSaved(s)
        setDraft(s)
      })
      .catch((e) => toast(e.message, 'error'))
  }, [toast])

  const dirty = useMemo(() => draft && JSON.stringify(draft) !== JSON.stringify(saved), [draft, saved])

  const save = async () => {
    setBusy(true)
    try {
      const s = await api.saveSettings(draft)
      setSaved(s)
      setDraft(s)
      toast('Settings saved. New books will use them.')
      onSaved?.()
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  if (!catalog || !draft)
    return (
      <main className="mx-auto max-w-6xl space-y-6 px-4 py-10 sm:px-6">
        {[0, 1].map((i) => <div key={i} className="shimmer h-80 rounded-[28px]" />)}
      </main>
    )

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-4 pb-32 pt-10 sm:px-6">
      <div>
        <h1 className="font-display text-4xl sm:text-5xl">Models &amp; plugins</h1>
        <p className="mt-3 max-w-2xl text-paper-dim">
          Booktures uses two models: a <span className="text-paper">story model</span> that reads the book and writes a
          brief for every picture, and an <span className="text-paper">illustrator</span> that paints it. Mix local and
          cloud however you like.
        </p>
      </div>
      <ProviderSection
        kind="text"
        title="Story model"
        intro="Reads the opening to build the character bible and art style, then describes each page as a scene."
        providers={catalog.text}
        draft={draft}
        setDraft={setDraft}
      />
      <ProviderSection
        kind="image"
        title="Illustrator"
        intro="Paints each scene. The local mini model runs SD-Turbo on your GPU; the Sketchbook painter needs nothing at all."
        providers={catalog.image}
        draft={draft}
        setDraft={setDraft}
      />
      <PipelineSection draft={draft} setDraft={setDraft} />
      <PluginsSection catalog={catalog} />

      <div className={cx('fixed inset-x-0 bottom-0 z-30 border-t border-ink-700 bg-ink-900/95 backdrop-blur transition-transform', dirty ? 'translate-y-0' : 'translate-y-full')}>
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <p className="text-sm text-paper-dim">You have unsaved changes.</p>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => setDraft(saved)}>Discard</Button>
            <Button variant="primary" busy={busy} onClick={save}>Save changes</Button>
          </div>
        </div>
      </div>
    </main>
  )
}
