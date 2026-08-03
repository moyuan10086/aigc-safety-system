import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'

export interface AuditEvent {
  id: string
  occurred_at: string
  event_type: string
  module: string
  action: string
  severity: 'info' | 'warning' | 'high' | 'critical'
  outcome: 'success' | 'allowed' | 'review' | 'blocked' | 'denied' | 'error'
  actor?: string
  client_ip?: string
  method?: string
  path?: string
  status_code?: number
  latency_ms?: number
  summary: string
  resource_id?: string
  risk_code?: string
  risk_score?: number
  content_hash?: string
  record_hash: string
  prev_hash: string
  has_evidence: number
  metadata: Record<string, unknown>
}

export interface AuditStats {
  total: number
  last_24h: number
  high_risk: number
  blocked: number
  unique_clients: number
  chain_valid: boolean
  latest_at?: string
  retention_days: number
  by_severity: Record<string, number>
}

export function useAuditLogs() {
  const items = ref<AuditEvent[]>([])
  const stats = ref<AuditStats | null>(null)
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const loading = ref(false)
  const error = ref('')
  const authRequired = ref(false)
  const autoRefresh = ref(false)
  const filters = reactive({ keyword: '', module: '', severity: '', outcome: '' })
  let controller: AbortController | null = null
  let debounceTimer: ReturnType<typeof setTimeout> | null = null
  let refreshTimer: ReturnType<typeof setInterval> | null = null

  const queryString = computed(() => {
    const query = new URLSearchParams({ page: String(page.value), page_size: String(pageSize.value) })
    Object.entries(filters).forEach(([key, value]) => { if (value) query.set(key, value) })
    return query.toString()
  })

  const exportUrl = computed(() => {
    const query = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => { if (value) query.set(key, value) })
    const suffix = query.toString()
    return `/api/audit/export.csv${suffix ? `?${suffix}` : ''}`
  })

  async function readJson(response: Response) {
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      const detail = typeof data.detail === 'string' ? data.detail : '审计服务暂时不可用'
      throw Object.assign(new Error(detail), { status: response.status })
    }
    return data
  }

  async function refresh() {
    controller?.abort()
    const activeController = new AbortController()
    controller = activeController
    loading.value = true
    error.value = ''
    try {
      const [logsResponse, statsResponse] = await Promise.all([
        fetch(`/api/audit/logs?${queryString.value}`, { credentials: 'same-origin', signal: activeController.signal }),
        fetch('/api/audit/stats', { credentials: 'same-origin', signal: activeController.signal }),
      ])
      const [logsData, statsData] = await Promise.all([readJson(logsResponse), readJson(statsResponse)])
      items.value = logsData.items
      total.value = logsData.total
      stats.value = statsData
      authRequired.value = false
    } catch (caught) {
      if ((caught as Error).name === 'AbortError') return
      const status = (caught as Error & { status?: number }).status
      authRequired.value = status === 401
      error.value = (caught as Error).message
      if (status === 401) {
        items.value = []
        stats.value = null
      }
    } finally {
      if (controller === activeController) loading.value = false
    }
  }

  function scheduleRefresh(delay = 0) {
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(refresh, delay)
  }

  function setAutoRefresh(enabled: boolean) {
    autoRefresh.value = enabled
    if (refreshTimer) clearInterval(refreshTimer)
    refreshTimer = enabled ? setInterval(refresh, 15_000) : null
  }

  function openLogin() {
    window.dispatchEvent(new CustomEvent('aigc:open-login'))
  }

  watch(() => filters.keyword, () => { page.value = 1; scheduleRefresh(350) })
  watch(() => [filters.module, filters.severity, filters.outcome], () => { page.value = 1; scheduleRefresh() })
  watch([page, pageSize], () => scheduleRefresh())
  onBeforeUnmount(() => {
    controller?.abort()
    if (debounceTimer) clearTimeout(debounceTimer)
    if (refreshTimer) clearInterval(refreshTimer)
  })

  return {
    items, stats, total, page, pageSize, loading, error, authRequired,
    autoRefresh, filters, exportUrl, refresh, setAutoRefresh, openLogin,
  }
}
