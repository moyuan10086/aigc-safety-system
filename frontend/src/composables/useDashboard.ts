import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { createDebouncedTask } from '../lib/scheduling'

export interface ShadowEvaluationSummary {
  observed_events: number
  evaluated_samples: number
  agreement_count: number
  disagreement_count: number
  not_comparable_count: number
  agreement_rate: number
  false_positive_candidates: number
  false_negative_candidates: number
  target_labels: number
  pilot_target_labels: number
  pilot_remaining_count: number
  pilot_completed: boolean
  target_completed: boolean
  eligible_samples: number
  pending_reviews: number
  reviewed_count: number
  reviewer_reviewed_count: number
  verified_review_count: number
  unverified_review_count: number
  review_integrity_complete: boolean
  review_completion_rate: number
  active_claims: number
  claimed_by_me_count: number
  remaining_count: number
  p95_latency_ms: number
  statuses: Record<string, number>
  review_labels: Record<string, number>
  reviewer_counts: Array<{ reviewer: string; count: number }>
}

export interface ShadowReviewItem {
  event_id: string
  occurred_at: string
  primary_verdict: 'safe' | 'borderline' | 'unsafe'
  risk_code?: string
  risk_score?: number
  content_hash?: string
  categories: string[]
  shadow_status: string
  shadow_decision?: 'pass' | 'fail'
  shadow_confidence?: number
  shadow_alert: boolean
  shadow_latency_ms?: number
  shadow_risk_type?: string
  is_disagreement: boolean
  priority: 'disagreement' | 'stratified'
  has_evidence: boolean
  evidence_reviewed: boolean
  claim_state: 'available' | 'mine' | 'other'
  claim_expires_at?: string
  review_label?: 'safe' | 'borderline' | 'unsafe'
  reason_code?: string
  review_note?: string
  reviewer?: string
  reviewed_at?: string
  review_claim_verified: boolean
  label_evidence_verified: boolean
}

export interface ReviewResolution {
  event_id: string
  review_label: 'safe' | 'borderline' | 'unsafe'
  reason_code: string
  review_note?: string
  reviewer: string
  reviewed_at: string
  next_event_id?: string
  next_claim_expires_at?: string
}

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
  shadow_evaluation: ShadowEvaluationSummary
  shadow_reviews: ShadowReviewItem[]
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
  const reviewingEventId = ref('')
  let controller: AbortController | null = null
  let timer: ReturnType<typeof setInterval> | null = null
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

  const refreshScheduler = createDebouncedTask(() => { void refresh(true) }, 220)

  async function resolveShadowReview(eventId: string, reviewLabel: 'safe' | 'borderline' | 'unsafe', reviewNote = '') {
    if (reviewingEventId.value) return
    reviewingEventId.value = eventId
    try {
      const response = await fetch(`/api/dashboard/shadow-reviews/${eventId}`, {
        method: 'PUT',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ review_label: reviewLabel, review_note: reviewNote.trim() || null }),
      })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) {
        const detail = typeof body.detail === 'string' ? body.detail : '人工复核保存失败'
        throw new Error(detail)
      }
      await refresh(true)
      return body as ReviewResolution
    } finally {
      reviewingEventId.value = ''
    }
  }

  async function claimReview(eventId: string) {
    if (reviewingEventId.value && reviewingEventId.value !== eventId) return
    reviewingEventId.value = eventId
    try {
      const response = await fetch(`/api/dashboard/review-claims/${eventId}`, {
        method: 'POST',
        credentials: 'same-origin',
      })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) {
        const detail = typeof body.detail === 'string' ? body.detail : '复核样本领取失败'
        throw new Error(detail)
      }
      return body as { event_id: string; expires_at: string; lease_seconds: number }
    } finally {
      reviewingEventId.value = ''
    }
  }

  function openLogin() { window.dispatchEvent(new CustomEvent('aigc:open-login')) }
  watch(hours, refreshScheduler.schedule)
  onMounted(() => {
    refresh(true)
    timer = setInterval(() => refresh(), 15_000)
  })
  onBeforeUnmount(() => {
    controller?.abort()
    if (timer) clearInterval(timer)
    refreshScheduler.cancel()
  })
  return { data, hours, loading, error, authRequired, reviewingEventId, refresh, claimReview, resolveShadowReview, openLogin }
}
