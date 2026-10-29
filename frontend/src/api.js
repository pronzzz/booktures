async function request(method, url, body, isForm = false) {
  const opts = { method, headers: {} }
  if (body !== undefined) {
    if (isForm) opts.body = body
    else {
      opts.headers['Content-Type'] = 'application/json'
      opts.body = JSON.stringify(body)
    }
  }
  const res = await fetch(url, opts)
  const text = await res.text()
  let data = null
  try { data = text ? JSON.parse(text) : null } catch { data = text }
  if (!res.ok) {
    const detail = data && typeof data === 'object' ? data.detail : data
    throw new Error(typeof detail === 'string' ? detail : `Request failed (${res.status})`)
  }
  return data
}

export const api = {
  health: () => request('GET', '/api/health'),
  styles: () => request('GET', '/api/styles'),
  providers: () => request('GET', '/api/providers'),
  settings: () => request('GET', '/api/settings'),
  saveSettings: (patch) => request('PUT', '/api/settings', patch),
  checkProvider: (kind, id, config) => request('POST', `/api/providers/${kind}/${id}/check`, { config }),
  testProvider: (kind, id, config) => request('POST', `/api/providers/${kind}/${id}/test`, { config }),
  books: () => request('GET', '/api/books'),
  book: (id) => request('GET', `/api/books/${id}`),
  upload: (form) => request('POST', '/api/books', form, true),
  sample: (style_preset) => request('POST', '/api/books/sample', { style_preset }),
  patchBook: (id, patch) => request('PATCH', `/api/books/${id}`, patch),
  deleteBook: (id) => request('DELETE', `/api/books/${id}`),
  run: (id, mode = 'resume') => request('POST', `/api/books/${id}/run`, { mode }),
  cancel: (id) => request('POST', `/api/books/${id}/cancel`),
  regenerate: (id, number, prompt_override) =>
    request('POST', `/api/books/${id}/pages/${number}/regenerate`, { prompt_override }),
  exportUrl: (id) => `/api/books/${id}/export`,
}

export const ACTIVE = ['queued', 'analyzing', 'illustrating']
