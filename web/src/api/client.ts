export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const UNAUTHORIZED_EVENT = 'metrixsense:unauthorized'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, init)
  } catch {
    throw new ApiError(0, 'Сервер недоступен — убедитесь, что MetrixSense запущен')
  }

  if (res.status === 401) {
    window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT))
    throw new ApiError(401, 'Требуется вход')
  }

  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // тело не json — оставляем statusText
    }
    throw new ApiError(res.status, detail)
  }

  return res.json() as Promise<T>
}

export const api = {
  get: <T>(path: string) => request<T>(path),

  post: <T>(path: string, body?: unknown) =>
    body === undefined
      ? request<T>(path, { method: 'POST' })
      : request<T>(path, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }),

  put: <T>(path: string, body: unknown) =>
    request<T>(path, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),

  onUnauthorized(cb: () => void) {
    const handler = () => cb()
    window.addEventListener(UNAUTHORIZED_EVENT, handler)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, handler)
  },
}
