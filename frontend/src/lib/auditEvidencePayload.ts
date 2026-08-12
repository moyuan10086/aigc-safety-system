interface BuildInput {
  eventId: string
  sampleName: string
  reportId?: string
  customNote?: string
  operatorId?: string
  results: Record<string, any>
}

const rounded = (value: unknown) => typeof value === 'number' ? Number(value.toFixed(4)) : null

export const buildAuditEvidencePayload = (input: BuildInput) => {
  const { results } = input
  const credentials = results.provenance?.source_evidence?.content_credentials || {}
  return {
    event_id: input.eventId,
    sample_id: input.sampleName.slice(0, 120),
    ...(input.reportId ? { report_id: input.reportId } : {}),
    ...(input.operatorId ? { operator_id: input.operatorId } : {}),
    ...(input.customNote?.trim() ? { custom_note: input.customNote.trim().slice(0, 500) } : {}),
    platform_version: 'aigc-safety-system',
    deepfake: results.deepfake ? {
      status: 'completed', label: results.deepfake.label || 'unknown',
      score: rounded(results.deepfake.score), confidence: rounded(results.deepfake.confidence),
      model: results.deepfake.model || null,
    } : { status: 'not_run', label: null, score: null, confidence: null, model: null },
    provenance: results.provenance ? {
      status: 'completed', state: results.provenance.overall_state || 'inconclusive',
      provider: credentials.claim_generator || results.provenance.local_c2pa?.claimGenerator || null,
      source_type: results.provenance.local_c2pa?.sourceType || null,
    } : { status: 'not_run', state: null, provider: null, source_type: null },
    content_safety: results.content_safety ? {
      status: 'completed', verdict: results.content_safety.verdict || 'review',
      risk_score: rounded(results.content_safety.risk_score),
      categories: (results.content_safety.categories || []).slice(0, 10).map((item:any) => item.code || item.label),
    } : { status: 'not_run', verdict: null, risk_score: null, categories: [] },
    rag: results.rag ? {
      status: 'completed', safe: !!results.rag.safe, risk_level: results.rag.risk_level || null,
      matched_keywords: (results.rag.matched_keywords || []).slice(0, 10),
    } : { status: 'not_run', safe: null, risk_level: null, matched_keywords: [] },
    human_review: { status: 'pending', verdict: null },
  }
}
