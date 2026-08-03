import { readonly, ref } from 'vue'

export interface AuthUser {
  username: string
  display_name: string
  role: string
}

const user = ref<AuthUser | null>(null)
const configured = ref(true)
const loading = ref(true)

async function readJson(response: Response) {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || '认证服务暂时不可用')
  return data
}

export async function restoreSession() {
  loading.value = true
  try {
    const response = await fetch('/api/auth/session', { credentials: 'same-origin' })
    const data = await readJson(response)
    user.value = data.authenticated ? data.user : null
    configured.value = data.configured !== false
  } catch {
    user.value = null
  } finally {
    loading.value = false
  }
}

export async function login(username: string, password: string) {
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  const data = await readJson(response)
  user.value = data.user
  configured.value = true
  return data.user as AuthUser
}

export async function logout() {
  const response = await fetch('/api/auth/logout', {
    method: 'POST',
    credentials: 'same-origin',
  })
  await readJson(response)
  user.value = null
}

export function useAuth() {
  return {
    user: readonly(user),
    configured: readonly(configured),
    loading: readonly(loading),
  }
}
