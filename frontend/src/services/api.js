const API_ROOT = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api'

async function request(path, options = {}) {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const detail = typeof body.detail === 'string'
      ? body.detail
      : Array.isArray(body.detail)
        ? body.detail.map((issue) => issue.msg).join('; ')
        : 'Request failed'
    throw new Error(detail)
  }
  return response.status === 204 ? null : response.json()
}

export const api = {
  status: () => request('/status'),
  detail: (id) => request(`/status/${id}`),
  history: (id) => request(`/history/${id}?limit=48`),
  create: (values) => request('/websites', { method: 'POST', body: JSON.stringify(values) }),
  createMany: (websites) => request('/websites/bulk', {
    method: 'POST',
    body: JSON.stringify({ websites }),
  }),
  update: (id, values) => request(`/websites/${id}`, { method: 'PUT', body: JSON.stringify(values) }),
  remove: (id) => request(`/websites/${id}`, { method: 'DELETE' }),
  importCsv: (file) => request('/websites/import', {
    method: 'POST',
    headers: { 'Content-Type': 'text/csv' },
    body: file,
  }),
  checkAll: () => request('/check', { method: 'POST' }),
  checkOne: (id) => request(`/check/${id}`, { method: 'POST' }),
}