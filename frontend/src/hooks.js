import { useEffect, useState } from 'react'
import { api } from './api'

/** Current hash route, e.g. ['book', 'abc123'] for #/book/abc123. */
export function useRoute() {
  const parse = () => window.location.hash.replace(/^#\/?/, '').split('/').filter(Boolean)
  const [route, setRoute] = useState(parse)
  useEffect(() => {
    const on = () => {
      setRoute(parse())
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return route
}

export const go = (path) => {
  window.location.hash = path
}

/** Live book state over server-sent events, with polling as a fallback. */
export function useLiveBook(id) {
  const [book, setBook] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id) return
    let closed = false
    let timer
    let source

    const poll = async () => {
      try {
        const b = await api.book(id)
        if (!closed) setBook(b)
      } catch (e) {
        if (!closed) setError(e.message)
      }
      if (!closed) timer = setTimeout(poll, 2000)
    }

    if ('EventSource' in window) {
      source = new EventSource(`/api/books/${id}/events`)
      source.onmessage = (e) => setBook(JSON.parse(e.data))
      source.addEventListener('gone', () => {
        setError('This book was deleted.')
        source.close()
      })
      source.onerror = () => {
        source.close()
        if (!closed) poll()
      }
    } else {
      poll()
    }
    return () => {
      closed = true
      clearTimeout(timer)
      source?.close()
    }
  }, [id])

  return [book, setBook, error]
}

export function useLocalSetting(key, initial) {
  const [value, setValue] = useState(() => {
    try {
      const raw = localStorage.getItem(`booktures:${key}`)
      return raw === null ? initial : JSON.parse(raw)
    } catch {
      return initial
    }
  })
  useEffect(() => {
    try {
      localStorage.setItem(`booktures:${key}`, JSON.stringify(value))
    } catch {
      /* storage unavailable */
    }
  }, [key, value])
  return [value, setValue]
}
