const API = import.meta.env.VITE_API_BASE || ''

export async function api(path, options = {}) {
  const res = await fetch(`${API}${path}`, options)
  const type = res.headers.get('content-type') || ''
  const body = type.includes('application/json') ? await res.json() : await res.text()
  if (!res.ok) throw new Error(body?.detail || body?.error || body || `HTTP ${res.status}`)
  return body
}

export const apiUrl = (path) => `${API}${path}`

export async function uploadDataset(file, modality='auto') {
  const form = new FormData()
  form.append('file', file)
  form.append('modality', modality)
  return api('/api/v1/datasets', { method: 'POST', body: form })
}
