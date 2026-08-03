import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

export interface DashboardOverview {
  generated_at: string
  window: { hours: number; bucket_hours: number; start: string; end: string }
  summary: {
    total_events: number; request_count: number; business_reviews: number; alerts: number
    blocked: number; successful: number; success_rate: number; block_rate: number
    average_latency_ms: number; p95_latency_ms: number; unique_clients: number; unique_actors: number
  }
  timeline: Array<{ start: string; events: number; alerts: number; blocked: number; avg_latency_ms: number }>
  risk_distribution: Array<{ name: string; value: number }>
  module_distribution: Array<{ name: string; value: number }>
  top_sources: Array<{ client_ip: string; events: number; alerts: number; blocked: number }>
  recent_alerts: Array<{ id: string; occurred_at: string; module: string; severity: string; outcome: string; risk_code?: string; risk_score?: number; client_ip?: string; summary: string }>
  models: Array<{ id: string; label: string; model: string; status: string }>
  reports: { total: number; in_window: number; fake_count: number; risk_count: number; latest_at?: string }
  service_health: { api: string; audit_chain: string; raw_evidence_vault: string; configured_models: number; total_models: number }
  data_sources: string[]
  privacy: { raw_content_included: boolean; encrypted_evidence_retained: boolean }
}

export function useDashboard() {
  const data = ref<DashboardOverview | null>(null)
  const hours = ref(24)
  const loading = ref(false)
  const error = ref('')
  const authRequired = ref(false)
  let controller: AbortController | null = null
  let timer: ReturnType<typeof setInterval> | null = null
  let debounceTimer: ReturnType<typeof setTimeout> | null = null
  let lastStartedAt = 0

  async function refresh(force = false) {
    const now = Date.now()
    if (!force && now - lastStartedAt < 800) return
    lastStartedAt = now
    controller?.abort()
    const active = new AbortController()
    controller = active
    loading.value = true
    error.value = ''
    try {
      const response = await fetch(`/api/dashboard/overview?hours=${hours.value}`, {
        credentials: 'same-origin', signal: active.signal,
      })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw Object.assign(new Error(body.detail || '驾驶舱数据暂时不可用'), { status: response.status })
      data.value = body
      authRequired.value = false
    } catch (caught) {
      if ((caught as Error).name === 'AbortError') return
      authRequired.value = (caught as Error & { status?: number }).status === 401
      error.value = (caught as Error).message
      if (authRequired.value) data.value = null
    } finally {
      if (controller === active) loading.value = false
    }
  }

  function scheduleRefresh() {
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => refresh(true), 220)
  }

  function openLogin() { window.dispatchEvent(new CustomEvent('aigc:open-login')) }
  watch(hours, scheduleRefresh)
  onMounted(() => {
    refresh(true)
    timer = setInterval(() => refresh(), 15_000)
  })
  onBeforeUnmount(() => {
    controller?.abort()
    if (timer) clearInterval(timer)
    if (debounceTimer) clearTimeout(debounceTimer)
  })
  return { data, hours, loading, error, authRequired, refresh, openLogin }
}
